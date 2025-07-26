#!/usr/bin/env python3
"""
Strands Agents Documentation Scraper

This script scrapes the Strands Agents documentation and indexes it in Elasticsearch
for use with Amazon Q via the MCP server.
"""

import asyncio
import logging
import os
import sys
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import time

import aiohttp
import structlog
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from tenacity import retry, stop_after_attempt, wait_exponential

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


class StrandsDocsScraper:
    """Scraper for Strands Agents documentation."""
    
    def __init__(self, base_url: str, elasticsearch_url: str):
        self.base_url = base_url.rstrip('/')
        self.elasticsearch_url = elasticsearch_url
        self.es_client = None
        self.session = None
        self.scraped_urls = set()
        self.index_name = "strands-agents-docs"
        
        # Known working URLs from navigation
        self.target_sections = [
            "",  # Main documentation page
            "examples/",
            "api-reference/agent/"
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Strands-MCP-Scraper/1.0'}
        )
        await self.setup_elasticsearch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def setup_elasticsearch(self):
        """Setup Elasticsearch connection and index."""
        try:
            self.es_client = Elasticsearch([self.elasticsearch_url])
            
            # Wait for Elasticsearch to be ready
            for _ in range(30):  # 30 second timeout
                try:
                    if self.es_client.ping():
                        break
                except:
                    pass
                await asyncio.sleep(1)
            else:
                raise Exception("Elasticsearch not ready after 30 seconds")
            
            # Create index with mapping
            index_mapping = {
                "mappings": {
                    "properties": {
                        "url": {"type": "keyword"},
                        "title": {"type": "text", "analyzer": "standard"},
                        "content": {"type": "text", "analyzer": "standard"},
                        "section": {"type": "keyword"},
                        "subsection": {"type": "keyword"},
                        "headers": {"type": "text", "analyzer": "standard"},
                        "code_blocks": {"type": "text", "analyzer": "keyword"},
                        "scraped_at": {"type": "date"},
                        "version": {"type": "keyword"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            if self.es_client.indices.exists(index=self.index_name):
                self.es_client.indices.delete(index=self.index_name)
                logger.info("Deleted existing index", index=self.index_name)
            
            self.es_client.indices.create(index=self.index_name, body=index_mapping)
            logger.info("Created Elasticsearch index", index=self.index_name)
            
        except Exception as e:
            logger.error("Failed to setup Elasticsearch", error=str(e))
            raise

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page content."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning("Failed to fetch page", url=url, status=response.status)
                    return None
        except Exception as e:
            logger.error("Error fetching page", url=url, error=str(e))
            return None

    def extract_sections_from_spa(self, html: str, url: str) -> List[Dict]:
        """Extract multiple sections from single-page application HTML."""
        soup = BeautifulSoup(html, 'lxml')
        documents = []
        
        # Remove navigation and footer elements
        for element in soup.find_all(['nav', 'footer', 'header', '.navigation']):
            element.decompose()
        
        # Find the main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if not main_content:
            main_content = soup.find('body')
        
        # Remove scripts and styles
        for script in main_content(["script", "style"]):
            script.decompose()
        
        # Extract the main overview document
        main_title = "Strands Agents SDK Documentation"
        title_elem = soup.find('h1')
        if title_elem:
            main_title = title_elem.get_text().strip()
        elif soup.title:
            main_title = soup.title.get_text().strip()
        
        # Get all text content for the main document
        full_content = main_content.get_text()
        full_content = ' '.join(full_content.split())
        
        # Extract all headers for navigation structure
        all_headers = []
        for header in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            header_text = header.get_text().strip()
            if header_text and len(header_text) > 1:
                all_headers.append(header_text)
        
        # Extract all code blocks
        all_code_blocks = []
        for code in main_content.find_all(['code', 'pre']):
            code_text = code.get_text().strip()
            if len(code_text) > 10:  # Only meaningful code blocks
                all_code_blocks.append(code_text)
        
        # Create main document with all content
        main_doc = {
            "url": url,
            "title": main_title,
            "content": full_content,
            "section": "main",
            "subsection": "overview",
            "headers": " | ".join(all_headers),
            "code_blocks": " | ".join(all_code_blocks),
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": "1.1.x"
        }
        documents.append(main_doc)
        
        # Try to extract logical sections based on content structure
        sections_content = self.extract_logical_sections(main_content)
        for section_data in sections_content:
            section_doc = {
                "url": f"{url}#{section_data['id']}",
                "title": section_data['title'],
                "content": section_data['content'],
                "section": section_data['section'],
                "subsection": section_data['subsection'],
                "headers": " | ".join(section_data['headers']),
                "code_blocks": " | ".join(section_data['code_blocks']),
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "version": "1.1.x"
            }
            documents.append(section_doc)
        
        return documents
    
    def extract_logical_sections(self, main_content) -> List[Dict]:
        """Extract logical sections from the main content based on headers and structure."""
        sections = []
        
        # Define section mappings based on observed navigation structure
        section_keywords = {
            'quickstart': ['quickstart', 'getting started', 'installation'],
            'agents': ['agent', 'create agent', 'agent loop'],
            'tools': ['tools', 'python tools', 'mcp', 'example tools'],
            'model-providers': ['model provider', 'bedrock', 'anthropic', 'openai', 'ollama'],
            'streaming': ['streaming', 'async', 'callback'],
            'multi-agent': ['multi-agent', 'agent2agent', 'swarm', 'graph', 'workflow'],
            'safety': ['safety', 'security', 'responsible', 'guardrails'],
            'observability': ['observability', 'evaluation', 'metrics', 'traces', 'logs'],
            'deployment': ['deploy', 'production', 'lambda', 'fargate']
        }
        
        # Find all paragraphs and headers
        content_blocks = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'section'])
        
        current_section = None
        current_content = []
        current_headers = []
        current_codes = []
        
        for block in content_blocks:
            block_text = block.get_text().strip()
            if not block_text or len(block_text) < 10:
                continue
            
            # Check if this block indicates a new section
            block_lower = block_text.lower()
            detected_section = None
            
            for section_name, keywords in section_keywords.items():
                if any(keyword in block_lower for keyword in keywords):
                    detected_section = section_name
                    break
            
            # If we detected a new section and have accumulated content, save it
            if detected_section and detected_section != current_section and current_content:
                if current_section:
                    sections.append({
                        'id': current_section,
                        'title': f"Strands Agents - {current_section.replace('-', ' ').title()}",
                        'content': ' '.join(current_content),
                        'section': current_section,
                        'subsection': '',
                        'headers': current_headers,
                        'code_blocks': current_codes
                    })
                
                # Start new section
                current_section = detected_section
                current_content = []
                current_headers = []
                current_codes = []
            
            # Add content to current section
            if block.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                current_headers.append(block_text)
            
            # Check for code blocks within this block
            for code in block.find_all(['code', 'pre']):
                code_text = code.get_text().strip()
                if len(code_text) > 10:
                    current_codes.append(code_text)
            
            current_content.append(block_text)
        
        # Add the last section if any
        if current_section and current_content:
            sections.append({
                'id': current_section,
                'title': f"Strands Agents - {current_section.replace('-', ' ').title()}",
                'content': ' '.join(current_content),
                'section': current_section,
                'subsection': '',
                'headers': current_headers,
                'code_blocks': current_codes
            })
        
        return sections
    
    def extract_content(self, html: str, url: str) -> Dict:
        """Extract structured content from HTML (for non-SPA pages)."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove navigation and footer elements
        for element in soup.find_all(['nav', 'footer', 'header', '.navigation']):
            element.decompose()
        
        # Extract title
        title = ""
        title_elem = soup.find('h1')
        if title_elem:
            title = title_elem.get_text().strip()
        elif soup.title:
            title = soup.title.get_text().strip()
        
        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if not main_content:
            main_content = soup.find('body')
        
        # Extract headers
        headers = []
        for header in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            headers.append(header.get_text().strip())
        
        # Extract code blocks
        code_blocks = []
        for code in main_content.find_all(['code', 'pre']):
            code_text = code.get_text().strip()
            if len(code_text) > 10:  # Only meaningful code blocks
                code_blocks.append(code_text)
        
        # Extract clean text content
        for script in main_content(["script", "style"]):
            script.decompose()
        
        content = main_content.get_text()
        # Clean up whitespace
        content = ' '.join(content.split())
        
        # Determine section and subsection from URL
        url_path = urlparse(url).path
        path_parts = [p for p in url_path.split('/') if p]
        
        section = ""
        subsection = ""
        if len(path_parts) >= 4:  # /latest/documentation/docs/section/
            section = path_parts[3] if len(path_parts) > 3 else ""
            subsection = path_parts[4] if len(path_parts) > 4 else ""
        
        return {
            "url": url,
            "title": title,
            "content": content,
            "section": section,
            "subsection": subsection,
            "headers": " | ".join(headers),
            "code_blocks": " | ".join(code_blocks),
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": "1.1.x"
        }

    async def discover_documentation_urls(self, html: str) -> List[str]:
        """Discover actual documentation URLs from the main page."""
        soup = BeautifulSoup(html, 'lxml')
        discovered_urls = set()
        
        # Look for navigation links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/'):
                # Convert relative URLs to absolute
                full_url = urljoin(self.base_url, href)
                if '/documentation/docs/' in full_url and full_url != self.base_url:
                    discovered_urls.add(full_url)
        
        return list(discovered_urls)

    async def scrape_all_sections(self) -> List[Dict]:
        """Scrape all target documentation sections."""
        documents = []
        
        # First scrape the main documentation page
        main_url = self.base_url
        logger.info("Scraping main documentation page", url=main_url)
        
        html = await self.fetch_page(main_url)
        if html:
            # Extract multiple sections from the SPA main page
            spa_docs = self.extract_sections_from_spa(html, main_url)
            documents.extend(spa_docs)
            self.scraped_urls.add(main_url)
            logger.info("Extracted sections from main SPA page", sections_count=len(spa_docs))
            
            # Discover additional URLs from the main page
            discovered_urls = await self.discover_documentation_urls(html)
            logger.info("Discovered URLs", count=len(discovered_urls), urls=discovered_urls[:5])  # Log first 5
            
            # Add discovered URLs to target sections
            for url in discovered_urls:
                if url not in self.scraped_urls:
                    # Extract section from URL for logging
                    section = url.replace(self.base_url, '').strip('/')
                    logger.info("Scraping discovered section", section=section, url=url)
                    
                    section_html = await self.fetch_page(url)
                    if section_html:
                        section_doc = self.extract_content(section_html, url)
                        documents.append(section_doc)
                        self.scraped_urls.add(url)
                        
                        # Small delay to be respectful
                        await asyncio.sleep(0.5)
        
        # Also scrape the known working sections
        for section in self.target_sections:
            if not section:  # Skip empty string (main page already scraped)
                continue
                
            section_url = urljoin(self.base_url + '/', section)
            if section_url in self.scraped_urls:
                continue
                
            logger.info("Scraping known section", section=section, url=section_url)
            
            html = await self.fetch_page(section_url)
            if html:
                doc = self.extract_content(html, section_url)
                documents.append(doc)
                self.scraped_urls.add(section_url)
                
                # Small delay to be respectful
                await asyncio.sleep(0.5)
        
        logger.info("Scraping completed", total_documents=len(documents))
        return documents

    def index_documents(self, documents: List[Dict]):
        """Index documents in Elasticsearch."""
        if not documents:
            logger.warning("No documents to index")
            return
        
        def doc_generator():
            for i, doc in enumerate(documents):
                try:
                    # Validate document structure
                    if not isinstance(doc, dict):
                        logger.error("Invalid document type", doc_index=i, doc_type=type(doc))
                        continue
                    
                    # Ensure required fields exist
                    if 'url' not in doc:
                        logger.error("Document missing URL", doc_index=i, doc_keys=list(doc.keys()))
                        continue
                    
                    yield {
                        "_index": self.index_name,
                        "_source": doc
                    }
                except Exception as doc_error:
                    logger.error("Error processing document", doc_index=i, error=str(doc_error))
                    continue
        
        try:
            success, failed = bulk(self.es_client, doc_generator(), chunk_size=50)
            logger.info("Indexed documents", success=success, failed=len(failed))
            
            if failed:
                for failure in failed:
                    logger.error("Failed to index document", error=failure)
                logger.error("1 document(s) failed to index.")
                    
        except Exception as e:
            logger.error("Failed to bulk index documents", error=str(e))
            raise

    async def run(self):
        """Run the complete scraping and indexing process."""
        logger.info("Starting Strands Agents documentation scraper")
        
        try:
            # Scrape all documentation
            documents = await self.scrape_all_sections()
            
            if not documents:
                logger.warning("No documents scraped")
                return
            
            # Index in Elasticsearch
            try:
                self.index_documents(documents)
                logger.info("Scraping and indexing completed successfully", 
                           total_docs=len(documents))
            except Exception as index_error:
                logger.error("Indexing failed but scraping succeeded", 
                           error=str(index_error), 
                           scraped_docs=len(documents))
                # Don't exit with error code for indexing failures
                # The MCP server can still work with existing data
            
        except Exception as e:
            logger.error("Scraping failed", error=str(e))
            raise


async def main():
    """Main entry point."""
    base_url = os.getenv('DOCS_BASE_URL', 'https://strandsagents.com/latest/documentation/docs/')
    elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    
    logger.info("Starting scraper", base_url=base_url, elasticsearch_url=elasticsearch_url)
    
    async with StrandsDocsScraper(base_url, elasticsearch_url) as scraper:
        await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
