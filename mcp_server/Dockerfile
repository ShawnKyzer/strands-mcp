FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY mcp_server/ ./mcp_server/

# Create logs directory
RUN mkdir -p logs

# Expose MCP server port
EXPOSE 8000

# Run MCP server
CMD ["python", "-u", "mcp_server/main.py"]
