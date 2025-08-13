#!/usr/bin/env python3
"""
MCP Server for Strands Agents Documentation

This server provides Amazon Q with access to the indexed Strands Agents documentation
via the Model Context Protocol (MCP).
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime

import structlog
from elasticsearch import Elasticsearch
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
    CallToolResult
)
from pydantic import BaseModel

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class SearchQuery(BaseModel):
    """Search query model."""
    query: str
    max_results: Optional[int] = 10
    section_filter: Optional[str] = None


class StrandsDocsMCPServer:
    """MCP Server for Strands Agents documentation."""
    
    def __init__(self, elasticsearch_url: str):
        self.elasticsearch_url = elasticsearch_url
        self.es_client = None
        self.index_name = "strands-agents-docs"
        self.server = Server("strands-agents-docs")
        self.setup_handlers()

    async def setup_elasticsearch(self):
        """Setup Elasticsearch connection."""
        try:
            self.es_client = Elasticsearch([self.elasticsearch_url])
            
            # Wait for Elasticsearch to be ready
            for _ in range(30):
                try:
                    if self.es_client.ping():
                        logger.info("Connected to Elasticsearch", url=self.elasticsearch_url)
                        return
                except:
                    pass
                await asyncio.sleep(1)
            
            raise Exception("Could not connect to Elasticsearch")
            
        except Exception as e:
            logger.error("Failed to setup Elasticsearch", error=str(e))
            raise

    def setup_handlers(self):
        """Setup MCP server handlers."""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources."""
            try:
                return [
                    Resource(
                        uri="strands://docs/search",
                        name="Strands Agents Documentation Search",
                        description="Search through Strands Agents documentation",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="strands://docs/sections",
                        name="Documentation Sections",
                        description="List all available documentation sections",
                        mimeType="application/json"
                    )
                ]
            except Exception as e:
                logger.error("Error listing resources", error=str(e))
                return []

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource."""
            try:
                if uri == "strands://docs/sections":
                    return await self.get_documentation_sections()
                elif uri == "strands://docs/search":
                    return json.dumps({
                        "description": "Use the search_documentation tool to search through Strands Agents documentation",
                        "usage": "Provide a search query to find relevant documentation"
                    })
                else:
                    raise ValueError(f"Unknown resource URI: {uri}")
            except Exception as e:
                logger.error("Error reading resource", uri=uri, error=str(e))
                return json.dumps({"error": f"Failed to read resource: {str(e)}"})

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools."""
            try:
                return [
                    Tool(
                        name="search_documentation",
                        description="Search through Strands Agents documentation",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query for the documentation"
                                },
                                "max_results": {
                                    "type": "integer",
                                    "description": "Maximum number of results to return (default: 10)",
                                    "default": 10
                                },
                                "section_filter": {
                                    "type": "string",
                                    "description": "Filter results by documentation section (optional)"
                                }
                            },
                            "required": ["query"]
                        }
                    ),
                    Tool(
                        name="get_document_by_url",
                        description="Get a specific document by its URL",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "URL of the document to retrieve"
                                }
                            },
                            "required": ["url"]
                        }
                    ),
                    Tool(
                        name="list_sections",
                        description="List all available documentation sections",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    )
                ]
            except Exception as e:
                logger.error("Error listing tools", error=str(e))
                return []

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "search_documentation":
                    return await self.search_documentation(arguments)
                elif name == "get_document_by_url":
                    return await self.get_document_by_url(arguments)
                elif name == "list_sections":
                    return await self.list_sections_tool()
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.error("Error calling tool", tool_name=name, error=str(e))
                return [TextContent(type="text", text=f"Error calling tool {name}: {str(e)}")]

    async def search_documentation(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search through the documentation."""
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 10)
        section_filter = arguments.get("section_filter")
        
        if not query:
            return [TextContent(type="text", text="Error: Query parameter is required")]
        
        try:
            # Build Elasticsearch query
            es_query = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^3", "content^2", "headers^2", "code_blocks"],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            },
                            {
                                "match_phrase": {
                                    "content": {
                                        "query": query,
                                        "boost": 2
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "highlight": {
                    "fields": {
                        "content": {"fragment_size": 150, "number_of_fragments": 3},
                        "title": {},
                        "headers": {}
                    }
                },
                "size": max_results,
                "_source": ["url", "title", "section", "subsection", "content", "headers", "code_blocks"]
            }
            
            # Add section filter if provided
            if section_filter:
                es_query["query"]["bool"]["filter"] = [
                    {"term": {"section": section_filter}}
                ]
            
            response = self.es_client.search(index=self.index_name, body=es_query)
            
            if not response["hits"]["hits"]:
                return [TextContent(type="text", text=f"No results found for query: '{query}'")]
            
            # Format results
            results = []
            results.append(TextContent(
                type="text", 
                text=f"Found {len(response['hits']['hits'])} results for '{query}':\n"
            ))
            
            for i, hit in enumerate(response["hits"]["hits"], 1):
                source = hit["_source"]
                score = hit["_score"]
                
                result_text = f"\n**Result {i}** (Score: {score:.2f})\n"
                result_text += f"**Title:** {source.get('title', 'Untitled')}\n"
                result_text += f"**URL:** {source.get('url', '')}\n"
                result_text += f"**Section:** {source.get('section', 'N/A')} / {source.get('subsection', 'N/A')}\n"
                
                # Add highlights if available
                if "highlight" in hit:
                    highlights = hit["highlight"]
                    if "content" in highlights:
                        result_text += f"**Relevant Content:**\n"
                        for highlight in highlights["content"][:2]:  # Limit to 2 highlights
                            result_text += f"...{highlight}...\n"
                    elif "title" in highlights:
                        result_text += f"**Highlighted Title:** {highlights['title'][0]}\n"
                else:
                    # Fallback to content snippet
                    content = source.get('content', '')
                    if len(content) > 200:
                        content = content[:200] + "..."
                    result_text += f"**Content Preview:** {content}\n"
                
                # Add code blocks if relevant
                code_blocks = source.get('code_blocks', '')
                if code_blocks and query.lower() in code_blocks.lower():
                    result_text += f"**Code Examples Available:** Yes\n"
                
                result_text += "\n" + "-" * 50 + "\n"
                results.append(TextContent(type="text", text=result_text))
            
            return results
            
        except Exception as e:
            logger.error("Search failed", query=query, error=str(e))
            return [TextContent(type="text", text=f"Search failed: {str(e)}")]

    async def get_document_by_url(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get a specific document by URL."""
        url = arguments.get("url", "")
        
        if not url:
            return [TextContent(type="text", text="Error: URL parameter is required")]
        
        try:
            es_query = {
                "query": {
                    "term": {"url": url}
                }
            }
            
            response = self.es_client.search(index=self.index_name, body=es_query)
            
            if not response["hits"]["hits"]:
                return [TextContent(type="text", text=f"No document found for URL: {url}")]
            
            doc = response["hits"]["hits"][0]["_source"]
            
            result_text = f"**Document Details**\n\n"
            result_text += f"**Title:** {doc.get('title', 'Untitled')}\n"
            result_text += f"**URL:** {doc.get('url', '')}\n"
            result_text += f"**Section:** {doc.get('section', 'N/A')} / {doc.get('subsection', 'N/A')}\n"
            result_text += f"**Last Updated:** {doc.get('scraped_at', 'Unknown')}\n\n"
            
            if doc.get('headers'):
                result_text += f"**Headers:** {doc.get('headers')}\n\n"
            
            result_text += f"**Content:**\n{doc.get('content', 'No content available')}\n"
            
            if doc.get('code_blocks'):
                result_text += f"\n**Code Examples:**\n{doc.get('code_blocks')}\n"
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            logger.error("Document retrieval failed", url=url, error=str(e))
            return [TextContent(type="text", text=f"Document retrieval failed: {str(e)}")]

    async def list_sections_tool(self) -> List[TextContent]:
        """List all available documentation sections."""
        try:
            es_query = {
                "aggs": {
                    "sections": {
                        "terms": {
                            "field": "section",
                            "size": 100
                        },
                        "aggs": {
                            "subsections": {
                                "terms": {
                                    "field": "subsection",
                                    "size": 100
                                }
                            }
                        }
                    }
                },
                "size": 0
            }
            
            response = self.es_client.search(index=self.index_name, body=es_query)
            
            sections_text = "**Available Documentation Sections:**\n\n"
            
            for section_bucket in response["aggregations"]["sections"]["buckets"]:
                section = section_bucket["key"]
                doc_count = section_bucket["doc_count"]
                sections_text += f"**{section}** ({doc_count} documents)\n"
                
                for subsection_bucket in section_bucket["subsections"]["buckets"]:
                    subsection = subsection_bucket["key"]
                    sub_count = subsection_bucket["doc_count"]
                    if subsection:  # Only show non-empty subsections
                        sections_text += f"  - {subsection} ({sub_count} documents)\n"
                
                sections_text += "\n"
            
            return [TextContent(type="text", text=sections_text)]
            
        except Exception as e:
            logger.error("Failed to list sections", error=str(e))
            return [TextContent(type="text", text=f"Failed to list sections: {str(e)}")]

    async def get_documentation_sections(self) -> str:
        """Get documentation sections as JSON."""
        try:
            es_query = {
                "aggs": {
                    "sections": {
                        "terms": {
                            "field": "section",
                            "size": 100
                        },
                        "aggs": {
                            "subsections": {
                                "terms": {
                                    "field": "subsection",
                                    "size": 100
                                }
                            }
                        }
                    }
                },
                "size": 0
            }
            
            response = self.es_client.search(index=self.index_name, body=es_query)
            
            sections = {}
            for section_bucket in response["aggregations"]["sections"]["buckets"]:
                section = section_bucket["key"]
                sections[section] = {
                    "document_count": section_bucket["doc_count"],
                    "subsections": []
                }
                
                for subsection_bucket in section_bucket["subsections"]["buckets"]:
                    subsection = subsection_bucket["key"]
                    if subsection:
                        sections[section]["subsections"].append({
                            "name": subsection,
                            "document_count": subsection_bucket["doc_count"]
                        })
            
            return json.dumps(sections, indent=2)
            
        except Exception as e:
            logger.error("Failed to get sections", error=str(e))
            return json.dumps({"error": str(e)})

    async def run(self):
        """Run the MCP server."""
        logger.info("Starting Strands Agents MCP Server")
        
        try:
            await self.setup_elasticsearch()
            
            # Check if index exists and has documents
            if not self.es_client.indices.exists(index=self.index_name):
                logger.warning("Elasticsearch index does not exist", index=self.index_name)
            else:
                doc_count = self.es_client.count(index=self.index_name)["count"]
                logger.info("Index ready", index=self.index_name, document_count=doc_count)
            
            # Run the MCP server using stdin/stdout
            from mcp.server.stdio import stdio_server
            
            async with stdio_server() as (read_stream, write_stream):
                logger.info("MCP Server running on stdin/stdout")
                await self.server.run(
                    read_stream, 
                    write_stream,
                    InitializationOptions(
                        server_name="strands-agents-docs",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
                
        except KeyboardInterrupt:
            logger.info("MCP Server stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error("MCP Server failed", 
                        error=str(e), 
                        error_type=type(e).__name__,
                        traceback=traceback.format_exc())
            sys.exit(1)


def main():
    """Main entry point for uv script."""
    asyncio.run(async_main())


async def async_main():
    """Async main entry point."""
    elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    
    logger.info("Starting MCP server", elasticsearch_url=elasticsearch_url)
    
    server = StrandsDocsMCPServer(elasticsearch_url)
    await server.run()


if __name__ == "__main__":
    asyncio.run(async_main())
