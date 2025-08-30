# FastMCP Web Deployment Guide

This guide explains how to deploy the Strands MCP project using FastMCP for web accessibility.

## Overview

The project has been converted from a local stdin/stdout MCP server to a web-accessible FastMCP server that anyone can use via HTTP.

## Architecture

```
Internet Users
    ↓ HTTP
FastMCP Server (Port 8000)
    ↓ Internal
Elasticsearch (Port 9200)
    ↑ Data
Scraper (One-time)
```

## FastMCP Server Features

### **MCP Tools**
- `search_documentation`: Advanced search with Elasticsearch boosting
- `get_documentation_sections`: Overview of available content

### **MCP Resources**
- `strands://docs/search`: Documentation search guide
- `strands://docs/health`: System health status

### **Web Endpoints**
- **MCP Endpoint**: `http://localhost:8000/mcp/`
- **Health Check**: Available via MCP resources
- **Direct HTTP**: Standard MCP over HTTP protocol

## Local Development

### Start with Elasticsearch
```bash
# Start Elasticsearch first
docker-compose up -d elasticsearch

# Run scraper to populate data
uv run scraper

# Start FastMCP server
uv run fastmcp-server
```

### Test the Server
```python
from fastmcp import Client

async def test_server():
    async with Client("http://localhost:8000/mcp/") as client:
        # Test search
        result = await client.call_tool("search_documentation", {
            "query": "agent configuration",
            "max_results": 5
        })
        print(result)
        
        # Get sections overview
        sections = await client.call_tool("get_documentation_sections")
        print(sections)
```

## Railway Deployment

### Service Configuration

**1. Elasticsearch Service**
- **Image**: `docker.elastic.co/elasticsearch/elasticsearch:8.11.1`
- **Environment**:
  ```
  discovery.type=single-node
  xpack.security.enabled=false
  ES_JAVA_OPTS=-Xms512m -Xmx512m
  ```
- **Volume**: `/usr/share/elasticsearch/data` (10GB)

**2. Scraper Service** 
- **Config**: `scraper-railway.toml`
- **Command**: `uv run scraper`
- **Restart**: `never` (one-time job)
- **Environment**: `ELASTICSEARCH_URL=${{elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200`

**3. FastMCP Server Service**
- **Config**: `railway.toml`
- **Command**: `uv run fastmcp-server`
- **Port**: Generate domain (public access)
- **Environment**: `ELASTICSEARCH_URL=${{elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200`

### Deployment Order
1. Deploy Elasticsearch → Wait for healthy
2. Deploy Scraper → Wait for completion (exits)
3. Deploy FastMCP Server → Public endpoint ready

## Client Integration

### Python Client
```python
from fastmcp import Client

# Connect to deployed server
async with Client("https://your-railway-url/mcp/") as client:
    tools = await client.list_tools()
    result = await client.call_tool("search_documentation", {
        "query": "your search terms"
    })
```

### Claude Desktop Integration
```json
{
  "mcpServers": {
    "strands-docs": {
      "command": "fastmcp",
      "args": ["connect", "https://your-railway-url/mcp/"]
    }
  }
}
```

### Cursor IDE Integration
```json
{
  "mcpServers": {
    "strands-docs": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/client-http",
        "https://your-railway-url/mcp/"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ELASTICSEARCH_URL` | Elasticsearch connection URL | `http://localhost:9200` |
| `PORT` | FastMCP server port | `8000` |
| `HOST` | FastMCP server host | `0.0.0.0` |

## Monitoring

### Health Check
```python
# Via MCP resource
async with Client("http://your-server/mcp/") as client:
    health = await client.read_resource("strands://docs/health")
    print(health.content)
```

### Logs
- **Railway**: View in Railway dashboard
- **Local**: Console output with structured logging

## Benefits of FastMCP

1. **Web Accessible**: Anyone can connect via HTTP
2. **Multi-Client**: Supports concurrent connections
3. **Standard Protocol**: Full MCP compatibility
4. **Production Ready**: Built for deployment
5. **Authentication**: Ready for auth providers
6. **Monitoring**: Built-in health checks

## Cost Estimation (Railway)

- **Elasticsearch**: ~$8-12/month (always running)
- **FastMCP Server**: ~$3-5/month (always running)
- **Scraper**: ~$0.10/month (runs once)
- **Total**: ~$11-17/month

## Troubleshooting

### Server Won't Start
- Check Elasticsearch connection
- Verify environment variables
- Check port availability

### Search Returns No Results
- Ensure scraper completed successfully
- Check Elasticsearch index exists
- Verify document count > 0

### Connection Issues
- Verify Railway domain is accessible
- Check MCP endpoint path `/mcp/`
- Test with simple HTTP client first

## Migration from Local MCP

The original `mcp_server/main.py` (stdin/stdout) is preserved for local development. The new `mcp_server/fastmcp_server.py` provides web accessibility while maintaining the same search functionality.

Both servers share:
- Same Elasticsearch queries
- Same search optimization
- Same result formatting
- Compatible tool interfaces
