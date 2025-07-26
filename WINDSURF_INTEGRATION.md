# Windsurf Integration Guide

This guide explains how to integrate the Strands Agents MCP server with Windsurf IDE to enhance your development experience with Strands Agents documentation.

## Prerequisites

1. **Windsurf IDE** - Ensure you have Windsurf installed
2. **MCP Server Running** - The Strands Agents MCP server must be running
3. **Docker** - Required for the containerized MCP server

## Setup Steps

### 1. Start the MCP Server

```bash
# Start all services including the MCP server
./start.sh

# Or manually start just the MCP server
docker-compose up -d mcp-server
```

### 2. Configure Windsurf

#### Option A: Use the provided configuration file

Copy the `windsurf-mcp-config.json` file to your Windsurf MCP configuration directory:

```bash
# Copy the configuration file to Windsurf's MCP config location
# (Adjust path based on your Windsurf installation)
cp windsurf-mcp-config.json ~/.windsurf/mcp-servers.json
```

#### Option B: Manual configuration

Add the following to your Windsurf MCP configuration:

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

### 3. Restart Windsurf

After adding the MCP server configuration, restart Windsurf to load the new server.

## Available Features

Once integrated, Windsurf will have access to three powerful tools for Strands Agents development:

### 1. `search_documentation`
Search through comprehensive Strands Agents documentation.

**Usage in Windsurf:**
- Ask: "How do I create a basic agent with Strands?"
- Ask: "What are the available model providers?"
- Ask: "Show me examples of multi-agent systems"

### 2. `get_document_by_url`
Retrieve specific documentation pages by URL.

**Usage in Windsurf:**
- Ask: "Get the full quickstart guide"
- Ask: "Show me the deployment documentation"

### 3. `list_sections`
Browse all available documentation sections.

**Usage in Windsurf:**
- Ask: "What documentation sections are available?"
- Ask: "List all the topics covered in Strands Agents docs"

## Example Windsurf Queries

With the MCP server integrated, you can ask Windsurf questions like:

### Development Questions
- "How do I set up a Strands agent with Amazon Bedrock?"
- "What's the difference between streaming and non-streaming agents?"
- "Show me how to implement custom tools in Strands Agents"

### Architecture Questions
- "How do I implement a multi-agent workflow?"
- "What are the best practices for agent state management?"
- "How do I add observability to my agents?"

### Deployment Questions
- "How do I deploy Strands agents to AWS Lambda?"
- "What are the production deployment options?"
- "How do I configure agents for different environments?"

## Documentation Coverage

The MCP server provides Windsurf with access to:

- **Core Concepts** - Agents, loops, state, sessions, prompts
- **Tools System** - Python tools, MCP integration, examples
- **Model Providers** - Amazon Bedrock, Anthropic, OpenAI, Ollama, and more
- **Streaming** - Async iterators and callback handlers
- **Multi-agent Systems** - Agent2Agent, swarms, graphs, workflows
- **Safety & Security** - Responsible AI, guardrails, prompt engineering
- **Observability** - Metrics, traces, logs, evaluation
- **Deployment** - Production deployment guides for AWS Lambda, Fargate

## Troubleshooting

### MCP Server Not Responding
1. Check if the MCP server container is running:
   ```bash
   docker ps | grep strands-mcp-server
   ```

2. Check MCP server logs:
   ```bash
   docker-compose logs mcp-server
   ```

3. Verify Elasticsearch is healthy:
   ```bash
   curl http://localhost:9200/_health
   ```

### Windsurf Not Finding the Server
1. Verify the MCP configuration file path is correct
2. Check Windsurf logs for MCP connection errors
3. Ensure Docker is accessible from Windsurf's environment
4. Restart Windsurf after configuration changes

### No Search Results
1. Verify documentation was indexed:
   ```bash
   python test_setup.py
   ```

2. Check Elasticsearch index:
   ```bash
   curl http://localhost:9200/strands-agents-docs/_count
   ```

3. Re-run scraper if needed:
   ```bash
   docker-compose up scraper
   ```

## Advanced Configuration

### Custom Elasticsearch URL
If you're running Elasticsearch on a different host/port, update the environment variable:

```json
{
  "mcpServers": {
    "strands-agents-docs": {
      "command": "docker",
      "args": ["exec", "-i", "strands-mcp-server", "python", "-u", "mcp_server/main.py"],
      "env": {
        "ELASTICSEARCH_URL": "http://your-elasticsearch-host:9200"
      }
    }
  }
}
```

### Standalone Mode
If you prefer to run the MCP server outside Docker:

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

## Benefits for Windsurf Users

- **Instant Documentation Access** - No need to browse external docs
- **Context-Aware Help** - Get relevant information based on your current code
- **Code Examples** - Access to searchable code snippets and examples
- **Best Practices** - Learn recommended patterns and approaches
- **Deployment Guidance** - Get help with production deployment strategies

## Support

For issues specific to:
- **Strands Agents**: Visit [Strands Agents GitHub](https://github.com/strands-agents/sdk-python)
- **Windsurf Integration**: Check Windsurf MCP documentation
- **This MCP Server**: Check the project README and logs
