#!/bin/bash

# Strands Agents MCP Server Startup Script

set -e

echo "🚀 Starting Strands Agents MCP Server for Amazon Q"
echo "=================================================="

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

echo "🔧 Building and starting services..."

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

# Run the scraper to index documentation
echo "🕷️  Running documentation scraper..."
$DOCKER_COMPOSE_CMD up --build scraper

# Check if scraping was successful
echo "🔍 Checking if documentation was indexed..."
sleep 5

# Start the MCP server
echo "🌐 Starting MCP server..."
$DOCKER_COMPOSE_CMD up -d --build mcp-server

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Service Status:"
echo "  - Elasticsearch: http://localhost:9200"
echo "  - MCP Server: Running in container 'strands-mcp-server'"
echo ""
echo "🧪 To test the setup, run:"
echo "  python test_setup.py"
echo ""
echo "📚 To view logs:"
echo "  docker-compose logs -f mcp-server"
echo "  docker-compose logs elasticsearch"
echo ""
echo "🛑 To stop all services:"
echo "  $DOCKER_COMPOSE_CMD down"
echo ""
echo "🔗 For Amazon Q integration instructions, see README.md"
