#!/bin/bash
# Helper script for running hyperfocus-agent in Docker run environment

set -e

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

TEST_PROMPT='Are we in a docker container? Is there anything in here that would be different from a bare container?'

print_usage() {
    cat << EOF
Usage: $0 [command]

Commands:
    build       Build the Docker container
    run         Run the agent interactively in the container
    shell       Open a bash shell in the container
    dev         Run in development mode (live code editing)
    dev-shell   Open shell in dev container
    dev-prompt  Run dev container with custom prompt: $0 dev-prompt "Your prompt here"
    clean       Remove container and volumes
    rebuild     Clean, build, and run
    logs        Show container logs

    phoenix-start   Start Phoenix observability server (UI on port 6006)
    phoenix-stop    Stop Phoenix server
    phoenix-logs    Show Phoenix server logs

    assets-start    Start the asset server (serves test files on port 8080)
    assets-stop     Stop the asset server
    assets-logs     Show asset server logs

    crawl4ai-start  Start the Crawl4AI service (web scraping on port 11235)
    crawl4ai-stop   Stop the Crawl4AI service
    crawl4ai-logs   Show Crawl4AI service logs

Examples:
    $0 build                    # Build the container
    $0 run                      # Run the agent
    $0 dev                      # Run in dev mode (live editing)
    $0 shell                    # Interactive shell for manual testing
    $0 clean                    # Clean up everything
    $0 phoenix-start            # Start Phoenix observability UI
    $0 assets-start             # Start HTTP server for test assets

Modes:
    test        Isolated testing with read-only source (production-like)
    dev         Active development with live code editing (no rebuilds needed)

Environment variables can be overridden in docker-compose.yml
EOF
}

build_container() {
    echo -e "${GREEN}Building test container...${NC}"
    docker compose build
    echo -e "${GREEN}Build complete!${NC}"
}

run_agent() {
    echo -e "${GREEN}Running hyperfocus-agent in test container...${NC}"
    echo -e "${YELLOW}Agent will execute in isolated environment at /workspace/test_area${NC}"
    docker compose run --rm --service-ports hyperfocus-test /bin/bash -c "hyperfocus '${TEST_PROMPT}'"
}

open_shell() {
    echo -e "${GREEN}Opening shell in test container...${NC}"
    echo -e "${YELLOW}Working directory: /workspace/test_area${NC}"
    echo -e "${YELLOW}Test fixtures available at: /workspace/fixtures${NC}"
    docker compose run --rm --service-ports hyperfocus-test /bin/bash
}

clean_environment() {
    echo -e "${YELLOW}Cleaning up Docker environment...${NC}"
    docker compose down -v
    echo -e "${GREEN}Cleanup complete!${NC}"
}

rebuild_all() {
    clean_environment
    build_container
    echo -e "${GREEN}Ready to run tests!${NC}"
}

show_logs() {
    docker compose logs -f
}

run_dev() {
    echo -e "${GREEN}Running hyperfocus-agent in DEV mode...${NC}"
    echo -e "${YELLOW}Source code changes will reflect immediately (no rebuild needed)${NC}"
    echo -e "${YELLOW}Edit files in ./src/ and they'll update live in the container${NC}"
    docker compose run --rm --service-ports hyperfocus-dev hyperfocus "${TEST_PROMPT}"
}

open_dev_shell() {
    echo -e "${GREEN}Opening shell in DEV container...${NC}"
    echo -e "${YELLOW}Source is mounted read-write at /app/src${NC}"
    echo -e "${YELLOW}Working directory: /app${NC}"
    echo -e "${YELLOW}Note: Package is installed in editable mode on startup${NC}"
    docker compose run --rm --service-ports hyperfocus-dev bash
}

run_dev_prompt() {
    echo -e "${GREEN}Running hyperfocus-agent in DEV mode...${NC}"
    docker compose run --rm --service-ports hyperfocus-dev hyperfocus "${2}"
}

build_dev() {
    echo -e "${GREEN}Building dev container...${NC}"
    docker compose build hyperfocus-dev
    echo -e "${GREEN}Dev build complete!${NC}"
}

start_asset_server() {
    echo -e "${GREEN}Starting asset server...${NC}"
    echo -e "${YELLOW}Test files will be available at http://asset-server:8080${NC}"
    docker compose up -d asset-server
    echo -e "${GREEN}Asset server started!${NC}"
    echo -e "${YELLOW}Available files:${NC}"
    echo "  - http://asset-server:8080/example.txt"
    echo "  - http://asset-server:8080/data.json"
    echo "  - http://asset-server:8080/onirism.jpg"
}

stop_asset_server() {
    echo -e "${YELLOW}Stopping asset server...${NC}"
    docker compose stop asset-server
    docker compose rm -f asset-server
    echo -e "${GREEN}Asset server stopped!${NC}"
}

show_asset_logs() {
    echo -e "${GREEN}Showing asset server logs...${NC}"
    docker compose logs -f asset-server
}

start_crawl4ai() {
    echo -e "${GREEN}Starting Crawl4AI service...${NC}"
    echo -e "${YELLOW}Service will be reachable at http://localhost:11235 (container name: crawl4ai)${NC}"
    docker compose up -d crawl4ai
    echo -e "${GREEN}Crawl4AI service started!${NC}"
}

stop_crawl4ai() {
    echo -e "${YELLOW}Stopping Crawl4AI service...${NC}"
    docker compose stop crawl4ai
    docker compose rm -f crawl4ai
    echo -e "${GREEN}Crawl4AI service stopped!${NC}"
}

show_crawl4ai_logs() {
    echo -e "${GREEN}Showing Crawl4AI service logs...${NC}"
    docker compose logs -f crawl4ai
}

start_phoenix() {
    echo -e "${GREEN}Starting Phoenix observability server...${NC}"
    echo -e "${YELLOW}Phoenix UI will be available at http://localhost:6006${NC}"
    docker compose up -d phoenix
    echo -e "${GREEN}Phoenix server started!${NC}"
    echo -e "${YELLOW}Waiting for Phoenix to be ready...${NC}"
    sleep 3
    echo -e "${GREEN}Phoenix is ready at http://localhost:6006${NC}"
}

stop_phoenix() {
    echo -e "${YELLOW}Stopping Phoenix server...${NC}"
    docker compose stop phoenix
    docker compose rm -f phoenix
    echo -e "${GREEN}Phoenix server stopped!${NC}"
}

show_phoenix_logs() {
    echo -e "${GREEN}Showing Phoenix server logs...${NC}"
    docker compose logs -f phoenix
}

# Main command handling
case "${1:-}" in
    build)
        build_container
        ;;
    run)
        run_agent
        ;;
    shell)
        open_shell
        ;;
    dev)
        run_dev
        ;;
    dev-shell)
        open_dev_shell
        ;;
    dev-build)
        build_dev
        ;;
    dev-prompt)
        run_dev_prompt "$@"
        ;;
    clean)
        clean_environment
        ;;
    rebuild)
        rebuild_all
        ;;
    logs)
        show_logs
        ;;
    assets-start)
        start_asset_server
        ;;
    assets-stop)
        stop_asset_server
        ;;
    assets-logs)
        show_asset_logs
        ;;
    crawl4ai-start)
        start_crawl4ai
        ;;
    crawl4ai-stop)
        stop_crawl4ai
        ;;
    crawl4ai-logs)
        show_crawl4ai_logs
        ;;
    phoenix-start)
        start_phoenix
        ;;
    phoenix-stop)
        stop_phoenix
        ;;
    phoenix-logs)
        show_phoenix_logs
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo -e "${RED}Error: Unknown command '${1:-}'${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac
