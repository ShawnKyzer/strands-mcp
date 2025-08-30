#!/usr/bin/env python3
"""
Standalone script to run the MCP server with UV.
This script starts Elasticsearch in Docker but runs the scraper and MCP server using UV.
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path

def check_uv():
    """Check if UV is installed."""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

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

def run_scraper_uv():
    """Run the documentation scraper using UV."""
    print("🕷️  Running documentation scraper with UV...")
    
    # Set environment variables
    env = os.environ.copy()
    env['ELASTICSEARCH_URL'] = 'http://localhost:9200'
    env['DOCS_BASE_URL'] = 'https://strandsagents.com/latest/documentation/docs/'
    
    try:
        result = subprocess.run(['uv', 'run', 'scraper'], 
                              env=env, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("✅ Documentation scraping completed!")
            return True
        else:
            print(f"❌ Scraper failed with exit code {result.returncode}")
            return False
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")
        return False

async def run_mcp_server_uv():
    """Run the MCP server using UV."""
    print("🌐 Starting MCP server with UV...")
    
    # Set environment variables
    env = os.environ.copy()
    env['ELASTICSEARCH_URL'] = 'http://localhost:9200'
    
    try:
        print("🚀 MCP server is running! Use Ctrl+C to stop.")
        print("📋 The server is ready for Amazon Q integration.")
        print("📖 See AMAZON_Q_INTEGRATION.md for setup instructions.")
        
        process = subprocess.Popen(['uv', 'run', 'mcp-server'], 
                                 env=env, cwd=Path(__file__).parent)
        
        # Wait for the process to complete or be interrupted
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n🛑 MCP server stopped by user.")
            process.terminate()
            process.wait()
        
        return True
        
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
    print("🚀 Strands Agents MCP Server - UV Standalone Mode")
    print("=" * 55)
    
    # Check if UV is installed
    if not check_uv():
        print("❌ UV is not installed. Please install UV first:")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        return 1
    
    # Sync dependencies first
    print("📦 Syncing dependencies with UV...")
    try:
        result = subprocess.run(['uv', 'sync'], cwd=Path(__file__).parent)
        if result.returncode != 0:
            print("❌ Failed to sync dependencies")
            return 1
    except Exception as e:
        print(f"❌ Failed to sync dependencies: {e}")
        return 1
    
    try:
        # Start Elasticsearch
        if not start_elasticsearch():
            return 1
        
        # Run scraper
        if not run_scraper_uv():
            return 1
        
        # Run MCP server
        await run_mcp_server_uv()
        
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
