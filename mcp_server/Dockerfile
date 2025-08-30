FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and UV
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV and ensure it's in PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project files (when building from /mcp_server root directory)
COPY pyproject.toml uv.lock ./
COPY . ./

# Install dependencies with UV (using full path to ensure it's found)
RUN /root/.cargo/bin/uv sync

# Set environment variable for Elasticsearch URL
ENV ELASTICSEARCH_URL=http://elasticsearch:9200

# Expose MCP server port
EXPOSE 8000

# Run FastMCP server with UV (using full path)
CMD ["/root/.cargo/bin/uv", "run", "fastmcp-server"]
