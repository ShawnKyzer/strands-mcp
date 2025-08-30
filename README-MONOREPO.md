# Railway Monorepo Deployment Guide

This project is now configured as a proper Railway monorepo with three separate services:

## Project Structure

```
strands-mcp/
├── elasticsearch/           # Elasticsearch service
│   ├── Dockerfile          # Custom ES configuration
│   └── railway.json        # ES deployment config
├── scraper/                # Documentation scraper
│   ├── main.py            # Scraper implementation
│   └── railway.json       # Scraper deployment config
├── mcp_server/             # FastMCP server
│   ├── fastmcp_server.py  # MCP server implementation
│   └── railway.json       # MCP server deployment config
├── pyproject.toml          # Shared dependencies
├── uv.lock                # Dependency lock file
└── railway.json           # Root config (fallback)
```

## Service Configuration

### 1. Elasticsearch Service
- **Root Directory**: `/elasticsearch`
- **Builder**: Dockerfile
- **Purpose**: Search backend with 2GB memory allocation
- **Config**: `elasticsearch/railway.json`

### 2. Scraper Service  
- **Root Directory**: `/scraper`
- **Builder**: Nixpacks with UV
- **Purpose**: Populate Elasticsearch with documentation
- **Config**: `scraper/railway.json`
- **Environment**: `ELASTICSEARCH_URL` references elasticsearch service

### 3. MCP Server Service
- **Root Directory**: `/mcp_server` 
- **Builder**: Nixpacks with UV
- **Purpose**: FastMCP HTTP server for global access
- **Config**: `mcp_server/railway.json`
- **Environment**: `ELASTICSEARCH_URL` references elasticsearch service

## Railway UI Configuration

For each service in Railway dashboard:

1. **Settings → Source**:
   - Connect GitHub repository
   - Set **Root Directory** to service folder

2. **Settings → Deploy**:
   - Set **Config Path** to service's `railway.json`
   - Configure watch paths in UI (not config file)

3. **Variables**:
   - Add `ELASTICSEARCH_URL=http://${{elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200`

## Deployment Order

1. **Elasticsearch** - Deploy first, wait for healthy status
2. **Scraper** - Deploy to populate search index  
3. **MCP Server** - Deploy last to serve HTTP endpoints

## Service Communication

Services communicate via Railway's private networking:
- `elasticsearch.RAILWAY_PRIVATE_DOMAIN:9200`
- Internal hostnames resolve automatically
- No public internet required for inter-service communication

## Benefits

- ✅ Proper service separation
- ✅ Independent scaling and configuration  
- ✅ Efficient rebuilds (only changed services)
- ✅ Railway best practices compliance
- ✅ Private networking between services
- ✅ Centralized dependency management
