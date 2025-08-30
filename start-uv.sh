#!/bin/bash

# Strands Agents MCP Server Startup Script (UV Version)

set -e

echo "🚀 Starting Strands Agents MCP Server with UV"
echo "=============================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if Docker and Docker Compose are available
DOCKER_CMD="docker"
if ! command -v docker &> /dev/null; then
    # Try alternative Docker locations
    if [ -f "/usr/local/bin/docker" ]; then
        DOCKER_CMD="/usr/local/bin/docker"
        echo "📍 Found Docker at /usr/local/bin/docker"
    else
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi
fi

DOCKER_COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    # Try docker compose (newer syntax)
    if $DOCKER_CMD compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="$DOCKER_CMD compose"
        echo "📍 Using 'docker compose' instead of 'docker-compose'"
    else
        echo "❌ Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
fi

# Create logs directory
mkdir -p logs

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env file from .env.example"
fi

# Install/sync dependencies with uv
echo "📦 Installing dependencies with uv..."
uv sync

echo "🔧 Building and starting services..."

# Clean up any existing Docker resources to avoid network conflicts
echo "🧹 Cleaning up existing Docker resources..."
$DOCKER_COMPOSE_CMD down --remove-orphans 2>/dev/null || true
$DOCKER_CMD network prune -f 2>/dev/null || true

# Start Elasticsearch first
echo "📊 Starting Elasticsearch..."
$DOCKER_COMPOSE_CMD up -d elasticsearch

# Wait for Elasticsearch to be ready
echo "⏳ Waiting for Elasticsearch to be ready..."
sleep 10

# Check Elasticsearch health
for i in {1..30}; do
    if curl -s http://localhost:9200/_health &> /dev/null; then
        echo "✅ Elasticsearch is ready!"
        break
    fi
    echo "   Waiting for Elasticsearch... ($i/30)"
    sleep 2
done

# Run the scraper to index documentation using uv
echo "🕷️  Running documentation scraper with uv..."
uv run scraper

# Check if scraping was successful
echo "🔍 Checking if documentation was indexed..."
sleep 5

# Start the MCP server using uv
echo "🌐 Starting MCP server with uv..."
uv run mcp-server &
MCP_PID=$!

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Service Status:"
echo "  - Elasticsearch: http://localhost:9200"
echo "  - MCP Server: Running with PID $MCP_PID"
echo ""
echo "🧪 To test the setup, run:"
echo "  uv run python test_setup.py"
echo ""
echo "📚 To view logs:"
echo "  Check the console output above"
echo "  $DOCKER_COMPOSE_CMD logs elasticsearch"
echo ""
echo "🛑 To stop all services:"
echo "  kill $MCP_PID"
echo "  $DOCKER_COMPOSE_CMD down"
echo ""
echo "🔗 For Amazon Q integration instructions, see README.md"
echo ""
echo "💡 UV Commands:"
echo "  uv sync                    # Install/update dependencies"
echo "  uv run scraper            # Run scraper directly"
echo "  uv run mcp-server         # Run MCP server directly"
echo "  uv add <package>          # Add new dependency"
echo "  uv remove <package>       # Remove dependency"
