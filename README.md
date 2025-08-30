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

### Option 1: Using UV (Recommended)

This project now supports [UV](https://github.com/astral-sh/uv) for fast Python package management:

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Quick start with UV
./start-uv.sh

# Or run standalone with UV (no Docker for scraper/MCP server)
./run_standalone_uv.py
```

**UV Commands:**
```bash
uv sync                    # Install/update dependencies
uv run scraper            # Run scraper directly
uv run mcp-server         # Run MCP server directly
uv add <package>          # Add new dependency
uv remove <package>       # Remove dependency
```

### Option 2: Using Pre-indexed Data (Docker)

The `docker/` directory contains a Docker Compose setup with pre-indexed Strands documentation:

```bash
# Navigate to the docker directory
cd docker/

# Start all services (Elasticsearch, Kibana, and data restoration)
docker-compose up -d

# Wait for services to start (about 30-60 seconds)
# Check status
docker-compose ps

# Elasticsearch will be available on port 9200
# Kibana GUI will be available on port 5601
```

This setup includes:
- **Elasticsearch** with pre-indexed Strands documentation
- **Kibana** for data visualization and exploration
- **Automatic data restoration** from `es-data.tar.gz`

### Option 3: Traditional Setup (Root Directory)

For a fresh setup without pre-indexed data using traditional Python:

```bash
# Start Elasticsearch and Kibana (from root directory)
docker-compose up -d

# Then run the scraper to index documentation
python scraper/main.py
```

## Running the Scraper Locally

### Using pip
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run the scraper to index documentation
python scraper/main.py
```

### Using uv
```bash
# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium

# Run the scraper to index documentation
uv run python scraper/main.py
```

## Running the MCP Server Locally

```bash
# Run the MCP server
python mcp_server/main.py

# The MCP server will be available on port 8000
```

## Configuration

- Elasticsearch index: `strands-agents-docs`
- MCP server port: 8000
- Kibana GUI port: 5601
- Documentation source: https://strandsagents.com/latest/documentation/docs/

## Viewing Data with Kibana

Kibana provides a web-based GUI for exploring and visualizing your Elasticsearch data:

1. **Access Kibana**: Open http://localhost:5601 in your browser (no login required)
2. **Create Index Pattern**: 
   - Go to Stack Management → Index Patterns
   - Create a new index pattern with `strands-agents-docs`
   - Select `@timestamp` as the time field if available
3. **Explore Data**:
   - Use **Discover** to browse and search through scraped documentation
   - Use **Dashboard** to create visualizations of your data
   - Use **Dev Tools** to run Elasticsearch queries directly

### Quick Data Exploration

- **Discover Tab**: View all indexed documents with full-text search
- **Search**: Use the search bar to find specific documentation content
- **Filters**: Apply filters to narrow down results by fields
- **Time Range**: Adjust time range to see when documents were indexed

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

### Using pip
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

### Using uv
```bash
# Install dependencies
uv sync

# Run scraper manually
ELASTICSEARCH_URL=http://localhost:9200 uv run python scraper/main.py

# Run MCP server manually
ELASTICSEARCH_URL=http://localhost:9200 uv run python mcp_server/main.py

# Run standalone (Python + Docker Elasticsearch)
uv run python run_standalone.py

# Test the setup
uv run python test_setup.py
```

## Integration Options

- **Amazon Q Developer** - See `AMAZON_Q_INTEGRATION.md`
- **Windsurf IDE** - See `WINDSURF_INTEGRATION.md`
- **Custom MCP Client** - Use the MCP server directly via stdio protocol
