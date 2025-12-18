#!/bin/bash
# run_tests.sh - Convenient script for running tests in Docker

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get container name (adjust this to match your container)
CONTAINER_NAME=${CONTAINER_NAME:-"fastapi-test-runner"}

echo -e "${BLUE}FastAPI Test Runner${NC}"
echo "================================"

# Function to run tests in container
run_test() {
    echo -e "${GREEN}Running tests in container: $CONTAINER_NAME${NC}"
    docker exec -it $CONTAINER_NAME pytest tests/ "$@"
}

# Function to run with coverage
run_with_coverage() {
    echo -e "${GREEN}Running tests with coverage...${NC}"
    docker exec -it $CONTAINER_NAME pytest tests/ -v --cov=app --cov-report=html --cov-report=term
    echo -e "${GREEN}Copying coverage report...${NC}"
    docker cp $CONTAINER_NAME:/app/htmlcov ./htmlcov
    echo -e "${GREEN}Coverage report saved to ./htmlcov/index.html${NC}"
}

# Function to run specific test file
run_file() {
    echo -e "${GREEN}Running test file: $1${NC}"
    docker exec -it $CONTAINER_NAME pytest tests/$1 -v
}

# Function to run specific test
run_specific() {
    echo -e "${GREEN}Running specific test: $1${NC}"
    docker exec -it $CONTAINER_NAME pytest tests/$1 -v
}

# Check if container is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}Error: Container '$CONTAINER_NAME' is not running${NC}"
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    echo ""
    echo "Please set CONTAINER_NAME environment variable:"
    echo "export CONTAINER_NAME=your-container-name"
    exit 1
fi

# Parse command line arguments
case "${1}" in
    "")
        # No arguments - run all tests
        run_test -v
        ;;
    "coverage")
        # Run with coverage
        run_with_coverage
        ;;
    "auth")
        # Run auth tests
        run_file "test_auth.py"
        ;;
    "edge")
        # Run edge case tests
        run_file "test_auth_edge_cases.py"
        ;;
    "watch")
        # Run in watch mode
        echo -e "${GREEN}Running in watch mode (Ctrl+C to exit)...${NC}"
        docker exec -it $CONTAINER_NAME ptw tests/ --runner "pytest -v"
        ;;
    "clean")
        # Clean test database
        echo -e "${GREEN}Cleaning test database...${NC}"
        docker exec -it $CONTAINER_NAME rm -f test_app.db
        echo -e "${GREEN}Test database cleaned${NC}"
        ;;
    "shell")
        # Open shell in container
        echo -e "${GREEN}Opening shell in container...${NC}"
        docker exec -it $CONTAINER_NAME bash
        ;;
    "logs")
        # Show container logs
        docker logs $CONTAINER_NAME --tail 50 -f
        ;;
    *)
        # Custom test path
        if [[ $1 == *.py ]]; then
            run_file "$1"
        else
            run_specific "$1"
        fi
        ;;
esac

echo -e "${GREEN}Done!${NC}"
