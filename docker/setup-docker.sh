#!/bin/bash

# MTH Dementor CLI - Docker Setup Script
# Quick setup for Docker usage

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  MTH Dementor CLI - Docker Setup${NC}"
echo -e "${BLUE}================================${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo -e "${GREEN}✅ Docker is available${NC}"

# Make the run script executable
chmod +x run-docker.sh

# Build the Docker image
echo "🔨 Building Docker image..."
./run-docker.sh build

echo ""
echo -e "${GREEN}✅ Docker setup complete!${NC}"
echo ""
echo "🚀 Usage Examples:"
echo "  ./run-docker.sh run --url https://github.com/octocat/Hello-World --output html"
echo "  ./run-docker.sh run --repo your-org/your-repo --output html"
echo "  ./run-docker.sh run --folderpath /path/to/project --output html"
echo "  ./run-docker.sh shell"
echo ""
echo "📖 For more options: ./run-docker.sh help" 