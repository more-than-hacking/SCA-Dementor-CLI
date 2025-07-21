#!/bin/bash

# MTH Dementor CLI - Complete Docker Setup
# This script sets up everything needed for Docker usage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  MTH Dementor CLI - Docker Setup${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_header

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

print_status "✅ Docker is available"

# Make scripts executable
print_status "Setting up scripts..."
chmod +x dementor-docker
chmod +x docker/run-docker.sh
chmod +x docker/setup-docker.sh

# Build the Docker image
print_status "Building Docker image..."
cd docker
./run-docker.sh build
cd ..

if [ $? -eq 0 ]; then
    print_status "✅ Docker setup complete!"
    echo ""
    echo "🚀 Usage Examples:"
    echo ""
    echo "🐳 Docker Mode (Recommended for isolation):"
echo "  ./dementor-docker --url https://github.com/octocat/Hello-World --output html"
echo "  ./dementor-docker --repo your-org/your-repo --output html"
echo "  ./dementor-docker --folderpath /path/to/project --output html"
echo ""
echo "⚡ Native Mode (Faster execution):"
echo "  ./dementor-cli --url https://github.com/octocat/Hello-World --output html"
echo "  ./dementor-cli --repo your-org/your-repo --output html"
echo "  ./dementor-cli --folderpath /path/to/project --output html"
echo ""
echo "📖 For more options:"
echo "  ./dementor-docker --help"
echo "  ./dementor-cli --help"
    echo ""
    echo "🔧 Docker Management:"
    echo "  cd docker && ./run-docker.sh shell    # Interactive shell"
    echo "  cd docker && ./run-docker.sh clean    # Clean up resources"
    echo "  cd docker && ./run-docker.sh status   # Check status"
else
    print_error "❌ Docker setup failed"
    exit 1
fi 