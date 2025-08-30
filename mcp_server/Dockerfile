FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and UV
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV using pip instead of shell script for better reliability
RUN pip install uv

# Copy project files (when building from /mcp_server root directory)
COPY pyproject.toml uv.lock ./
COPY . ./mcp_server/

# Install dependencies with UV
RUN uv sync

# Set environment variable for Elasticsearch URL
ENV ELASTICSEARCH_URL=http://elasticsearch:9200

# Expose MCP server port
EXPOSE 8000

# Run FastMCP server with UV
CMD ["uv", "run", "fastmcp-server"]
