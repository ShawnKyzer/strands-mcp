# Amazon Q Developer Integration Guide

This guide explains how to integrate the Strands Agents MCP server with Amazon Q Developer.

## Prerequisites

1. **Amazon Q Developer** - Ensure you have Amazon Q Developer installed and configured
2. **Docker & Docker Compose** - Required to run the MCP server
3. **MCP Support** - Amazon Q Developer with MCP protocol support

## Setup Steps

### 1. Start the MCP Server

```bash
# Clone and navigate to the project
cd /path/to/strands-mcp

# Start all services
./start.sh

# Or manually:
docker-compose up -d elasticsearch
# Wait for Elasticsearch to be ready
docker-compose up scraper  # This will scrape and index the docs
docker-compose up -d mcp-server
```

### 2. Configure Amazon Q Developer

Add the MCP server configuration to your Amazon Q Developer settings. The exact method depends on your Amazon Q setup:

#### Option A: Direct MCP Configuration

```json
{
  "mcpServers": {
    "strands-agents-docs": {
      "command": "docker",
      "args": [
        "exec", "-i", "strands-mcp-server", 
        "python", "-u", "mcp_server/main.py"
      ],
      "env": {
        "ELASTICSEARCH_URL": "http://elasticsearch:9200"
      }
    }
  }
}
```

#### Option B: Stdio Connection

If your Amazon Q setup supports direct stdio connections:

```json
{
  "mcpServers": {
    "strands-agents-docs": {
      "command": "python",
      "args": ["-u", "/path/to/strands-mcp/mcp_server/main.py"],
      "env": {
        "ELASTICSEARCH_URL": "http://localhost:9200"
      }
    }
  }
}
```

### 3. Verify Integration

Test the integration by asking Amazon Q questions about Strands Agents:

- "How do I create a basic agent with Strands Agents?"
- "What model providers are supported by Strands Agents?"
- "Show me examples of multi-agent systems in Strands"
- "How do I deploy Strands agents to AWS Lambda?"

## Available MCP Tools

The server provides three main tools for Amazon Q:

### 1. `search_documentation`
Search through the Strands Agents documentation.

**Parameters:**
- `query` (required): Search terms
- `max_results` (optional): Maximum results to return (default: 10)
- `section_filter` (optional): Filter by documentation section

**Example Usage:**
```
Amazon Q: "Search for information about agent tools"
→ Uses search_documentation with query="agent tools"
```

### 2. `get_document_by_url`
Retrieve a specific document by its URL.

**Parameters:**
- `url` (required): Full URL of the document

**Example Usage:**
```
Amazon Q: "Get the full content of the quickstart guide"
→ Uses get_document_by_url with the quickstart URL
```

### 3. `list_sections`
List all available documentation sections.

**Example Usage:**
```
Amazon Q: "What documentation sections are available?"
→ Uses list_sections to show all available sections
```

## Documentation Coverage

The MCP server indexes comprehensive Strands Agents v1.1.x documentation including:

- **User Guide & Quickstart** - Getting started with Strands Agents
- **Core Concepts** - Agents, loops, state, sessions, prompts, hooks
- **Tools System** - Python tools, MCP integration, example tools
- **Model Providers** - Amazon Bedrock, Anthropic, OpenAI, and 7+ others
- **Streaming** - Async iterators and callback handlers
- **Multi-agent Systems** - Agent2Agent, swarms, graphs, workflows
- **Safety & Security** - Responsible AI, guardrails, prompt engineering
- **Observability** - Metrics, traces, logs, evaluation
- **Deployment** - Production deployment on AWS Lambda, Fargate

## Troubleshooting

### MCP Server Not Responding
1. Check if containers are running: `docker ps`
2. Check MCP server logs: `docker-compose logs mcp-server`
3. Verify Elasticsearch is healthy: `curl http://localhost:9200/_health`

### No Search Results
1. Verify documentation was indexed: `python test_setup.py`
2. Check Elasticsearch index: `curl http://localhost:9200/strands-agents-docs/_count`
3. Re-run scraper if needed: `docker-compose up scraper`

### Amazon Q Integration Issues
1. Verify MCP protocol version compatibility
2. Check Amazon Q Developer logs for connection errors
3. Ensure the MCP server container is accessible from Amazon Q

## Advanced Configuration

### Custom Elasticsearch Settings
Modify `docker-compose.yml` to adjust Elasticsearch memory, ports, or persistence settings.

### Scraper Customization
Edit `scraper/main.py` to modify which documentation sections are scraped or how content is processed.

### MCP Server Customization
Modify `mcp_server/main.py` to add custom tools or change search behavior.

## Performance Notes

- **Initial Setup**: First run takes 2-3 minutes to download images and scrape docs
- **Search Performance**: Elasticsearch provides sub-second search responses
- **Memory Usage**: Default setup uses ~1GB RAM (Elasticsearch: 512MB, other services: ~500MB)
- **Storage**: Documentation index requires ~50MB disk space

## Support

For issues specific to:
- **Strands Agents**: Visit [Strands Agents GitHub](https://github.com/strands-agents/sdk-python)
- **Amazon Q Developer**: Check AWS documentation
- **This MCP Server**: Check the project README and logs
