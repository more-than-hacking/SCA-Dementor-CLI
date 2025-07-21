#!/usr/bin/env python3
"""
MTH_REPO_FETCHER.py
MTH Repository Fetcher - Fetches repositories and manages hash caching for dependency scanning.
"""

import os
import json
import logging
import subprocess
import shutil
import hashlib
import argparse
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- Configuration ---
BASE_REPOS_DIR = 'REPOSITORIES'

GITHUB_TOKEN = None
ORG_NAME = None
URL_CLONE_INFO = None  # Store URL info for direct URL cloning

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def load_github_config():
    """Load GitHub configuration from org_config.yaml."""
    try:
        with open("config/org_config.yaml", "r") as f:
            config = yaml.safe_load(f)
        global GITHUB_TOKEN, ORG_NAME
        GITHUB_TOKEN = config.get("github", {}).get("token")
        ORG_NAME = config.get("github", {}).get("org_name")
        if not GITHUB_TOKEN or not ORG_NAME:
            raise ValueError("Missing GitHub token or org_name in config")
        return True
    except Exception as e:
        logging.error(f"Error loading GitHub config: {e}")
        return False

def load_dependency_config():
    """Load dependency file patterns from Languages.yaml."""
    try:
        with open("config/Languages.yaml", 'r') as f:
            config = yaml.safe_load(f)
        all_files = []
        for file_list in config.get("languages", {}).values():
            all_files.extend(f for f in file_list if '*' not in f)
        return list(set(all_files))
    except Exception as e:
        logging.error(f"Error loading dependency config: {e}")
        return []



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

def run_git_command(command, working_dir="."):
    """Run git command and return success status."""
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

def clone_or_update_repo(repo_name, files_to_find):
    """Clone or update a repository."""
    repo_path = os.path.join(BASE_REPOS_DIR, repo_name)
    
    # Use URL info if available (for direct URL cloning), otherwise use config
    global URL_CLONE_INFO
    if URL_CLONE_INFO and URL_CLONE_INFO['repo_name'] == repo_name:
        clone_url = URL_CLONE_INFO['clone_url']
        logging.info(f"Using direct URL for cloning: {clone_url}")
    else:
        clone_url = f"https://{GITHUB_TOKEN}@github.com/{ORG_NAME}/{repo_name}.git"
        logging.info(f"Using configured org/token for cloning: {clone_url}")

    # Check if repository directory exists
    if os.path.exists(repo_path):
        if os.path.isdir(os.path.join(repo_path, '.git')):
            logging.info(f"Repository '{repo_name}' exists. Pulling latest changes...")
            return run_git_command(["git", "pull"], working_dir=repo_path)
        else:
            logging.info(f"'{repo_path}' exists but is not a git repo. Removing and re-cloning.")
            shutil.rmtree(repo_path)
            logging.info(f"Cloning '{repo_name}'...")
            return run_git_command(["git", "clone", "--depth", "1", clone_url, repo_path])
    else:
        logging.info(f"Cloning '{repo_name}'...")
        return run_git_command(["git", "clone", "--depth", "1", clone_url, repo_path])

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

def calculate_repo_hash(repo_path):
    """Calculate hash of repository after purging."""
    if not os.path.exists(repo_path):
        return None
    
    hash_md5 = hashlib.md5()
    
    for root, dirs, files in os.walk(repo_path):
        # Sort for consistent hashing
        dirs.sort()
        files.sort()
        
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'rb') as f:
                    hash_md5.update(f.read())
            except Exception as e:
                logging.error(f"Error reading file {file_path}: {e}")
    
    return hash_md5.hexdigest()

def process_repo_with_hash_check(repo_name, files_to_find, hash_cache, org, token, force_scan=False):
    """Process repository with proper hash checking after cloning and purging."""
    logging.info(f"Processing repository: {repo_name}")
    
    repo_path = os.path.join(BASE_REPOS_DIR, repo_name)
    
    # Always clone/update to check for GitHub changes
    # We need to know about GitHub changes, so we can't skip cloning based on cached hash
    if not os.path.exists(repo_path):
        logging.info(f"Cloning '{repo_name}'...")
        clone_or_update_repo(repo_name, files_to_find)
    else:
        logging.info(f"Updating '{repo_name}'...")
        clone_or_update_repo(repo_name, files_to_find)
    
    # Check if we have dependency files after clone/update
    has_dependency_files = False
    for root, _, files in os.walk(repo_path):
        for name in files:
            if any(name.endswith(pattern) for pattern in files_to_find):
                has_dependency_files = True
                break
        if has_dependency_files:
            break
    
    if not has_dependency_files:
        logging.info(f"Repository '{repo_name}' has no dependency files, skipping...")
        return False
    
    # Prune repository to keep only dependency files
    logging.info(f"Pruning '{repo_path}' to keep only specified dependency files...")
    prune_repo(repo_path, files_to_find)
    
    # Calculate hash after pruning
    current_hash = calculate_repo_hash(repo_path)
    if not current_hash:
        logging.error(f"❌ Could not calculate hash for '{repo_name}'")
        return False
    
    # For force scan, always process regardless of hash
    if force_scan:
        logging.info(f"Force scan mode: Repository '{repo_name}' will be processed regardless of hash")
        hash_cache[repo_name] = current_hash
        return True
    
    # Check if hash changed
    cached_hash = hash_cache.get(repo_name)
    if cached_hash == current_hash:
        logging.info(f"Repository '{repo_name}' unchanged ({current_hash[:8]}), skipping...")
        return False
    else:
        if cached_hash is None:
            logging.info(f"Repository '{repo_name}' is new, will process")
        else:
            logging.info(f"Repository '{repo_name}' changed ({cached_hash[:8]} → {current_hash[:8]}), will process")
        
        # Update hash cache
        hash_cache[repo_name] = current_hash
        return True

def get_all_repos_from_org():
    """Get all repositories from the organization."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/orgs/{ORG_NAME}/repos"
    
    try:
        import requests
        response = requests.get(url, headers=headers, params={"per_page": 100}, timeout=30)
        if response.status_code == 200:
            repos = response.json()
            return [repo["name"] for repo in repos if not repo["archived"]]
        else:
            logging.error(f"Failed to fetch repos: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Error fetching repositories: {e}")
        return []

def get_repos_from_file(file_path):
    """Get repository list from a file."""
    try:
        with open(file_path, 'r') as f:
            repos = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return repos
    except Exception as e:
        logging.error(f"Error reading repo file {file_path}: {e}")
        return []

def parse_github_url(url):
    """Parse GitHub URL to extract org, repo name, and token if present."""
    import re
    
    # Remove .git suffix if present
    if url.endswith('.git'):
        url = url[:-4]
    
    # Pattern to match GitHub URLs with optional token
    # https://token@github.com/org/repo
    # https://github.com/org/repo
    pattern = r'https://(?:([^@]+)@)?github\.com/([^/]+)/([^/\s]+)'
    match = re.match(pattern, url)
    
    if not match:
        raise ValueError(f"Invalid GitHub URL format: {url}")
    
    token = match.group(1)  # Can be None
    org = match.group(2)
    repo_name = match.group(3)
    
    return {
        'org': org,
        'repo_name': repo_name,
        'token': token,
        'clone_url': url + '.git' if not url.endswith('.git') else url
    }

def main():
    """Main function to fetch repositories based on command line arguments."""
    parser = argparse.ArgumentParser(description='Fetch repositories for dependency scanning')
    parser.add_argument('--full-repo-scan', action='store_true', 
                       help='Scan all repositories in the organization')
    parser.add_argument('--repo-list', type=str, 
                       help='Path to file containing list of repositories to scan')
    parser.add_argument('--folderpath', type=str, 
                       help='Path to local folder (no cloning needed)')
    parser.add_argument('--repo', type=str, 
                       help='Specific repository name (format: org/repo-name) - restricted to configured org')
    parser.add_argument('--url', type=str, 
                       help='Direct repository URL (universal scope - can be any GitHub repo with/without token)')
    parser.add_argument('--workers', type=int, default=5,
                       help='Number of worker threads (default: 5)')
    parser.add_argument('--force-scan', action='store_true',
                       help='Force fresh scan regardless of existing data')
    parser.add_argument('--one-time-scan', action='store_true',
                       help='One-time scan: don\'t save cache or repositories')
    
    args = parser.parse_args()
    
    # Load configurations
    if not load_github_config():
        logging.error("Failed to load GitHub configuration")
        return
    
    files_to_find = load_dependency_config()
    if not files_to_find:
        logging.error("Failed to load dependency configuration")
        return
    
    logging.info(f"📄 Loading dependency configuration from: config/Languages.yaml")
    logging.info(f"Loaded {len(files_to_find)} unique dependency file targets from config/Languages.yaml.")
    
    # Load hash cache only if not one-time scan
    if args.one_time_scan:
        logging.info("🔄 One-time scan mode: Skipping cache loading and saving")
        hash_cache = {}
    else:
        hash_cache = load_hash_cache()
        logging.info(f"Loaded hash cache with {len(hash_cache)} repositories")
    
    # Determine repositories to process
    repos_to_process = []
    
    if args.full_repo_scan:
        logging.info("Using full repository scan mode")
        repos_to_process = get_all_repos_from_org()
        logging.info(f"Found {len(repos_to_process)} repositories in organization")
        
    elif args.repo_list:
        logging.info(f"Using repository list from: {args.repo_list}")
        repos_to_process = get_repos_from_file(args.repo_list)
        logging.info(f"Loaded {len(repos_to_process)} repositories from file")
        
    elif args.folderpath:
        logging.info(f"Using local folder: {args.folderpath}")
        if os.path.exists(args.folderpath):
            # For local folder, just add it to hash cache without cloning
            folder_name = os.path.basename(args.folderpath)
            repos_to_process = [folder_name]
            logging.info(f"Processing local folder: {folder_name}")
        else:
            logging.error(f"Folder path does not exist: {args.folderpath}")
            return
            
    elif args.repo:
        logging.info(f"Using specific repository: {args.repo}")
        if '/' in args.repo:
            org, repo_name = args.repo.split('/', 1)
            if org != ORG_NAME:
                logging.warning(f"Repository org '{org}' differs from config org '{ORG_NAME}'")
            repos_to_process = [repo_name]
        else:
            repos_to_process = [args.repo]
        logging.info(f"Processing specific repository: {repos_to_process[0]}")
        
    elif args.url:
        logging.info(f"Using direct repository URL: {args.url}")
        try:
            url_info = parse_github_url(args.url)
            repos_to_process = [url_info['repo_name']]
            # Store URL info for later use in cloning
            global URL_CLONE_INFO
            URL_CLONE_INFO = url_info
            logging.info(f"Parsed URL - Org: {url_info['org']}, Repo: {url_info['repo_name']}")
        except ValueError as e:
            logging.error(f"Invalid GitHub URL: {e}")
            return
        
    else:
        logging.error("No mode specified. Use --full-repo-scan, --repo-list, --folderpath, --repo, or --url")
        parser.print_help()
        return
    
    if not repos_to_process:
        logging.error("No repositories to process")
        return
    
    logging.info(f"🚀 Starting git processing with {args.workers} workers.")
    
    # Process repositories
    updated_cache = hash_cache.copy()
    
    if args.folderpath:
        # For local folder, just calculate hash without cloning
        folder_name = os.path.basename(args.folderpath)  # Use actual folder name instead of fixed name
        repo_path = os.path.join(BASE_REPOS_DIR, folder_name)
        
        # Create symlink or copy if needed
        if not os.path.exists(repo_path):
            os.makedirs(BASE_REPOS_DIR, exist_ok=True)
        
        # Remove existing symlink if it exists
        if os.path.exists(repo_path):
            if os.path.islink(repo_path):
                os.unlink(repo_path)
            elif os.path.isdir(repo_path):
                import shutil
                shutil.rmtree(repo_path)
            else:
                os.remove(repo_path)
        
        # Create new symlink - point to the actual folder path, not /app
        actual_path = os.path.abspath(args.folderpath)
        os.symlink(actual_path, repo_path)
        
        # Calculate hash for local folder (only if not one-time scan)
        if not args.one_time_scan:
            current_hash = calculate_repo_hash(repo_path)
            if current_hash:
                updated_cache[folder_name] = current_hash
                logging.info(f"Calculated hash for local folder '{folder_name}': {current_hash[:8]}")
    else:
        # Process repositories with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_repo_with_hash_check, repo, files_to_find, updated_cache, ORG_NAME, GITHUB_TOKEN, args.force_scan): repo 
                      for repo in repos_to_process}
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="📦 Repositories"):
                repo_name = futures[future]
                try:
                    # The function now returns True if repository was processed, False if skipped
                    # The hash cache is updated within the function
                    processed = future.result()
                    if processed:
                        logging.info(f"Repository '{repo_name}' was processed")
                    else:
                        logging.info(f"Repository '{repo_name}' was skipped")
                except Exception as e:
                    logging.error(f"Error processing {repo_name}: {e}")
    
    # Save updated hash cache only if not one-time scan
    if not args.one_time_scan:
        save_hash_cache(updated_cache)
        logging.info("✅ Repository processing completed!")
    else:
        logging.info("✅ One-time scan completed! (No cache saved)")

if __name__ == "__main__":
    main()