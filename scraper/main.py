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

from playwright.async_api import async_playwright
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
        self.playwright = None
        self.browser = None
        self.scraped_urls = set()
        self.index_name = "strands-agents-docs"
        
        # URLs to discover and crawl
        self.discovered_urls = set()
        self.max_depth = 3  # Limit crawling depth
        self.allowed_paths = [
            '/latest/documentation/docs/',
            '/latest/documentation/docs/user-guide/',
            '/latest/documentation/docs/examples/',
            '/latest/documentation/docs/api-reference/',
            '/latest/documentation/docs/deploy/',
            '/latest/documentation/docs/observability/',
            '/latest/documentation/docs/safety/',
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        # Setup Playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']  # Required for Docker
        )
        await self.setup_elasticsearch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

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

    async def fetch_page_with_playwright(self, url: str) -> Optional[str]:
        """Fetch a single page content using Playwright."""
        try:
            page = await self.browser.new_page()
            
            # Navigate to the page
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to be loaded (adjust selector as needed)
            try:
                await page.wait_for_selector('main', timeout=10000)
            except:
                # If main is not found, wait for body content
                await page.wait_for_selector('body', timeout=10000)
            
            # Additional wait for any dynamic content
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(2000)  # 2 second additional wait
            
            # Get the fully rendered HTML
            html = await page.content()
            
            # Optionally, you can also interact with the page here
            # For example, click on expand buttons if needed:
            # expand_buttons = await page.query_selector_all('button.expand')
            # for button in expand_buttons:
            #     await button.click()
            #     await page.wait_for_timeout(500)
            
            await page.close()
            return html
            
        except Exception as e:
            logger.error("Error fetching page with Playwright", url=url, error=str(e))
            return None

    def extract_sections_from_spa(self, html: str, url: str) -> List[Dict]:
        """Extract multiple sections from single-page application HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        documents = []
        
        # First, extract navigation structure to understand available sections
        nav_sections = self.extract_navigation_sections(soup)
        logger.info("Found navigation sections", count=len(nav_sections))
        
        # Find the main content area (preserve navigation for structure analysis)
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if not main_content:
            main_content = soup.find('body')
        
        # Create a copy for processing
        content_soup = BeautifulSoup(str(main_content), 'html.parser')
        
        # Remove scripts and styles but keep structure
        for script in content_soup(["script", "style"]):
            script.decompose()
        
        # Extract comprehensive sections based on headings and content blocks
        sections = self.extract_comprehensive_sections(content_soup, nav_sections)
        
        for section_data in sections:
            if section_data['content'].strip() and len(section_data['content']) > 100:
                doc = {
                    "url": f"{url}#{section_data.get('id', section_data['title'].lower().replace(' ', '-'))}",
                    "title": section_data['title'],
                    "content": section_data['content'],
                    "section": section_data['section'],
                    "subsection": section_data['subsection'],
                    "headers": " | ".join(section_data['headers']),
                    "code_blocks": " | ".join(section_data['code_blocks']),
                    "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "version": "1.1.x"
                }
                documents.append(doc)
        
        logger.info("Extracted SPA sections", total_sections=len(documents))
        return documents
    
    def extract_navigation_sections(self, soup):
        """Extract section information from navigation elements."""
        nav_sections = []
        
        # Look for navigation elements
        nav_selectors = [
            'nav ul li a',
            '.sidebar ul li a', 
            '.navigation ul li a',
            '.menu ul li a',
            '[role="navigation"] ul li a'
        ]
        
        for selector in nav_selectors:
            for link in soup.select(selector):
                text = link.get_text().strip()
                href = link.get('href', '')
                if text and len(text) > 1:
                    nav_sections.append({
                        'title': text,
                        'href': href,
                        'level': len(link.find_parents('ul'))
                    })
        
        return nav_sections
    
    def extract_comprehensive_sections(self, soup, nav_sections):
        """Extract comprehensive sections based on content structure."""
        sections = []
        
        # Find all major headings (h1, h2, h3)
        headings = soup.find_all(['h1', 'h2', 'h3'])
        
        for i, heading in enumerate(headings):
            heading_text = heading.get_text().strip()
            if not heading_text or len(heading_text) < 2:
                continue
                
            # Determine section and subsection based on heading level and nav structure
            section, subsection = self.categorize_heading(heading_text, heading.name, nav_sections)
            
            # Extract content until next heading of same or higher level
            content_elements = []
            current = heading.next_sibling
            
            while current:
                if hasattr(current, 'name'):
                    # Stop at next heading of same or higher level
                    if current.name in ['h1', 'h2', 'h3']:
                        current_level = int(current.name[1])
                        heading_level = int(heading.name[1])
                        if current_level <= heading_level:
                            break
                    
                    # Collect content elements
                    if current.name in ['p', 'div', 'ul', 'ol', 'pre', 'code', 'blockquote']:
                        content_elements.append(current)
                
                current = current.next_sibling
            
            # Extract text content
            content_parts = []
            headers = [heading_text]
            code_blocks = []
            
            for elem in content_elements:
                if elem.name in ['pre', 'code']:
                    code_text = elem.get_text().strip()
                    if len(code_text) > 10:
                        code_blocks.append(code_text)
                elif elem.name in ['h4', 'h5', 'h6']:
                    headers.append(elem.get_text().strip())
                
                text = elem.get_text().strip()
                if text:
                    content_parts.append(text)
            
            content = ' '.join(content_parts)
            
            if content and len(content) > 50:
                sections.append({
                    'title': heading_text,
                    'content': content,
                    'section': section,
                    'subsection': subsection,
                    'headers': headers,
                    'code_blocks': code_blocks,
                    'id': heading.get('id', heading_text.lower().replace(' ', '-'))
                })
        
        # Also extract content blocks that might not have clear headings
        self.extract_additional_content_blocks(soup, sections)
        
        return sections
    
    def categorize_heading(self, heading_text, heading_level, nav_sections):
        """Categorize heading into section and subsection based on navigation structure."""
        heading_lower = heading_text.lower()
        
        # Map common patterns to sections
        section_mappings = {
            'quickstart': ('user-guide', 'quickstart'),
            'concepts': ('user-guide', 'concepts'),
            'agents': ('user-guide', 'agents'),
            'tools': ('user-guide', 'tools'),
            'model providers': ('user-guide', 'model-providers'),
            'streaming': ('user-guide', 'streaming'),
            'multi-agent': ('user-guide', 'multi-agent'),
            'safety': ('user-guide', 'safety'),
            'security': ('user-guide', 'security'),
            'observability': ('user-guide', 'observability'),
            'evaluation': ('user-guide', 'evaluation'),
            'deploy': ('user-guide', 'deploy'),
            'examples': ('examples', 'overview'),
            'api reference': ('api-reference', 'overview'),
            'features': ('main', 'features'),
            'next steps': ('main', 'next-steps')
        }
        
        for pattern, (section, subsection) in section_mappings.items():
            if pattern in heading_lower:
                return section, subsection
        
        # Default categorization based on heading level
        if heading_level == 'h1':
            return 'main', 'overview'
        elif heading_level == 'h2':
            return 'user-guide', heading_text.lower().replace(' ', '-')
        else:
            return 'user-guide', 'concepts'
    
    def extract_additional_content_blocks(self, soup, existing_sections):
        """Extract additional content blocks that might be missed."""
        # Look for content in divs, articles, or sections that might contain documentation
        content_selectors = [
            'article',
            '.content',
            '.documentation',
            '.docs-content',
            'section'
        ]
        
        existing_content = {s['content'][:100] for s in existing_sections}
        
        for selector in content_selectors:
            for element in soup.select(selector):
                text = element.get_text().strip()
                if len(text) > 200 and text[:100] not in existing_content:
                    # This is additional content worth extracting
                    title = "Additional Documentation"
                    title_elem = element.find(['h1', 'h2', 'h3', 'h4'])
                    if title_elem:
                        title = title_elem.get_text().strip()
                    
                    existing_sections.append({
                        'title': title,
                        'content': text,
                        'section': 'additional',
                        'subsection': 'content',
                        'headers': [title],
                        'code_blocks': [],
                        'id': f"additional-{len(existing_sections)}"
                    })

    async def scrape_all_sections(self):
        """Scrape all documentation sections from the SPA main page only."""
        documents = []
        
        logger.info("Scraping main SPA page with Playwright", url=self.base_url)
        html = await self.fetch_page_with_playwright(self.base_url)
        
        if html:
            # Always treat as SPA and extract comprehensive sections
            logger.info("Extracting comprehensive sections from SPA")
            spa_docs = self.extract_sections_from_spa(html, self.base_url)
            documents.extend(spa_docs)
            
            # Filter out documents with minimal content
            filtered_docs = []
            for doc in documents:
                content = doc.get('content', '').strip()
                if len(content) > 100:  # Only keep docs with substantial content
                    filtered_docs.append(doc)
                else:
                    logger.debug("Filtered out minimal content doc", 
                               title=doc.get('title', 'unknown'),
                               content_length=len(content))
            
            logger.info("SPA scraping completed", 
                       total_sections_found=len(documents),
                       total_documents_kept=len(filtered_docs),
                       filtered_out=len(documents) - len(filtered_docs))
            
            return filtered_docs
        else:
            logger.error("Failed to fetch main SPA page")
            return []

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
        logger.info("Starting Strands Agents documentation scraper with Playwright")
        
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