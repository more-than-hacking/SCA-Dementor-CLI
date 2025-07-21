#!/usr/bin/env python3
"""
MTH_DEPENDENCY_PARSER.py
MTH Dependency Parser - Parses dependencies from repositories with hash-based caching.
"""

import os
import json
import yaml
import hashlib
import subprocess
import shutil
import importlib
import argparse
import logging
from pathlib import Path

# --- Configuration ---
REPO_ROOT = 'REPOSITORIES'

DEPENDENCY_RESULTS_FILE = 'dependency_results.json'
SKIPPED_LOG_PATH = 'skipped_libraries.log'

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Configuration Loading ---
def load_config():
    """Load parser configuration."""
    try:
        with open("config/parser_config.yaml", "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading parser config: {e}")
        return {}

def load_main_config(config_path="config/org_config.yaml"):
    """Load main configuration from org_config.yaml."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config.get("github", {}).get("org_name"), config.get("github", {}).get("token")
    except Exception as e:
        logging.error(f"FATAL: Error loading config '{config_path}': {e}")
        return None, None

def load_dependency_config(yaml_path="config/Languages.yaml"):
    """Load dependency file patterns from Languages.yaml."""
    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        all_files = []
        for file_list in config.get("languages", {}).values():
            all_files.extend(f for f in file_list if '*' not in f)
        return list(set(all_files))
    except Exception as e:
        logging.error(f"Error loading dependency config: {e}")
        return []

# --- Hash Cache Management ---


def load_existing_results():
    """Load existing dependency results."""
    if os.path.exists(DEPENDENCY_RESULTS_FILE):
        try:
            with open(DEPENDENCY_RESULTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Error loading existing results: {e}")
    return {}

def get_repos_to_check():
    """Get list of repositories to check."""
    if not os.path.exists(REPO_ROOT):
        logging.error(f"Repository directory '{REPO_ROOT}' does not exist. Run MTH_REPO_FETCHER.py first.")
        return []
    
    repos_to_process = []
    for repo_name in os.listdir(REPO_ROOT):
        repo_path = os.path.join(REPO_ROOT, repo_name)
        if os.path.isdir(repo_path):
            repos_to_process.append(repo_name)
    
    return repos_to_process

def parse_repository_dependencies(repo_path, repo_name, dependency_config):
    """Parse dependencies for a specific repository."""
    all_dependencies = []
    
    # Load parser configuration
    config = load_config()
    
    for lang, lang_conf in config.items():
        parser_name = lang_conf.get('parser')
        patterns = lang_conf.get('patterns', [])

        try:
            # Add current directory to Python path for parser imports
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            parser_module = importlib.import_module(f'parsers.{parser_name}')
        except ImportError:
            logging.warning(f"Skipping '{lang}' - parser '{parser_name}' not found")
            continue

        if not hasattr(parser_module, 'parse'):
            logging.warning(f"Skipping '{lang}' - no 'parse()' function found in parser")
            continue

        logging.info(f"  Discovering files for '{lang}' using patterns: {patterns}")
        dep_files = discover_files(repo_path, {lang: lang_conf})
        logging.info(f"  Found {len(dep_files)} files for '{lang}'")

        for file_path in dep_files:
            logging.info(f"\n    Parsing: {file_path}")
            try:
                results, skipped = parser_module.parse(file_path)
                logging.info(f"      Found {len(results)} dependencies")
                if skipped:
                    logging.info(f"      Skipped {len(skipped)} dependencies")
                    for skip in skipped:
                        logging.info(f"        - {skip}")
                
                all_dependencies.extend(results)
                
            except Exception as e:
                logging.error(f"Error parsing {file_path}: {e}")

    return all_dependencies

def save_dependency_results(results):
    """Save dependency results to file."""
    with open(DEPENDENCY_RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

# --- GitHub API Functions ---
def get_repo_latest_hash(org, repo_name, token):
    """Get the latest commit hash for a repository."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{org}/{repo_name}/commits"
    try:
        import requests
        response = requests.get(url, headers=headers, params={"per_page": 1}, timeout=30)
        if response.status_code == 200:
            commits = response.json()
            if commits:
                return commits[0]["sha"]
        logging.warning(f"Could not get latest hash for {repo_name}")
        return None
    except Exception as e:
        logging.error(f"Error getting hash for {repo_name}: {e}")
        return None

# --- Git Operations ---
def run_git_command(command, working_dir="."):
    try:
        logging.info(f"Running command: {' '.join(command)} in '{working_dir}'")
        result = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed in '{working_dir}': {' '.join(command)}")
        logging.error(f"Stderr: {e.stderr.strip()}")
        return False

def clone_or_update_repo(repo_name, org, token, files_to_find):
    """Clone or update a repository."""
    repo_path = os.path.join(REPO_ROOT, repo_name)
    clone_url = f"https://{token}@github.com/{org}/{repo_name}.git"

    # Always clone or update to check for GitHub changes
    if os.path.isdir(os.path.join(repo_path, '.git')):
        logging.info(f"Repository '{repo_name}' exists. Pulling latest changes...")
        return run_git_command(["git", "pull"], working_dir=repo_path)
    else:
        if os.path.exists(repo_path):
            logging.info(f"'{repo_path}' exists but is not a git repo. Removing and re-cloning.")
            shutil.rmtree(repo_path)
        logging.info(f"Cloning '{repo_name}'...")
        return run_git_command(["git", "clone", "--depth", "1", clone_url, repo_path])

# --- Repository Purging ---
def prune_repo(repo_path, files_to_keep_basenames):
    """Purge repository to keep only dependency files."""
    logging.info(f"Pruning '{repo_path}' to keep only specified dependency files...")

    files_to_keep_full_path = set()
    for root, _, files in os.walk(repo_path):
        for name in files:
            if name in files_to_keep_basenames:
                files_to_keep_full_path.add(os.path.join(root, name))

    if not files_to_keep_full_path:
        logging.warning(f"No target files found in '{repo_path}'. Removing entire directory.")
        try:
            shutil.rmtree(repo_path)
        except OSError as e:
            logging.error(f"Error removing directory {repo_path}: {e}")
        return

    for root, _, files in os.walk(repo_path):
        for name in files:
            file_path = os.path.join(root, name)
            if file_path not in files_to_keep_full_path:
                try:
                    os.remove(file_path)
                except OSError as e:
                    logging.error(f"Error removing file {file_path}: {e}")

    for root, dirs, _ in os.walk(repo_path, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if dir_path == os.path.join(repo_path, '.git'):
                continue
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except OSError as e:
                logging.error(f"Error removing directory {dir_path}: {e}")

    git_dir = os.path.join(repo_path, '.git')
    if os.path.exists(git_dir):
        try:
            shutil.rmtree(git_dir)
            logging.info(f"Removed .git directory from {repo_path}")
        except OSError as e:
            logging.error(f"Error removing .git directory from {repo_path}: {e}")

# --- Hash Calculation ---
# --- Repository Processing ---
def process_repository(repo_name, files_to_find, org, token):
    """Process repository - clone, purge, and prepare for dependency parsing."""
    logging.info(f"Processing repository: {repo_name}")
    
    repo_path = os.path.join(REPO_ROOT, repo_name)
    
    # Clone or update repository
    if not clone_or_update_repo(repo_name, org, token, files_to_find):
        logging.error(f"Could not clone or update '{repo_name}'. Skipping.")
        return False
    
    # Purge repository to keep only dependency files
    prune_repo(repo_path, files_to_find)
    logging.info(f"Repository '{repo_name}' processed successfully")
    
    return True

# --- File Discovery ---
def discover_files(root, config_by_lang):
    all_files = []
    for lang, config in config_by_lang.items():
        for pattern in config.get('patterns', []):
            search_pattern = os.path.join(root, '**', pattern)
            import glob
            files = glob.glob(search_pattern, recursive=True)
            all_files.extend(files)
    return all_files

def get_repo_from_file_path(file_path):
    """Extract repository name from file path."""
    relative_path = os.path.relpath(file_path, REPO_ROOT)
    repo_name = relative_path.split(os.sep)[0]
    return repo_name

# --- Main Execution ---
def main():
    """Main function to parse dependencies from repositories."""
    parser = argparse.ArgumentParser(description='Parse dependencies from repositories')
    parser.add_argument('--repo', type=str, help='Specific repository to process (restricted to configured org)')
    parser.add_argument('--url', type=str, help='Direct repository URL (universal scope)')
    parser.add_argument('--repo-list', type=str, help='File containing list of repositories to process')
    parser.add_argument('--force-scan', action='store_true', help='Force fresh scan regardless of existing data')
    parser.add_argument('--one-time-scan', action='store_true', help='One-time scan: don\'t save cache or results')
    args = parser.parse_args()
    
    logging.info("📄 Loaded 48 dependency file patterns")
    
    # For CLI tool, no hash cache needed
    logging.info("🔄 CLI mode: No hash cache needed")
    
    # Load existing results only if not one-time scan
    if args.one_time_scan:
        existing_results = {}
        logging.info("🔄 One-time scan mode: Skipping existing results loading")
    else:
        existing_results = load_existing_results()
        logging.info(f"📊 Loaded existing results with {len(existing_results)} dependencies")
    
    # Load configurations
    org, token = load_main_config()
    if not org or not token:
        logging.error("❌ Could not load GitHub configuration. Exiting.")
        return
    dependency_config = load_dependency_config()
    
    # Determine repositories to process
    repos_to_check = []
    
    if args.repo:
        # Process specific repository
        repos_to_check = [args.repo]
        logging.info(f"🔍 Processing specific repository: {args.repo}")
    elif args.url:
        # Process repository from URL
        try:
            # Import the parse_github_url function from repo fetcher
            import sys
            sys.path.append('core')
            from MTH_REPO_FETCHER import parse_github_url
            url_info = parse_github_url(args.url)
            repos_to_check = [url_info['repo_name']]
            logging.info(f"🔍 Processing repository from URL: {url_info['repo_name']}")
        except Exception as e:
            logging.error(f"Error parsing URL: {e}")
            return
    elif args.repo_list:
        # Process repositories from file
        try:
            with open(args.repo_list, 'r') as f:
                repos_to_check = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logging.info(f"🔍 Processing repositories from file: {repos_to_check}")
        except Exception as e:
            logging.error(f"Error reading repo list file: {e}")
            return
    else:
        # Process all repositories in REPOSITORIES folder
        repos_to_check = get_repos_to_check()
        logging.info(f"🔍 Processing all repositories: {repos_to_check}")
    
    if not repos_to_check:
        logging.error("No repositories to process")
        return
    
    # Process all repositories fresh (no hash cache needed for CLI)
    logging.info("🔄 CLI mode: Processing all repositories fresh")
    
    # Process all repositories
    for repo_name in repos_to_check:
        logging.info(f"\n🔍 Processing repository: {repo_name}")
        if process_repository(repo_name, dependency_config, org, token):
            logging.info(f"✅ Repository '{repo_name}' processed successfully")
        else:
            logging.warning(f"⚠️ Repository '{repo_name}' processing failed")
    
    # Parse dependencies for all repositories
    logging.info("🔄 Processing dependencies for all repositories...")
    
    # Process dependencies for changed repositories
    all_dependencies = []
    
    for repo_name in repos_to_check:
        repo_path = os.path.join(REPO_ROOT, repo_name)
        if not os.path.exists(repo_path):
            logging.warning(f"⚠️ Repository '{repo_name}' not found, skipping...")
            continue
            
        logging.info(f"\n🔍 Processing dependencies for: {repo_name}")
        
        # Parse dependencies for this repository
        repo_dependencies = parse_repository_dependencies(repo_path, repo_name, dependency_config)
        
        # Add new dependencies to the list
        all_dependencies.extend(repo_dependencies)
    
    # Save updated results only if not one-time scan
    if not args.one_time_scan:
        save_dependency_results(all_dependencies)
        logging.info(f"💾 Saved {len(all_dependencies)} dependencies to dependency_results.json")
    else:
        logging.info(f"🔄 One-time scan: Found {len(all_dependencies)} dependencies (not saved)")
    
    if args.one_time_scan:
        logging.info("✅ One-time scan dependency parsing completed! (No results saved)")
    else:
        logging.info("✅ Dependency parsing completed!")

if __name__ == '__main__':
    main()
