@echo off
echo 🔮 Setting up MTH Dementor CLI for Windows...

REM Check if Python 3 is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 is required but not installed. Please install Python 3 first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create virtual environment
echo 📦 Creating virtual environment...
python -m venv venv

REM Activate virtual environment and install dependencies
echo 📦 Installing dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

REM Create alias for easy access (Windows batch file)
echo 🔧 Creating Windows batch file for easy access...
echo @echo off > dementor-cli.bat
echo call venv\Scripts\activate >> dementor-cli.bat
echo python dementor-cli %%* >> dementor-cli.bat

echo ✅ Setup complete!
echo.
echo 🚀 You can now use the tool:
echo    dementor-cli.bat --help
echo    dementor-cli.bat --url https://github.com/octocat/Hello-World --output html
echo.
echo 📝 Don't forget to update your GitHub token in config/org_config.yaml if needed!
pause 