# Strands Agents MCP Server Startup Script for Windows

$ErrorActionPreference = "Stop"

Write-Host "Starting Strands Agents MCP Server for Amazon Q" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# Check if Docker is available
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check Docker Compose
$dockerComposeCmd = "docker-compose"
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    try {
        & docker compose version | Out-Null
        $dockerComposeCmd = "docker compose"
        Write-Host "Using 'docker compose' instead of 'docker-compose'" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Docker Compose is not available. Please install Docker Desktop with Compose." -ForegroundColor Red
        exit 1
    }
}

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Copy environment file if it doesn't exist
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env file from .env.example" -ForegroundColor Yellow
}

Write-Host "Building and starting services..." -ForegroundColor Cyan

# Start Elasticsearch first
Write-Host "Starting Elasticsearch..." -ForegroundColor Cyan
if ($dockerComposeCmd -eq "docker compose") {
    & docker compose up -d elasticsearch
} else {
    & docker-compose up -d elasticsearch
}

# Wait for Elasticsearch to be ready
Write-Host "Waiting for Elasticsearch to be ready..." -ForegroundColor Yellow
Start-Sleep 10

# Check Elasticsearch health
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9200/_health" -UseBasicParsing -TimeoutSec 2
        Write-Host "Elasticsearch is ready!" -ForegroundColor Green
        break
    }
    catch {
        Write-Host "   Waiting for Elasticsearch... ($i/30)" -ForegroundColor Yellow
        Start-Sleep 2
    }
}

# Run the scraper to index documentation
Write-Host "Running documentation scraper..." -ForegroundColor Cyan
if ($dockerComposeCmd -eq "docker compose") {
    & docker compose up --build scraper
} else {
    & docker-compose up --build scraper
}

# Check if scraping was successful
Write-Host "Checking if documentation was indexed..." -ForegroundColor Cyan
Start-Sleep 5

# Start the MCP server
Write-Host "Starting MCP server..." -ForegroundColor Cyan
if ($dockerComposeCmd -eq "docker compose") {
    & docker compose up -d --build mcp-server
} else {
    & docker-compose up -d --build mcp-server
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
Write-Host "  - Elasticsearch: http://localhost:9200"
Write-Host "  - MCP Server: Running in container 'strands-mcp-server'"
Write-Host ""
Write-Host "To test the setup, run:" -ForegroundColor Cyan
Write-Host "  python test_setup.py"
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  $dockerComposeCmd logs -f mcp-server"
Write-Host "  $dockerComposeCmd logs elasticsearch"
Write-Host ""
Write-Host "To stop all services:" -ForegroundColor Cyan
Write-Host "  $dockerComposeCmd down"
Write-Host ""
Write-Host "For Amazon Q integration instructions, see README.md" -ForegroundColor Cyan