#!/usr/bin/env python3
"""
Test script for FastMCP server functionality.
"""

import asyncio
import os
from fastmcp import Client

async def test_fastmcp_server():
    """Test the FastMCP server functionality."""
    server_url = "http://localhost:8000/mcp/"
    
    print("🧪 Testing FastMCP Server")
    print("=" * 40)
    
    try:
        async with Client(server_url) as client:
            print("✅ Connected to FastMCP server")
            
            # Test ping
            await client.ping()
            print("✅ Server ping successful")
            
            # List available tools
            tools = await client.list_tools()
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"   - {tool.name}: {tool.description}")
            
            # List available resources
            resources = await client.list_resources()
            print(f"✅ Found {len(resources)} resources:")
            for resource in resources:
                print(f"   - {resource.uri}: {resource.name}")
            
            # Test search functionality
            print("\n🔍 Testing search functionality...")
            search_result = await client.call_tool("search_documentation", {
                "query": "agent configuration",
                "max_results": 3
            })
            
            if hasattr(search_result, 'content') and search_result.content:
                if isinstance(search_result.content, list) and len(search_result.content) > 0:
                    content = search_result.content[0].text if hasattr(search_result.content[0], 'text') else str(search_result.content[0])
                else:
                    content = str(search_result.content)
                
                print(f"✅ Search successful - content length: {len(content)}")
                # Parse the content to see results
                content_lines = content.split('\n')[:10]
                for line in content_lines:
                    if line.strip():
                        print(f"   {line}")
            else:
                print("⚠️  Search returned no results (index may be empty)")
            
            # Test sections overview
            print("\n📊 Testing sections overview...")
            sections_result = await client.call_tool("get_documentation_sections")
            
            if sections_result.data:
                sections = sections_result.data
                print(f"✅ Found {sections.get('total_documents', 0)} total documents")
                print(f"   Section types: {len(sections.get('section_types', []))}")
                print(f"   Popular sections: {len(sections.get('popular_sections', []))}")
            else:
                print("⚠️  Sections overview returned no data")
            
            # Test resource reading
            print("\n📚 Testing resource access...")
            health_resource = await client.read_resource("strands://docs/health")
            print("✅ Health resource:")
            if hasattr(health_resource, 'content'):
                print(health_resource.content[:200] + "..." if len(health_resource.content) > 200 else health_resource.content)
            elif isinstance(health_resource, list) and len(health_resource) > 0:
                print(health_resource[0].content[:200] + "..." if len(health_resource[0].content) > 200 else health_resource[0].content)
            else:
                print(f"Resource type: {type(health_resource)}")
            
            print("\n🎉 All tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print("\n💡 Make sure:")
        print("   1. FastMCP server is running: uv run fastmcp-server")
        print("   2. Elasticsearch is running: docker-compose up -d elasticsearch")
        print("   3. Data is indexed: uv run scraper")

if __name__ == "__main__":
    asyncio.run(test_fastmcp_server())
