# MTH_SCA_SCANNER.py
# MTH Security Scanner - Combines modular parser support + latest verification + full detail report

import json
import os
import requests
import argparse
import importlib
import yaml
import subprocess
import shutil
import hashlib
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from packaging.version import Version, InvalidVersion
import logging

# --- Constants ---
REPO_ROOT = "REPOSITORIES"
MAX_QUERIES_PER_BATCH = 100
MAX_WORKERS = 10

# Default reports directory (will be overridden by --output-dir if specified)
REPORTS_DIR = "reports"

# Global variable for URL clone info
URL_CLONE_INFO = None

# --- Config ---
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_SINGLE_URL = "https://api.osv.dev/v1/query"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/"
VULNERABILITY_RESULTS_FILE = "vulnerability_results.json"

# --- Helper Functions ---
def normalize_ecosystem(name: str) -> str:
    mapping = {"maven": "Maven", "pypi": "PyPI", "npm": "npm", "golang": "Go", "go": "Go", "nuget": "NuGet", "rubygems": "RubyGems"}
    return mapping.get(name.lower(), name)



def get_repo_from_file_path(file_path):
    """Extract repository name from file path."""
    # Handle both host and Docker container paths
    if file_path.startswith('REPOSITORIES/'):
        # Direct path format
        parts = file_path.split('/')
        if len(parts) >= 2:
            return parts[1]
    elif 'REPOSITORIES' in file_path:
        # Full path format, extract after REPOSITORIES
        parts = file_path.split('REPOSITORIES')
        if len(parts) > 1:
            repo_part = parts[1].strip('/')
            if '/' in repo_part:
                return repo_part.split('/')[0]
            return repo_part
    
    # Fallback: try relative path method
    try:
        relative_path = os.path.relpath(file_path, REPO_ROOT)
        repo_name = relative_path.split(os.sep)[0]
        return repo_name
    except:
        # If all else fails, try to extract from the path
        if '/' in file_path:
            parts = file_path.split('/')
            for i, part in enumerate(parts):
                if part == 'REPOSITORIES' and i + 1 < len(parts):
                    return parts[i + 1]
    
    return "unknown"

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

def get_repo_latest_hash(org, repo_name, token):
    """Get the latest commit hash for a repository."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{org}/{repo_name}/commits"
    try:
        response = requests.get(url, headers=headers, params={"per_page": 1}, timeout=30)
        if response.status_code == 200:
            commits = response.json()
            if commits:
                return commits[0]["sha"]
        print(f"Could not get latest hash for {repo_name}")
        return None
    except Exception as e:
        print(f"Error getting hash for {repo_name}: {e}")
        return None

def run_git_command(command, working_dir="."):
    try:
        print(f"Running command: {' '.join(command)} in '{working_dir}'")
        result = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git command failed in '{working_dir}': {' '.join(command)}")
        print(f"Stderr: {e.stderr.strip()}")
        return False

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

def clone_or_update_repo(repo_name, org, token, files_to_find):
    """Clone or update a repository."""
    repo_path = os.path.join(REPO_ROOT, repo_name)
    
    # Check if we have URL info for this repository
    global URL_CLONE_INFO
    if URL_CLONE_INFO and URL_CLONE_INFO['repo_name'] == repo_name:
        clone_url = URL_CLONE_INFO['clone_url']
        # Hide token in logs
        safe_url = clone_url.replace(token, '***') if token else clone_url
        print(f"Using direct URL for cloning: {safe_url}")
    else:
        clone_url = f"https://{token}@github.com/{org}/{repo_name}.git"
        safe_url = f"https://***@github.com/{org}/{repo_name}.git"
        print(f"Using configured org/token for cloning: {safe_url}")

    # Always clone or update to check for GitHub changes
    if os.path.isdir(os.path.join(repo_path, '.git')):
        print(f"Repository '{repo_name}' exists. Pulling latest changes...")
        return run_git_command(["git", "pull"], working_dir=repo_path)
    else:
        if os.path.exists(repo_path):
            print(f"'{repo_path}' exists but is not a git repo. Removing and re-cloning.")
            shutil.rmtree(repo_path)
        print(f"Cloning '{repo_name}'...")
        return run_git_command(["git", "clone", "--depth", "1", clone_url, repo_path])

def prune_repo(repo_path, files_to_keep_basenames):
    """Purge repository to keep only dependency files."""
    print(f"Pruning '{repo_path}' to keep only specified dependency files...")

    files_to_keep_full_path = set()
    for root, _, files in os.walk(repo_path):
        for name in files:
            if name in files_to_keep_basenames:
                files_to_keep_full_path.add(os.path.join(root, name))

    if not files_to_keep_full_path:
        print(f"No target files found in '{repo_path}'. Removing entire directory.")
        try:
            shutil.rmtree(repo_path)
        except OSError as e:
            print(f"Error removing directory {repo_path}: {e}")
        return

    for root, _, files in os.walk(repo_path):
        for name in files:
            file_path = os.path.join(root, name)
            if file_path not in files_to_keep_full_path:
                try:
                    os.remove(file_path)
                except OSError as e:
                    print(f"Error removing file {file_path}: {e}")

    for root, dirs, _ in os.walk(repo_path, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if dir_path == os.path.join(repo_path, '.git'):
                continue
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except OSError as e:
                print(f"Error removing directory {dir_path}: {e}")

    git_dir = os.path.join(repo_path, '.git')
    if os.path.exists(git_dir):
        try:
            shutil.rmtree(git_dir)
            print(f"Removed .git directory from {repo_path}")
        except OSError as e:
            print(f"Error removing .git directory from {repo_path}: {e}")

def process_repository(repo_name, files_to_find, org, token):
    """Process repository - clone, purge, and prepare for scanning."""
    print(f"\n🔍 Processing repository: {repo_name}")
    
    repo_path = os.path.join(REPO_ROOT, repo_name)
    
    # Clone or update repository
    if not clone_or_update_repo(repo_name, org, token, files_to_find):
        print(f"❌ Could not clone or update '{repo_name}'. Skipping.")
        return False
    
    # Purge repository to keep only dependency files
    prune_repo(repo_path, files_to_find)
    print(f"✅ Repository '{repo_name}' processed successfully")
    
    return True

def load_json_file(filepath: str) -> list:
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print(f"Warning: Expected list in '{filepath}', got {type(data)}")
                return []
    except Exception as e:
        print(f"Error reading '{filepath}': {e}")
        return []

def fetch_latest_version(library_name: str, ecosystem: str, parser_config: dict) -> str | None:
    parser_path = parser_config.get(ecosystem.strip())
    if not parser_path:
        return None
    try:
        module = importlib.import_module(parser_path)
        return module.fetch_latest_version(library_name)
    except Exception as e:
        print(f"[WARN] Failed to fetch latest version for {library_name}: {e}")
        return None

def check_version_vulnerabilities(name: str, version: str, ecosystem: str) -> list:
    if not all([name, version, ecosystem]): return []
    try:
        q = {"version": version, "package": {"name": name, "ecosystem": ecosystem}}
        with requests.Session() as s:
            r = s.post(OSV_SINGLE_URL, json=q, timeout=15)
            r.raise_for_status(); return [v['id'] for v in r.json().get('vulns', [])]
    except: return []

def fetch_vulns_for_chunk(chunk: list) -> dict:
    try:
        with requests.Session() as s:
            r = s.post(OSV_BATCH_URL, json={"queries": chunk}, timeout=60)
            r.raise_for_status(); return r.json()
    except: return {"results": []}

def fetch_vuln_details(osv_id: str) -> dict:
    try:
        with requests.Session() as s:
            r = s.get(f"{OSV_VULN_URL}{osv_id}", timeout=10)
            r.raise_for_status(); return r.json()
    except: return {"id": osv_id, "error": "Failed to fetch details"}

def extract_severity(vuln: dict) -> str:
    """Extract severity from vulnerability."""
    if "database_specific" in vuln and "severity" in vuln["database_specific"]:
        return vuln["database_specific"]["severity"]
    return "UNKNOWN"

def find_best_safer_version(current: str, vulns: list, lib_name: str) -> str | None:
    """Find the best safer version."""
    try:
        current_v = Version(current)
        safer_versions = []
        for vuln in vulns:
            for affected in vuln.get("affected", []):
                for range_info in affected.get("ranges", []):
                    for event in range_info.get("events", []):
                        if "fixed" in event:
                            fixed_v = event["fixed"]
                            try:
                                if Version(fixed_v) > current_v:
                                    safer_versions.append(fixed_v)
                            except InvalidVersion:
                                continue
        return min(safer_versions, key=lambda x: Version(x)) if safer_versions else None
    except InvalidVersion:
        return None

# --- Output Format Functions ---
def generate_html_report(vulnerability_results, output_file="vulnerability_report.html"):
    """Generate HTML report."""
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SCA-Dementor Vulnerability Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .vuln-item {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .high {{ border-left: 5px solid #ff4444; }}
        .medium {{ border-left: 5px solid #ffaa00; }}
        .low {{ border-left: 5px solid #44aa44; }}
        .unknown {{ border-left: 5px solid #888888; }}
        .library-name {{ font-weight: bold; font-size: 18px; }}
        .version {{ color: #666; }}
        .recommendation {{ background-color: #e8f4fd; padding: 10px; border-radius: 3px; margin: 10px 0; }}
        .vuln-details {{ margin-left: 20px; }}
        .severity {{ font-weight: bold; }}
        .summary {{ font-style: italic; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔮 SCA-Dementor Vulnerability Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Total Vulnerabilities:</strong> {len(vulnerability_results)}</p>
    </div>
"""
    
    for vuln in vulnerability_results:
        severity_class = vuln.get('vulnerabilities', [{}])[0].get('severity', 'unknown').lower()
        html_content += f"""
    <div class="vuln-item {severity_class}">
        <div class="library-name">{vuln.get('library', 'Unknown')}</div>
        <div class="version">Version: {vuln.get('version_in_use', 'Unknown')}</div>
        <div class="version">File: {vuln.get('file_location', 'Unknown')}</div>
        
        <div class="recommendation">
            <strong>Recommendation:</strong> {vuln.get('upgrade_recommendation', {}).get('recommendation', 'Manual review required.')}
        </div>
        
        <div class="vuln-details">
            <h3>Vulnerabilities:</h3>
"""
        
        for vuln_detail in vuln.get('vulnerabilities', []):
            severity = vuln_detail.get('severity', 'UNKNOWN')
            html_content += f"""
            <div class="vuln-item {severity.lower()}">
                <div class="severity">Severity: {severity}</div>
                <div class="summary">{vuln_detail.get('summary', 'No summary available')}</div>
                <div><strong>OSV ID:</strong> {vuln_detail.get('osv_id', 'Unknown')}</div>
                <div><strong>CVE IDs:</strong> {', '.join(vuln_detail.get('cve_ids', []))}</div>
                <div><strong>Published:</strong> {vuln_detail.get('published', 'Unknown')}</div>
                <div><strong>Fixed in:</strong> {vuln_detail.get('fixed_in_branch', 'Not specified')}</div>
            </div>
"""
        
        html_content += """
        </div>
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"📄 HTML report saved to '{output_file}'")

def generate_csv_report(vulnerability_results, output_file="vulnerability_report.csv"):
    """Generate CSV report."""
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['library', 'version', 'file_location', 'severity', 'osv_id', 'cve_ids', 'summary', 'recommendation', 'published', 'fixed_in']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for vuln in vulnerability_results:
            for vuln_detail in vuln.get('vulnerabilities', []):
                writer.writerow({
                    'library': vuln.get('library', ''),
                    'version': vuln.get('version_in_use', ''),
                    'file_location': vuln.get('file_location', ''),
                    'severity': vuln_detail.get('severity', ''),
                    'osv_id': vuln_detail.get('osv_id', ''),
                    'cve_ids': '; '.join(vuln_detail.get('cve_ids', [])),
                    'summary': vuln_detail.get('summary', ''),
                    'recommendation': vuln.get('upgrade_recommendation', {}).get('recommendation', ''),
                    'published': vuln_detail.get('published', ''),
                    'fixed_in': vuln_detail.get('fixed_in_branch', '')
                })
    
    print(f"📊 CSV report saved to '{output_file}'")

def generate_txt_report(vulnerability_results, output_file="vulnerability_report.txt"):
    """Generate TXT report."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("🔮 SCA-Dementor Vulnerability Report\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Vulnerabilities: {len(vulnerability_results)}\n\n")
        
        for i, vuln in enumerate(vulnerability_results, 1):
            f.write(f"{i}. {vuln.get('library', 'Unknown')} v{vuln.get('version_in_use', 'Unknown')}\n")
            f.write(f"   File: {vuln.get('file_location', 'Unknown')}\n")
            f.write(f"   Recommendation: {vuln.get('upgrade_recommendation', {}).get('recommendation', 'Manual review required.')}\n")
            
            for vuln_detail in vuln.get('vulnerabilities', []):
                f.write(f"   - Severity: {vuln_detail.get('severity', 'UNKNOWN')}\n")
                f.write(f"   - Summary: {vuln_detail.get('summary', 'No summary available')}\n")
                f.write(f"   - OSV ID: {vuln_detail.get('osv_id', 'Unknown')}\n")
                f.write(f"   - CVE IDs: {', '.join(vuln_detail.get('cve_ids', []))}\n")
                f.write(f"   - Published: {vuln_detail.get('published', 'Unknown')}\n")
                f.write(f"   - Fixed in: {vuln_detail.get('fixed_in_branch', 'Not specified')}\n")
            f.write("\n")
    
    print(f"📝 TXT report saved to '{output_file}'")

def generate_xml_report(vulnerability_results, output_file="vulnerability_report.xml"):
    """Generate XML report."""
    root = ET.Element("vulnerability_report")
    root.set("generated", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    root.set("total_vulnerabilities", str(len(vulnerability_results)))
    
    for vuln in vulnerability_results:
        vuln_elem = ET.SubElement(root, "vulnerability")
        
        library_elem = ET.SubElement(vuln_elem, "library")
        library_elem.text = vuln.get('library', '')
        
        version_elem = ET.SubElement(vuln_elem, "version")
        version_elem.text = vuln.get('version_in_use', '')
        
        file_elem = ET.SubElement(vuln_elem, "file_location")
        file_elem.text = vuln.get('file_location', '')
        
        recommendation_elem = ET.SubElement(vuln_elem, "recommendation")
        recommendation_elem.text = vuln.get('upgrade_recommendation', {}).get('recommendation', '')
        
        vulns_elem = ET.SubElement(vuln_elem, "vulnerabilities")
        for vuln_detail in vuln.get('vulnerabilities', []):
            detail_elem = ET.SubElement(vulns_elem, "vulnerability_detail")
            
            severity_elem = ET.SubElement(detail_elem, "severity")
            severity_elem.text = vuln_detail.get('severity', '')
            
            summary_elem = ET.SubElement(detail_elem, "summary")
            summary_elem.text = vuln_detail.get('summary', '')
            
            osv_elem = ET.SubElement(detail_elem, "osv_id")
            osv_elem.text = vuln_detail.get('osv_id', '')
            
            cve_elem = ET.SubElement(detail_elem, "cve_ids")
            cve_elem.text = '; '.join(vuln_detail.get('cve_ids', []))
            
            published_elem = ET.SubElement(detail_elem, "published")
            published_elem.text = vuln_detail.get('published', '')
            
            fixed_elem = ET.SubElement(detail_elem, "fixed_in")
            fixed_elem.text = vuln_detail.get('fixed_in_branch', '')
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"📋 XML report saved to '{output_file}'")

def generate_access_links(generated_files):
    """Generate access links for the reports."""
    print(f"\n🔗 **Access Your Reports:**")
    print(f"📁 Reports saved in: {REPORTS_DIR}/")
    print(f"")
    
    for file in generated_files:
        file_path = file.split(" (")[0]  # Extract just the path
        file_name = os.path.basename(file_path)
        file_type = file.split("(")[1].split(")")[0] if "(" in file else "Unknown"
        
        # Create a simple access link
        access_link = f"file://{os.path.abspath(file_path)}"
        
        print(f"📄 {file_type.upper()}: {file_name}")
        print(f"   📂 Path: {file_path}")
        print(f"   🔗 Access: {access_link}")
        print(f"")
    
    print(f"💡 **Quick Access Tips:**")
    print(f"   • Open HTML files in your browser for beautiful reports")
    print(f"   • Import CSV files into Excel/Google Sheets for analysis")
    print(f"   • Use TXT files for email reports or plain text viewing")
    print(f"   • XML files are perfect for tool integration")
    print(f"   • JSON files contain complete data for programmatic access")
    print(f"")

def generate_specified_formats(vulnerability_results, output_formats):
    """Generate only specified output formats."""
    from datetime import datetime
    
    # Generate readable timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Extract repository name from vulnerability results for filename
    repo_name = "unknown"
    if vulnerability_results:
        # Get the first result to extract repo name
        first_result = vulnerability_results[0]
        file_location = first_result.get('file_location', '')
        if file_location:
            # Extract repo name from file path like /app/REPOSITORIES/repo-name/package.json
            if '/REPOSITORIES/' in file_location:
                repo_name = file_location.split('/REPOSITORIES/')[1].split('/')[0]
            elif 'REPOSITORIES/' in file_location:
                repo_name = file_location.split('REPOSITORIES/')[1].split('/')[0]
    
    generated_files = []
    
    if 'html' in output_formats or 'all' in output_formats:
        html_filename = f"vulnerability_report_{repo_name}_{timestamp}.html"
        generate_html_report(vulnerability_results, os.path.join(REPORTS_DIR, html_filename))
        generated_files.append(f"{REPORTS_DIR}/{html_filename} (HTML format)")
    
    if 'csv' in output_formats or 'all' in output_formats:
        csv_filename = f"vulnerability_report_{repo_name}_{timestamp}.csv"
        generate_csv_report(vulnerability_results, os.path.join(REPORTS_DIR, csv_filename))
        generated_files.append(f"{REPORTS_DIR}/{csv_filename} (CSV format)")
    
    if 'txt' in output_formats or 'all' in output_formats:
        txt_filename = f"vulnerability_report_{repo_name}_{timestamp}.txt"
        generate_txt_report(vulnerability_results, os.path.join(REPORTS_DIR, txt_filename))
        generated_files.append(f"{REPORTS_DIR}/{txt_filename} (TXT format)")
    
    if 'xml' in output_formats or 'all' in output_formats:
        xml_filename = f"vulnerability_report_{repo_name}_{timestamp}.xml"
        generate_xml_report(vulnerability_results, os.path.join(REPORTS_DIR, xml_filename))
        generated_files.append(f"{REPORTS_DIR}/{xml_filename} (XML format)")
    
    if 'json' in output_formats or 'all' in output_formats:
        json_filename = f"vulnerability_report_{repo_name}_{timestamp}.json"
        with open(os.path.join(REPORTS_DIR, json_filename), "w") as f:
            json.dump(vulnerability_results, f, indent=4)
        print(f"📄 JSON report saved to '{os.path.join(REPORTS_DIR, json_filename)}'")
        generated_files.append(f"{REPORTS_DIR}/{json_filename} (JSON format)")
    
    if generated_files:
        print(f"\n🎉 Report format(s) generated successfully!")
        print(f"📁 Files created:")
        for file in generated_files:
            print(f"   - {file}")
        
        # Generate access links
        generate_access_links(generated_files)
    else:
        print(f"\n⚠️  No valid output formats specified. Available formats: html,csv,txt,xml,json,all")

def generate_all_formats(vulnerability_results):
    """Generate all output formats (legacy function)."""
    generate_specified_formats(vulnerability_results, ['all'])

def main():
    """Main function to scan vulnerabilities."""
    parser = argparse.ArgumentParser(description='Scan vulnerabilities in dependencies')
    parser.add_argument('--repo', type=str, help='Specific repository to process (restricted to configured org)')
    parser.add_argument('--url', type=str, help='Direct repository URL (universal scope)')
    parser.add_argument('--repo-list', type=str, help='File containing list of repositories to process')
    parser.add_argument('--output', type=str, help='Output format(s): html,csv,txt,xml,json,all (default: json)')
    parser.add_argument('--output-dir', type=str, help='Output directory for reports (default: ./Results)')
    parser.add_argument('--one-time-scan', action='store_true', help='One-time scan: don\'t save cache or results')
    args = parser.parse_args()
    
    # Set output directory
    global REPORTS_DIR
    if args.output_dir:
        REPORTS_DIR = args.output_dir
        print(f"📁 Output directory set to: {REPORTS_DIR}")
    else:
        # Default to Results directory for organized output
        REPORTS_DIR = "Results"  # Default to Results directory
        print(f"📁 Output directory set to: {os.path.abspath(REPORTS_DIR)}")
    
    # Create reports directory if it doesn't exist
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    # For CLI tool, always process dependencies fresh
    print("🔄 CLI mode: Processing dependencies fresh")
    
    # Load configurations
    org, token = load_main_config()
    if not org or not token:
        print("❌ Could not load GitHub configuration. Exiting.")
        return
    
    files_to_find = load_dependency_config()
    if not files_to_find:
        print("❌ Could not load dependency configuration. Exiting.")
        return
    
    print(f"📄 Loaded {len(files_to_find)} dependency file patterns")
    
    # For CLI tool, always start fresh - no caching needed
    print("🔄 CLI mode: Starting fresh scan")
    existing_vulnerability_results = []
    
    # Determine repositories to process
    repos_to_process = []
    
    if args.repo:
        # Process specific repository
        repos_to_process = [args.repo]
        print(f"🔍 Processing specific repository: {args.repo}")
    elif args.url:
        # Process repository from URL
        try:
            # Use local parse_github_url function
            url_info = parse_github_url(args.url)
            repos_to_process = [url_info['repo_name']]
            # Set global variable for URL clone info
            global URL_CLONE_INFO
            URL_CLONE_INFO = url_info
            print(f"🔍 Processing repository from URL: {url_info['repo_name']}")
        except Exception as e:
            print(f"❌ Error parsing URL '{args.url}': {e}")
            return
    elif args.repo_list:
        # Process repositories from file
        try:
            with open(args.repo_list, 'r') as f:
                repos_to_process = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"🔍 Processing repositories from file: {repos_to_process}")
        except Exception as e:
            print(f"Error reading repo list file: {e}")
            return
    else:
        # Process all repositories in REPOSITORIES folder (only for non-one-time scans)
        if args.one_time_scan:
            # For one-time scans, get repositories from REPOSITORIES folder that were created by previous steps
            if os.path.exists(REPO_ROOT):
                for repo_name in os.listdir(REPO_ROOT):
                    repo_path = os.path.join(REPO_ROOT, repo_name)
                    if os.path.isdir(repo_path):
                        repos_to_process.append(repo_name)
                print(f"🔄 One-time scan: Found repositories in REPOSITORIES: {repos_to_process}")
            else:
                print("🔄 One-time scan: No REPOSITORIES folder found, will parse dependencies directly")
        else:
            # Normal mode: process repositories from REPOSITORIES folder
            if not os.path.exists(REPO_ROOT):
                print(f"❌ Repository directory '{REPO_ROOT}' does not exist. Run MTH_REPO_FETCHER.py first.")
                return
            
            for repo_name in os.listdir(REPO_ROOT):
                repo_path = os.path.join(REPO_ROOT, repo_name)
                if os.path.isdir(repo_path):
                    repos_to_process.append(repo_name)
            
            print(f"🔍 Processing all repositories: {repos_to_process}")
    
    if not repos_to_process and not args.one_time_scan:
        print("❌ No repositories found to process.")
        return
    
    # Process repositories (no hash checking needed for CLI)
    processed_repos = []
    
    for repo_name in repos_to_process:
        if process_repository(repo_name, files_to_find, org, token):
            processed_repos.append(repo_name)
    
    print(f"✅ Processed {len(processed_repos)} repositories: {processed_repos}")
    
    # Always parse dependencies fresh for CLI tool
    print(f"\n🔄 Parsing dependencies from repositories: {processed_repos}")
    
    # Import dependency parsing functions
    from MTH_DEPENDENCY_PARSER import parse_repository_dependencies
    
    # Load dependency config using local function
    dependency_config = load_dependency_config()
    
    # Parse dependencies from processed repositories
    libs = []
    for repo_name in processed_repos:
        repo_path = os.path.join(REPO_ROOT, repo_name)
        if os.path.exists(repo_path):
            repo_dependencies = parse_repository_dependencies(repo_path, repo_name, dependency_config)
            libs.extend(repo_dependencies)
    
    print(f"✅ Parsed {len(libs)} dependencies from repositories")
    
    if not libs:
        print("✅ No dependencies to scan from processed repositories.")
        return
    
    # Start fresh vulnerability results for CLI tool
    all_vulnerability_results = []
    print("🔄 CLI mode: Starting with fresh vulnerability results")
    
    with open("latest-version_parsers/parser_config.yaml") as f:
        parser_config = yaml.safe_load(f).get("latest-version_parsers", {})

    print("--- Hybrid Vulnerability Scan ---")
    
    queries, query_map = [], {}
    for lib in libs:
        eco = normalize_ecosystem(lib.get("ecosystem", ""))
        name, ver = lib.get("library"), lib.get("version")
        if name and ver and eco:
            q = {"version": ver, "package": {"name": name, "ecosystem": eco}}
            queries.append(q)
            query_map[(name, ver, eco)] = lib

    # Step 1: Discover vulnerabilities
    vuln_map, all_ids = {}, set()
    chunks = [queries[i:i+MAX_QUERIES_PER_BATCH] for i in range(0, len(queries), MAX_QUERIES_PER_BATCH)]
    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        fut_map = {ex.submit(fetch_vulns_for_chunk, c): c for c in chunks}
        for fut in tqdm(as_completed(fut_map), total=len(fut_map), desc="Discovering vulns"):
            for i, res in enumerate(fut.result().get("results", [])):
                if "vulns" in res:
                    q = fut_map[fut][i]
                    k = (q["package"]["name"], q["version"], q["package"]["ecosystem"])
                    vuln_map[k] = [v['id'] for v in res["vulns"]]
                    all_ids.update(v['id'] for v in res["vulns"])

    # Step 2: Enrich details
    details_map = {}
    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_vuln_details, oid): oid for oid in all_ids}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Fetching details"):
            res = fut.result(); details_map[res.get("id")] = res

    # Step 3: Get latest versions
    latest_map = {}
    uniq = {(k[0], k[2]) for k in vuln_map}
    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_latest_version, n, e, parser_config): n for n, e in uniq}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Fetching latest"):
            latest_map[futs[fut]] = fut.result()

    # Step 4: Check if latest versions are also vulnerable
    verify_map = {}
    to_check = [(n, latest_map[n], e) for (n, e) in uniq if latest_map.get(n)]
    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        futs = {ex.submit(check_version_vulnerabilities, n, v, e): n for n, v, e in to_check}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Verifying latest"):
            verify_map[futs[fut]] = fut.result()

    # Step 5: Report generation
    new_vulnerability_results, fp_count = [], 0
    for k, ids in tqdm(vuln_map.items(), desc="Generating report"):
        lib = query_map[k]; name = lib["library"]
        relevant = [details_map[i] for i in ids if not details_map.get(i, {}).get("error") and any(a.get("package", {}).get("name") == name for a in details_map[i].get("affected", []))]
        fp_count += len(ids) - len(relevant)
        if not relevant: continue

        safer_v = find_best_safer_version(lib['version'], relevant, name)
        latest_v = latest_map.get(name)
        latest_vuln = bool(verify_map.get(name))

        recommendation = "Manual review required."
        if safer_v:
            recommendation = f"Upgrade to minimal safer version ({safer_v})."
            try:
                if latest_v and Version(latest_v) > Version(safer_v):
                    recommendation = f"Upgrade to latest version ({latest_v})."
                    if latest_vuln:
                        recommendation += f" CAUTION: latest version has vulnerabilities."
            except InvalidVersion:
                recommendation += f" NOTE: latest version not comparable."

        new_vulnerability_results.append({
            "library": name, "version_in_use": lib["version"], "file_location": lib["file"],
            "upgrade_recommendation": {
                "minimal_safer_version": safer_v, "latest_version": latest_v,
                "latest_is_vulnerable": latest_vuln,
                "latest_version_vulns": verify_map.get(name, []),
                "recommendation": recommendation
            },
            "vulnerabilities": [
                {
                    "osv_id": v.get("id"),
                    "cve_ids": [c for c in v.get("aliases", []) if "CVE" in c],
                    "severity": extract_severity(v),
                    "summary": v.get("summary"),
                    "details": v.get("details"),
                    "fixed_in_branch": next((e['fixed'] for a in v.get("affected", []) for r in a.get("ranges", []) for e in r.get("events", []) if "fixed" in e), None),
                    "published": v.get("published"), "modified": v.get("modified")
                } for v in relevant
            ]
        })

    # Combine existing and new results
    all_vulnerability_results.extend(new_vulnerability_results)
    
    # Determine output formats
    output_formats = ['json']  # Default to JSON only
    if args.output:
        if args.output.lower() == 'all':
            output_formats = ['all']
        else:
            output_formats = [fmt.strip().lower() for fmt in args.output.split(',')]
            # Validate formats
            valid_formats = ['html', 'csv', 'txt', 'xml', 'json']
            output_formats = [fmt for fmt in output_formats if fmt in valid_formats]
            if not output_formats:
                print(f"⚠️  Invalid output format(s): {args.output}")
                print(f"   Valid formats: html,csv,txt,xml,json,all")
                output_formats = ['json']  # Fallback to JSON
    
    # Generate specified output formats
    generate_specified_formats(all_vulnerability_results, output_formats)
    
    if fp_count > 0:
        print(f"Filtered {fp_count} possible false positives.")
    
    if args.one_time_scan:
        print(f"🔄 One-time scan: Found {len(all_vulnerability_results)} vulnerabilities (not saved to cache)")
    else:
        print(f"📊 Total vulnerability results: {len(all_vulnerability_results)}")

if __name__ == "__main__":
    main()
