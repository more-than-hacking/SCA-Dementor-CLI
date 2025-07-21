# MTH Dementor CLI - Windows PowerShell Setup Script

Write-Host "🔮 Setting up MTH Dementor CLI for Windows..." -ForegroundColor Cyan

# Check if Python 3 is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python 3 is required but not installed. Please install Python 3 first." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment
Write-Host "📦 Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

# Activate virtual environment and install dependencies
Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"
pip install -r requirements.txt

# Create PowerShell alias for easy access
Write-Host "🔧 Creating PowerShell function for easy access..." -ForegroundColor Cyan
$functionContent = @"
function dementor-cli {
    & ".\venv\Scripts\Activate.ps1"
    python dementor-cli `$args
}
"@

$functionContent | Out-File -FilePath "dementor-cli.ps1" -Encoding UTF8

Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 You can now use the tool:" -ForegroundColor Cyan
Write-Host "   .\dementor-cli.ps1" -ForegroundColor Yellow
Write-Host "   dementor-cli --url https://github.com/octocat/Hello-World --output html" -ForegroundColor Yellow
Write-Host ""
Write-Host "📝 Don't forget to update your GitHub token in config/org_config.yaml if needed!" -ForegroundColor Yellow
Read-Host "Press Enter to continue" 