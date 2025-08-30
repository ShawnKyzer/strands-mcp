# Railway Deployment Guide

This guide explains how to deploy the Strands MCP project on Railway with the correct service order and dependencies.

## Architecture Overview

Railway deployment requires 3 services in this order:
1. **Elasticsearch Service** - Database for document storage
2. **Scraper Service** - One-time job to populate Elasticsearch
3. **MCP Server Service** - Main application server

## Deployment Steps

### 1. Deploy Elasticsearch Service

**Service Name:** `strands-elasticsearch`

**Source:** Docker Image
- Image: `docker.elastic.co/elasticsearch/elasticsearch:8.11.1`

**Environment Variables:**
```
discovery.type=single-node
xpack.security.enabled=false
ES_JAVA_OPTS=-Xms512m -Xmx512m
```

**Volume:**
- Mount Path: `/usr/share/elasticsearch/data`
- Size: 10GB (recommended)

**Port:** 9200 (internal only - no public exposure needed)

### 2. Deploy Scraper Service (One-time Job)

**Service Name:** `strands-scraper`

**Source:** GitHub Repository (this repo)

**Root Directory:** `/` (main project root)

**Railway Config:** Create `scraper-railway.toml` in project root:
```toml
[build]
builder = "NIXPACKS"
nixpacksPlan = { phases = { install = { dependsOn = ["setup"], cmds = ["curl -LsSf https://astral.sh/uv/install.sh | sh", "uv sync"] } } }

[deploy]
startCommand = "uv run scraper"
restartPolicyType = "never"
```

**Environment Variables:**
```
ELASTICSEARCH_URL=${{strands-elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200
DOCS_BASE_URL=https://strandsagents.com/latest/documentation/docs/
```

**Notes:**
- This is a one-time job that will exit after scraping
- Set restart policy to "never" so it doesn't restart after completion
- Must run after Elasticsearch is ready

### 3. Deploy MCP Server Service

**Service Name:** `strands-mcp-server`

**Source:** GitHub Repository (this repo)

**Root Directory:** `/` (main project root)

**Railway Config:** Use existing `railway.toml`:
```toml
[build]
builder = "NIXPACKS"
nixpacksPlan = { phases = { install = { dependsOn = ["setup"], cmds = ["curl -LsSf https://astral.sh/uv/install.sh | sh", "uv sync"] } } }

[deploy]
startCommand = "uv run mcp-server"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
```

**Environment Variables:**
```
ELASTICSEARCH_URL=${{strands-elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200
```

**Port:** Generate domain (this will be your public MCP server endpoint)

## Service Dependencies

```
Elasticsearch (always running)
    ↓
Scraper (run once, then stop)
    ↓
MCP Server (always running)
```

## Railway Private Networking

Railway services communicate via private networking using:
- `${{service-name.RAILWAY_PRIVATE_DOMAIN}}`
- Internal port (9200 for Elasticsearch)

## Deployment Order

1. **First:** Deploy Elasticsearch service and wait for it to be healthy
2. **Second:** Deploy Scraper service and let it complete (will show as "Exited")
3. **Third:** Deploy MCP Server service

## Monitoring

- **Elasticsearch:** Check logs for startup completion
- **Scraper:** Monitor logs for indexing progress, should exit with success
- **MCP Server:** Should show as "Running" and respond to health checks

## Environment Variables Reference

| Variable | Service | Value |
|----------|---------|-------|
| `ELASTICSEARCH_URL` | Scraper, MCP Server | `${{strands-elasticsearch.RAILWAY_PRIVATE_DOMAIN}}:9200` |
| `DOCS_BASE_URL` | Scraper | `https://strandsagents.com/latest/documentation/docs/` |
| `discovery.type` | Elasticsearch | `single-node` |
| `xpack.security.enabled` | Elasticsearch | `false` |
| `ES_JAVA_OPTS` | Elasticsearch | `-Xms512m -Xmx512m` |

## Troubleshooting

- **Scraper fails:** Check if Elasticsearch is running and accessible
- **MCP Server fails:** Ensure scraper has completed and Elasticsearch has data
- **Connection issues:** Verify private domain variables are correct
- **Memory issues:** Adjust ES_JAVA_OPTS if needed

## Cost Optimization

- Elasticsearch: Always running (required)
- Scraper: Runs once, then stops (minimal cost)
- MCP Server: Always running (main service cost)

Total: ~$5-10/month depending on usage and resource allocation.
