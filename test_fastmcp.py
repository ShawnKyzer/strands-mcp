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
            
            if search_result.data:
                print(f"✅ Search returned {len(search_result.data)} results")
                for i, result in enumerate(search_result.data[:2], 1):
                    print(f"   {i}. {result.get('title', 'No title')}")
                    print(f"      Score: {result.get('relevance_score', 'N/A')}")
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
            print(health_resource.content[:200] + "..." if len(health_resource.content) > 200 else health_resource.content)
            
            print("\n🎉 All tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print("\n💡 Make sure:")
        print("   1. FastMCP server is running: uv run fastmcp-server")
        print("   2. Elasticsearch is running: docker-compose up -d elasticsearch")
        print("   3. Data is indexed: uv run scraper")

if __name__ == "__main__":
    asyncio.run(test_fastmcp_server())
