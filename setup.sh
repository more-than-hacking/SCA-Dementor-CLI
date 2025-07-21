#!/bin/bash

echo "🔮 Setting up MTH Dementor CLI..."

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $(pwd)"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Remove existing venv if it exists
if [ -d "venv" ]; then
    echo "🗑️ Removing existing virtual environment..."
    rm -rf venv
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Check if venv was created successfully
if [ ! -d "venv" ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment and install dependencies
echo "📦 Installing dependencies..."
source venv/bin/activate

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated: $VIRTUAL_ENV"

# Install dependencies
pip install -r requirements.txt

# Make dementor-cli executable
echo "🔧 Making dementor-cli executable..."
chmod +x dementor-cli

# Create alias for easy access (using absolute path)
echo "🔗 Creating alias for easy access..."
ALIAS_LINE="alias dementor-cli='$SCRIPT_DIR/dementor-cli'"

# Remove existing alias if it exists
if grep -q "alias dementor-cli=" ~/.zshrc; then
    sed -i '' '/alias dementor-cli=/d' ~/.zshrc
fi

# Add new alias
echo "$ALIAS_LINE" >> ~/.zshrc

echo "✅ Setup complete!"
echo ""
echo "🚀 You can now use the tool:"
echo "   ./dementor-cli --help"
echo "   dementor-cli --url https://github.com/octocat/Hello-World --output html"
echo ""
echo "📝 Don't forget to update your GitHub token in config/org_config.yaml if needed!"
echo ""
echo "💡 To start using immediately, run: source ~/.zshrc"
