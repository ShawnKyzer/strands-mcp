#!/usr/bin/env python3
"""
Test script to verify MCP server tools are properly exposed.
This simulates what Amazon Q would do when connecting to the MCP server.
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Dict

async def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages."""
    
    # Start the MCP server process
    process = subprocess.Popen(
        [sys.executable, "-u", "mcp_server/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"ELASTICSEARCH_URL": "http://localhost:9200"}
    )
    
    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Sending initialize request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"Initialize response: {json.dumps(response, indent=2)}")
        
        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        print("Sending initialized notification...")
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        
        # List tools request
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        print("Sending list tools request...")
        process.stdin.write(json.dumps(list_tools_request) + "\n")
        process.stdin.flush()
        
        # Read tools response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"Tools list response: {json.dumps(response, indent=2)}")
            
            # Check if tools are present
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"\nFound {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                
                if len(tools) > 0:
                    print("\n✅ SUCCESS: MCP server is properly exposing tools!")
                    return True
                else:
                    print("\n❌ ERROR: No tools found in MCP server response")
                    return False
            else:
                print("\n❌ ERROR: Invalid tools list response")
                return False
        else:
            print("\n❌ ERROR: No response received for tools list")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        process.terminate()
        process.wait()

async def test_search_tool():
    """Test the search tool specifically."""
    
    process = subprocess.Popen(
        [sys.executable, "-u", "mcp_server/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"ELASTICSEARCH_URL": "http://localhost:9200"}
    )
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        process.stdout.readline()  # Read init response
        
        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        
        # Test search tool
        search_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_documentation",
                "arguments": {
                    "query": "agent",
                    "max_results": 3
                }
            }
        }
        
        print("Testing search_documentation tool...")
        process.stdin.write(json.dumps(search_request) + "\n")
        process.stdin.flush()
        
        # Read search response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"Search response: {json.dumps(response, indent=2)}")
            
            if "result" in response and "content" in response["result"]:
                print("\n✅ SUCCESS: Search tool is working!")
                return True
            else:
                print("\n❌ ERROR: Search tool failed")
                return False
        else:
            print("\n❌ ERROR: No response from search tool")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        process.terminate()
        process.wait()

async def main():
    """Main test function."""
    print("🧪 Testing MCP Server Tools\n")
    
    # Test 1: Check if tools are exposed
    print("=" * 50)
    print("TEST 1: Checking if tools are properly exposed")
    print("=" * 50)
    
    tools_exposed = await test_mcp_server()
    
    if tools_exposed:
        # Test 2: Test search functionality
        print("\n" + "=" * 50)
        print("TEST 2: Testing search tool functionality")
        print("=" * 50)
        
        search_works = await test_search_tool()
        
        if search_works:
            print("\n🎉 ALL TESTS PASSED!")
            print("The MCP server is ready for Amazon Q integration.")
        else:
            print("\n⚠️  Tools are exposed but search functionality failed.")
    else:
        print("\n❌ TESTS FAILED!")
        print("The MCP server is not properly exposing tools to Amazon Q.")

if __name__ == "__main__":
    asyncio.run(main())
