#!/usr/bin/env python3
"""
Standalone script to run the MCP server without Docker.
This script starts Elasticsearch in Docker but runs the scraper and MCP server directly in Python.
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path

def check_elasticsearch():
    """Check if Elasticsearch is running."""
    try:
        import requests
        response = requests.get('http://localhost:9200', timeout=5)
        return response.status_code == 200
    except:
        return False

def start_elasticsearch():
    """Start Elasticsearch using Docker."""
    print("🔧 Starting Elasticsearch with Docker...")
    
    # Use the Docker command we found
    docker_cmd = "docker"
    if os.path.exists("/usr/local/bin/docker"):
        docker_cmd = "/usr/local/bin/docker"
    
    try:
        # Stop any existing Elasticsearch container
        subprocess.run([docker_cmd, "stop", "strands-elasticsearch"], 
                      capture_output=True, check=False)
        subprocess.run([docker_cmd, "rm", "strands-elasticsearch"], 
                      capture_output=True, check=False)
        
        # Start Elasticsearch
        cmd = [
            docker_cmd, "run", "-d",
            "--name", "strands-elasticsearch",
            "-p", "9200:9200",
            "-p", "9300:9300",
            "-e", "discovery.type=single-node",
            "-e", "xpack.security.enabled=false",
            "-e", "ES_JAVA_OPTS=-Xms512m -Xmx512m",
            "docker.elastic.co/elasticsearch/elasticsearch:8.11.1"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to start Elasticsearch: {result.stderr}")
            return False
        
        print("⏳ Waiting for Elasticsearch to be ready...")
        for i in range(30):
            if check_elasticsearch():
                print("✅ Elasticsearch is ready!")
                return True
            print(f"   Waiting... ({i+1}/30)")
            time.sleep(2)
        
        print("❌ Elasticsearch failed to start within 60 seconds")
        return False
        
    except Exception as e:
        print(f"❌ Error starting Elasticsearch: {e}")
        return False

async def run_scraper():
    """Run the documentation scraper."""
    print("🕷️  Running documentation scraper...")
    
    # Set environment variables
    os.environ['ELASTICSEARCH_URL'] = 'http://localhost:9200'
    os.environ['DOCS_BASE_URL'] = 'https://strandsagents.com/latest/documentation/docs/'
    
    # Import and run the scraper
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from scraper.main import StrandsDocsScraper
        
        base_url = os.getenv('DOCS_BASE_URL', 'https://strandsagents.com/latest/documentation/docs/')
        elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
        
        async with StrandsDocsScraper(base_url, elasticsearch_url) as scraper:
            await scraper.run()
        
        print("✅ Documentation scraping completed!")
        return True
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")
        return False

async def run_mcp_server():
    """Run the MCP server."""
    print("🌐 Starting MCP server...")
    
    # Set environment variables
    os.environ['ELASTICSEARCH_URL'] = 'http://localhost:9200'
    
    try:
        from mcp_server.main import StrandsDocsMCPServer
        
        elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
        server = StrandsDocsMCPServer(elasticsearch_url)
        
        print("🚀 MCP server is running! Use Ctrl+C to stop.")
        print("📋 The server is ready for Amazon Q integration.")
        print("📖 See AMAZON_Q_INTEGRATION.md for setup instructions.")
        
        await server.run()
        
    except KeyboardInterrupt:
        print("\n🛑 MCP server stopped by user.")
    except Exception as e:
        print(f"❌ MCP server failed: {e}")
        return False

def stop_elasticsearch():
    """Stop Elasticsearch container."""
    docker_cmd = "docker"
    if os.path.exists("/usr/local/bin/docker"):
        docker_cmd = "/usr/local/bin/docker"
    
    try:
        subprocess.run([docker_cmd, "stop", "strands-elasticsearch"], 
                      capture_output=True, check=False)
        subprocess.run([docker_cmd, "rm", "strands-elasticsearch"], 
                      capture_output=True, check=False)
        print("🛑 Elasticsearch stopped.")
    except:
        pass

async def main():
    """Main function to run the complete setup."""
    print("🚀 Strands Agents MCP Server - Standalone Mode")
    print("=" * 50)
    
    try:
        # Start Elasticsearch
        if not start_elasticsearch():
            return 1
        
        # Run scraper
        if not await run_scraper():
            return 1
        
        # Run MCP server
        await run_mcp_server()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        stop_elasticsearch()

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        sys.exit(0)
