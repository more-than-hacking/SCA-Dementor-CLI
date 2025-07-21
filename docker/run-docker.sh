#!/bin/bash

# MTH Dementor CLI - Docker Runner Script
# This script handles all Docker mounting issues and provides easy usage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    echo -e "${BLUE}  MTH Dementor CLI - Docker${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to show usage
show_usage() {
    print_header
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build                    Build the Docker image"
    echo "  run [dementor-args]      Run dementor with arguments"
    echo "  shell                    Start interactive shell"
    echo "  clean                    Clean up Docker resources"
    echo "  logs                     Show container logs"
    echo "  status                   Show container status"
    echo ""
    echo "Examples:"
    echo "  $0 build"
    echo "  $0 run --url https://github.com/octocat/Hello-World --output html"
    echo "  $0 run --repo your-org/your-repo --output html"
    echo "  $0 run --folderpath /path/to/project --output html"
    echo "  $0 shell"
    echo ""
    echo "Docker Features:"
    echo "  ✅ Automatic volume mounting"
    echo "  ✅ Persistent results storage"
    echo "  ✅ Git cache optimization"
    echo "  ✅ Cross-platform compatibility"
    echo ""
}

# Function to build Docker image
build_image() {
    print_status "Building MTH Dementor CLI Docker image..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Build the image from parent directory
    docker build -t mth-dementor-cli -f Dockerfile ..
    
    if [ $? -eq 0 ]; then
        print_status "✅ Docker image built successfully!"
    else
        print_error "❌ Failed to build Docker image"
        exit 1
    fi
}

# Function to run dementor with arguments
run_dementor() {
    print_status "Running MTH Dementor CLI with Docker..."
    print_status "Arguments: $*"
    
    # Create necessary directories if they don't exist
    mkdir -p ../reports ../REPOSITORIES
    
    # Run the container with proper volume mounting
    docker run --rm \
        -v "$(pwd)/..:/app" \
        -v "$(pwd)/../reports:/app/reports" \
        -v "$(pwd)/../REPOSITORIES:/app/REPOSITORIES" \
        -v "$(pwd)/../config:/app/config" \
        -v "$(pwd)/../core:/app/core" \
        -v "$(pwd)/../parsers:/app/parsers" \
        -v "$(pwd)/../utils:/app/utils" \
        -w /app \
        --name mth-dementor-run \
        mth-dementor-cli \
        "$@"
    
    if [ $? -eq 0 ]; then
        print_status "✅ Dementor completed successfully!"
        print_status "📁 Check the reports directory for output files"
    else
        print_error "❌ Dementor failed"
        exit 1
    fi
}

# Function to start interactive shell
start_shell() {
    print_status "Starting interactive Docker shell..."
    
    docker run --rm -it \
        -v "$(pwd)/..:/app" \
        -v "$(pwd)/../reports:/app/reports" \
        -v "$(pwd)/../REPOSITORIES:/app/REPOSITORIES" \
        -v "$(pwd)/../config:/app/config" \
        -v "$(pwd)/../core:/app/core" \
        -v "$(pwd)/../parsers:/app/parsers" \
        -v "$(pwd)/../utils:/app/utils" \
        -w /app \
        --name mth-dementor-shell \
        mth-dementor-cli \
        /bin/bash
}

# Function to clean up Docker resources
clean_docker() {
    print_status "Cleaning up Docker resources..."
    
    # Stop and remove containers
    docker stop mth-dementor-run mth-dementor-shell 2>/dev/null || true
    docker rm mth-dementor-run mth-dementor-shell 2>/dev/null || true
    
    # Remove unused images
    docker image prune -f
    
    print_status "✅ Docker cleanup completed!"
}

# Function to show logs
show_logs() {
    print_status "Showing container logs..."
    docker logs mth-dementor-run 2>/dev/null || docker logs mth-dementor-shell 2>/dev/null || print_warning "No running containers found"
}

# Function to show status
show_status() {
    print_status "Docker container status:"
    docker ps -a --filter "name=mth-dementor" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Main script logic
main() {
    case "${1:-}" in
        "build")
            build_image
            ;;
        "run")
            shift
            if [ $# -eq 0 ]; then
                print_error "No arguments provided for run command"
                show_usage
                exit 1
            fi
            run_dementor "$@"
            ;;
        "shell")
            start_shell
            ;;
        "clean")
            clean_docker
            ;;
        "logs")
            show_logs
            ;;
        "status")
            show_status
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 