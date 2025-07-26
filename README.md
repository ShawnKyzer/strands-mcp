# Strands Agents MCP Server for Amazon Q

This project provides an MCP (Model Context Protocol) server that scrapes the Strands Agents documentation and indexes it in Elasticsearch, making it searchable for Amazon Q Developer.

## Architecture

- **Documentation Scraper**: Python script that crawls the Strands Agents documentation (v1.1.x)
- **Elasticsearch Index**: Stores scraped documentation with full-text search capabilities
- **MCP Server**: Provides Amazon Q with access to the indexed documentation
- **Docker Compose**: Orchestrates all services

## Components

1. `scraper/` - Documentation scraping logic
2. `mcp_server/` - MCP server implementation
3. `elasticsearch/` - Elasticsearch configuration
4. `docker-compose.yml` - Service orchestration

## Quick Start

```bash
# Build and start all services
docker-compose up --build

# The MCP server will be available on port 8000
# Elasticsearch will be available on port 9200
```

## Configuration

- Elasticsearch index: `strands-agents-docs`
- MCP server port: 8000
- Documentation source: https://strandsagents.com/latest/documentation/docs/

## Usage with Amazon Q

Configure Amazon Q to use this MCP server by adding the server endpoint to your MCP configuration. See `AMAZON_Q_INTEGRATION.md` for detailed instructions.

## Usage with Windsurf

Integrate with Windsurf IDE for enhanced development experience with Strands Agents documentation. See `WINDSURF_INTEGRATION.md` for setup instructions.

### Quick Windsurf Setup
```bash
# Copy the configuration file
cp windsurf-mcp-config.json ~/.windsurf/mcp-servers.json

# Restart Windsurf to load the MCP server
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper manually
ELASTICSEARCH_URL=http://localhost:9200 python scraper/main.py

# Run MCP server manually
ELASTICSEARCH_URL=http://localhost:9200 python mcp_server/main.py

# Run standalone (Python + Docker Elasticsearch)
python run_standalone.py

# Test the setup
python test_setup.py
```

## Integration Options

- **Amazon Q Developer** - See `AMAZON_Q_INTEGRATION.md`
- **Windsurf IDE** - See `WINDSURF_INTEGRATION.md`
- **Custom MCP Client** - Use the MCP server directly via stdio protocol
