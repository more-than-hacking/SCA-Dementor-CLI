# 🔮 MTH Dementor CLI (SCA Tool)

**Your Security Companion - Complete dependency scanning & vulnerability analysis pipeline**

A powerful CLI tool for scanning GitHub repositories and local projects for security vulnerabilities in dependencies.

## 🚀 Quick Start

**After cloning the repository:**

### 🎯 Super Quick Start (No Configuration Needed!)
```bash
# Clone the repository
git clone https://github.com/your-username/SCA-Dementor-CLI
cd SCA-Dementor-CLI

# Run setup
./setup.sh

# Scan any repository immediately (no config needed!)
dementor-cli --url https://github.com/octocat/Hello-World --output html

# Scan private repository with embedded token
dementor-cli --url https://ghp_YOUR_TOKEN_HERE@github.com/your-org/private-repo --output html
```

**That's it! No configuration files needed for one-off scans.** 🎉

### Option 1: Native Mode (Recommended for Development)

**macOS/Linux:**
```bash
# Navigate to the project directory
cd SCA-Dementor-CLI

# Run the setup script
./setup.sh

# Start scanning!
dementor-cli --url https://github.com/octocat/Hello-World --output html
```

**Windows:**
```cmd
# Navigate to the project directory
cd SCA-Dementor-CLI

# Run the Windows setup script
setup-windows.bat

# Start scanning!
dementor-cli.bat --url https://github.com/octocat/Hello-World --output html
```

**Windows PowerShell:**
```powershell
# Navigate to the project directory
cd SCA-Dementor-CLI

# Run the PowerShell setup script
.\setup-windows.ps1

# Start scanning!
.\dementor-cli.ps1 --url https://github.com/octocat/Hello-World --output html
```

### Option 2: Docker Mode (Recommended for Production)
```bash
# Navigate to the project directory
cd SCA-Dementor-CLI

# Run the Docker setup script
./setup-docker.sh

# Start scanning!
./dementor-docker --url https://github.com/octocat/Hello-World --output html
```

### Option 3: Manual Native Setup
```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Make executable
chmod +x dementor-cli
```

## 📋 Prerequisites

### For Native Mode
- Python 3.7+
- Git
- GitHub Personal Access Token (for private repos)

### For Docker Mode
- Docker installed and running
- Git
- GitHub Personal Access Token (for private repos)
- 4GB+ RAM available for Docker

## ⚙️ Configuration

### Option 1: Direct URL with Token (Recommended)
You can include your GitHub Personal Access Token directly in the URL, eliminating the need for config files:

```bash
# Public repository (no token needed)
dementor-cli --url https://github.com/octocat/Hello-World --output html

# Private repository with embedded token
dementor-cli --url https://ghp_YOUR_TOKEN_HERE@github.com/your-org/private-repo --output html

# Example with actual token format
dementor-cli --url https://ghp_abc123def456@github.com/your-org/private-repo --output html
```

**Benefits:**
- ✅ **No config files needed** for one-off scans
- ✅ **Secure**: Token only used for specific scan
- ✅ **Flexible**: Works with any GitHub repository
- ✅ **Universal**: No organization restrictions

### Option 2: Configuration File
For repeated scans of the same organization, update your GitHub token in `config/org_config.yaml`:

```yaml
github:
  org_name: your-org-name
  token: your-github-token
```

Then use the `--repo` flag:
```bash
dementor-cli --repo your-org/repo-name --output html
```

## 🐳 Docker Setup

### Quick Docker Setup
```bash
# Run the Docker setup script
./setup-docker.sh
```

### Manual Docker Setup
```bash
# Navigate to docker directory
cd docker

# Build the image
./run-docker.sh build

# Run with Docker
./run-docker.sh run --url https://github.com/octocat/Hello-World --output html
```

### Docker Features
- ✅ **Automatic Volume Mounting**: All files and reports are accessible from host
- ✅ **Persistent Storage**: Reports saved to local filesystem
- ✅ **Cross-Platform**: Works on macOS, Linux, and Windows
- ✅ **Isolated Environment**: No conflicts with system dependencies
- ✅ **Easy Management**: Simple commands for building, running, and cleanup

### Docker Commands
```bash
# Run dementor with Docker
./dementor-docker --url https://github.com/octocat/Hello-World --output html

# Interactive shell
cd docker && ./run-docker.sh shell

# Clean up resources
cd docker && ./run-docker.sh clean

# Check status
cd docker && ./run-docker.sh status
```

## 🎯 Usage Examples

### Scan Any GitHub Repository
```bash
# Public repository (no token needed)
dementor-cli --url https://github.com/octocat/Hello-World --output html

# Private repository with embedded token
dementor-cli --url https://ghp_YOUR_TOKEN_HERE@github.com/your-org/private-repo --output html

# Docker mode
./dementor-docker --url https://github.com/octocat/Hello-World --output html

# Docker with private repo
./dementor-docker --url https://ghp_YOUR_TOKEN_HERE@github.com/your-org/private-repo --output html
```

### Scan Repository from Configured Organization
```bash
# Native mode
dementor-cli --repo your-org/repo-name --output html

# Docker mode
./dementor-docker --repo your-org/repo-name --output html
```

### Scan Local Project
```bash
# Native mode
dementor-cli --folderpath /path/to/your/project --output html

# Docker mode
./dementor-docker --folderpath /path/to/your/project --output html
```

### Full Organization Scan
```bash
# Native mode
dementor-cli --full-repo-scan --output html

# Docker mode
./dementor-docker --full-repo-scan --output html
```

### Multiple Output Formats
```bash
# Generate all formats
dementor-cli --url https://github.com/octocat/Hello-World --output all

# Specific formats
dementor-cli --url https://github.com/octocat/Hello-World --output html,csv,json
```

### Custom Output Directory
```bash
# Native mode
dementor-cli --url https://github.com/octocat/Hello-World --output html --output-dir ~/Documents/Results

# Docker mode
./dementor-docker --url https://github.com/octocat/Hello-World --output html --output-dir ~/Documents/Results
```

### Pipeline Control
```bash
# Only fetch repositories
dementor-cli --url https://github.com/octocat/Hello-World --fetch-only

# Only parse dependencies
dementor-cli --url https://github.com/octocat/Hello-World --parse-only

# Only scan vulnerabilities
dementor-cli --url https://github.com/octocat/Hello-World --scan-only
```

## 📊 Output Formats

- **HTML**: Beautiful web report with charts and details
- **CSV**: Spreadsheet-friendly format
- **JSON**: Machine-readable format
- **TXT**: Simple text report
- **XML**: Structured XML format
- **ALL**: Generate all formats at once

## 🔧 Available Options

```bash
dementor-cli --help
```

### Repository Options
- `--url <github-url>`: Direct repository URL (universal scope)
- `--repo <org/repo>`: Repository from configured org
- `--repo-list <file>`: List of repositories from file
- `--folderpath <path>`: Local folder to scan
- `--full-repo-scan`: Scan all repos in organization

### Output Options
- `--output <format>`: Output format(s): html,csv,txt,xml,json,all
- `--output-dir <path>`: Output directory for reports (default: ./Results)

### Pipeline Control
- `--fetch-only`: Only fetch repositories
- `--parse-only`: Only parse dependencies
- `--scan-only`: Only scan vulnerabilities
- `--skip-dependency-parser`: Skip dependency parsing
- `--skip-sca`: Skip vulnerability scanning
- `--workers <number>`: Number of worker threads (default: 5)

## 🏗️ Architecture

The tool follows a modular pipeline:

1. **Repository Fetcher** (`MTH_REPO_FETCHER.py`): Clones repositories
2. **Dependency Parser** (`MTH_DEPENDENCY_PARSER.py`): Extracts dependencies
3. **SCA Scanner** (`MTH_SCA_SCANNER.py`): Scans for vulnerabilities

## 🔍 Supported Languages

- **Python**: requirements.txt, setup.py, pyproject.toml, Pipfile
- **Node.js**: package.json, package-lock.json, yarn.lock
- **Java**: pom.xml, build.gradle, build.gradle.kts
- **Go**: go.mod, go.sum
- **TypeScript**: package.json, tsconfig.json
- **And more...**

## 🎯 Features

✅ **Universal Scope**: Scan any GitHub repository with `--url`  
✅ **Zero Configuration**: Use embedded tokens in URLs (no config files needed)  
✅ **Restricted Scope**: Scan only configured org with `--repo`  
✅ **Local Scanning**: Scan local projects with `--folderpath`  
✅ **Multiple Formats**: HTML, CSV, JSON, TXT, XML output  
✅ **CI/CD Ready**: Perfect for automation pipelines  
✅ **No Server**: Pure CLI tool, no web interface needed  
✅ **Cross-Platform**: Works on macOS, Linux, and Windows  
✅ **Docker Support**: Complete containerization  
✅ **Latest Version Parsers**: Fetch up-to-date dependency information  

## 🚀 Production Ready

- ✅ Clean CLI interface
- ✅ Comprehensive error handling
- ✅ Progress indicators
- ✅ Detailed logging
- ✅ Multiple output formats
- ✅ Configurable scanning options
- ✅ Docker containerization
- ✅ Windows support

## 🐳 Docker Architecture

```
Host System                    Docker Container
┌─────────────────┐           ┌─────────────────┐
│                 │           │                 │
│  Results/       │◄─────────┤  /app/Results   │
│  REPOSITORIES/  │◄─────────┤  /app/REPOSITORIES │
│  config/        │◄─────────┤  /app/config    │
│  core/          │◄─────────┤  /app/core      │
│  parsers/       │◄─────────┤  /app/parsers   │
│  utils/         │◄─────────┤  /app/utils     │
│                 │           │                 │
└─────────────────┘           └─────────────────┘
```

## 🔧 Troubleshooting

### Common Issues

**Permission Denied:**
```bash
chmod +x dementor-cli
chmod +x dementor-docker
```

**Docker Not Running:**
```bash
# Start Docker Desktop
# Or on Linux:
sudo systemctl start docker
```

**Python Not Found:**
```bash
# Install Python 3.7+
# macOS: brew install python3
# Ubuntu: sudo apt install python3
```

**Virtual Environment Issues:**
```bash
# Remove and recreate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Token Security:**
```bash
# Use embedded tokens for one-off scans (more secure)
dementor-cli --url https://ghp_YOUR_TOKEN@github.com/org/repo --output html

# Avoid storing tokens in config files for temporary scans
# The tool automatically hides tokens in logs for security
```

## 📝 License

By MTH - More Than Hacking

---

**Ready to secure your codebase? Run `dementor-cli --help` to get started!** 🛡️ 