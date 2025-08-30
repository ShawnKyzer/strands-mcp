#!/usr/bin/env python3
"""
FastMCP-based web server for Strands Agents documentation.
Provides HTTP-accessible MCP server that anyone can use.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
import structlog
from elasticsearch import Elasticsearch
from fastmcp import FastMCP, Context

# Configure structured logging
logger = structlog.get_logger(__name__)

class StrandsFastMCPServer:
    """FastMCP server for Strands documentation search."""
    
    def __init__(self, elasticsearch_url: str = "http://localhost:9200"):
        self.elasticsearch_url = elasticsearch_url
        self.index_name = "strands-agents-docs"
        self.es = None
        
        # Create FastMCP server instance
        self.mcp = FastMCP("Strands Agents Documentation Server")
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
    
    async def setup_elasticsearch(self):
        """Initialize Elasticsearch connection."""
        try:
            self.es = Elasticsearch([self.elasticsearch_url])
            
            # Test connection
            info = self.es.info()
            logger.info("Connected to Elasticsearch", 
                       cluster_name=info['cluster_name'],
                       version=info['version']['number'])
            
            # Check if index exists
            if not self.es.indices.exists(index=self.index_name):
                logger.warning("Index does not exist", index=self.index_name)
                return False
            
            # Get document count
            count_response = self.es.count(index=self.index_name)
            doc_count = count_response['count']
            logger.info("Index ready", index=self.index_name, document_count=doc_count)
            
            return True
            
        except Exception as e:
            logger.error("Failed to connect to Elasticsearch", error=str(e))
            return False
    
    def _register_tools(self):
        """Register MCP tools."""
        
        @self.mcp.tool
        async def search_documentation(
            query: str,
            max_results: int = 10,
            ctx: Context = None
        ) -> List[Dict[str, Any]]:
            """
            Search Strands Agents documentation.
            
            Args:
                query: Search query string
                max_results: Maximum number of results to return (default: 10)
            
            Returns:
                List of matching documentation sections with content and metadata
            """
            if ctx:
                await ctx.info(f"Searching for: {query}")
            
            try:
                # Enhanced search query with boosting
                search_body = {
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": [
                                            "title^5",
                                            "headers^3", 
                                            "content^2",
                                            "code_blocks^4"
                                        ],
                                        "type": "best_fields",
                                        "fuzziness": "AUTO"
                                    }
                                },
                                {
                                    "match_phrase": {
                                        "content": {
                                            "query": query,
                                            "boost": 3,
                                            "slop": 2
                                        }
                                    }
                                }
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "highlight": {
                        "fields": {
                            "content": {
                                "fragment_size": 150,
                                "number_of_fragments": 3
                            },
                            "title": {},
                            "headers": {}
                        }
                    },
                    "size": max_results,
                    "_source": ["title", "url", "content", "headers", "code_blocks", "section_type"]
                }
                
                response = self.es.search(index=self.index_name, body=search_body)
                
                results = []
                for hit in response['hits']['hits']:
                    source = hit['_source']
                    
                    # Get highlighted content or fallback to original
                    highlighted_content = ""
                    if 'highlight' in hit:
                        if 'content' in hit['highlight']:
                            highlighted_content = " ... ".join(hit['highlight']['content'])
                        elif 'title' in hit['highlight']:
                            highlighted_content = hit['highlight']['title'][0]
                    
                    if not highlighted_content and source.get('content'):
                        highlighted_content = source['content'][:300] + "..."
                    
                    result = {
                        "title": source.get('title', 'Untitled'),
                        "url": source.get('url', ''),
                        "content": highlighted_content,
                        "headers": source.get('headers', []),
                        "code_blocks": source.get('code_blocks', []),
                        "section_type": source.get('section_type', 'unknown'),
                        "relevance_score": hit['_score']
                    }
                    results.append(result)
                
                if ctx:
                    await ctx.info(f"Found {len(results)} results")
                
                return results
                
            except Exception as e:
                error_msg = f"Search failed: {str(e)}"
                logger.error("Search error", error=error_msg)
                if ctx:
                    await ctx.error(error_msg)
                return []
        
        @self.mcp.tool
        async def get_documentation_sections(ctx: Context = None) -> Dict[str, Any]:
            """
            Get overview of available documentation sections with aggregation data.
            
            Returns:
                Dictionary with section counts, types, and popular topics
            """
            if ctx:
                await ctx.info("Retrieving documentation sections overview")
            
            try:
                # Aggregation query to get section overview
                agg_body = {
                    "size": 0,
                    "aggs": {
                        "section_types": {
                            "terms": {
                                "field": "section_type.keyword",
                                "size": 20
                            }
                        },
                        "popular_titles": {
                            "terms": {
                                "field": "title.keyword",
                                "size": 10
                            }
                        },
                        "total_docs": {
                            "value_count": {
                                "field": "_id"
                            }
                        }
                    }
                }
                
                response = self.es.search(index=self.index_name, body=agg_body)
                
                result = {
                    "total_documents": response['aggregations']['total_docs']['value'],
                    "section_types": [
                        {
                            "type": bucket['key'],
                            "count": bucket['doc_count']
                        }
                        for bucket in response['aggregations']['section_types']['buckets']
                    ],
                    "popular_sections": [
                        {
                            "title": bucket['key'],
                            "count": bucket['doc_count']
                        }
                        for bucket in response['aggregations']['popular_titles']['buckets']
                    ]
                }
                
                if ctx:
                    await ctx.info(f"Retrieved overview of {result['total_documents']} documents")
                
                return result
                
            except Exception as e:
                error_msg = f"Failed to get sections: {str(e)}"
                logger.error("Sections error", error=error_msg)
                if ctx:
                    await ctx.error(error_msg)
                return {"error": error_msg}
    
    def _register_resources(self):
        """Register MCP resources."""
        
        @self.mcp.resource("strands://docs/search")
        async def search_resource(ctx: Context = None) -> str:
            """
            Provides access to Strands documentation search functionality.
            """
            return """
# Strands Agents Documentation Search

This resource provides access to comprehensive Strands Agents documentation.

## Available Tools:
- `search_documentation`: Search through all documentation with advanced relevance scoring
- `get_documentation_sections`: Get overview of available documentation sections

## Search Tips:
- Use specific terms for better results
- Include code-related keywords for API documentation
- Try different phrasings if initial search doesn't return expected results

## Coverage:
- User guides and tutorials
- API reference documentation  
- Code examples and snippets
- Configuration guides
- Best practices and patterns
"""
        
        @self.mcp.resource("strands://docs/health")
        async def health_resource(ctx: Context = None) -> str:
            """
            Health status of the documentation search system.
            """
            try:
                if not self.es:
                    return "❌ Elasticsearch not connected"
                
                # Check connection
                info = self.es.info()
                
                # Check index
                if not self.es.indices.exists(index=self.index_name):
                    return "❌ Documentation index not found"
                
                # Get document count
                count_response = self.es.count(index=self.index_name)
                doc_count = count_response['count']
                
                return f"""
✅ System Status: Healthy
📊 Elasticsearch: Connected (v{info['version']['number']})
📚 Documents Indexed: {doc_count:,}
🔍 Search: Available
"""
            except Exception as e:
                return f"❌ System Status: Error - {str(e)}"

async def create_server():
    """Create and initialize the FastMCP server."""
    elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    
    server = StrandsFastMCPServer(elasticsearch_url)
    
    # Initialize Elasticsearch connection
    connected = await server.setup_elasticsearch()
    if not connected:
        logger.warning("Starting server without Elasticsearch connection")
    
    return server.mcp

def main():
    """Main entry point for the FastMCP server."""
    # Get configuration from environment
    elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    host = os.getenv('HOST', '0.0.0.0')
    # Railway uses PORT environment variable, default to 8000 for local
    port = int(os.getenv('PORT', '8000'))
    
    logger.info("Starting Strands FastMCP Server", host=host, port=port)
    
    # Create server instance
    async def get_server():
        return await create_server()
    
    # Run the server
    mcp = asyncio.run(get_server())
    mcp.run(transport="http", host=host, port=port, path="/mcp")

if __name__ == "__main__":
    main()
