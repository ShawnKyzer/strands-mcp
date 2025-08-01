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

# Also configure standard logging to output to console
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        
        # Debug logging to see what navigation sections we found
        logger.info("Navigation sections found", count=len(nav_sections), nav_sections=[ns['title'] for ns in nav_sections[:30]])  # First 30 only
        logger.debug("All navigation sections", nav_sections=nav_sections)  # Full list in debug
        
        return nav_sections
    
    def extract_comprehensive_sections(self, soup, nav_sections):
        """Extract comprehensive sections based on content structure and navigation."""
        sections = []
        
        # Find all major headings (h1, h2, h3)
        headings = soup.find_all(['h1', 'h2', 'h3'])
        logger.info("Headings found in content", count=len(headings), headings=[h.get_text().strip() for h in headings[:10]])
        
        # First, extract sections based on headings (existing approach)
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
                section_data = {
                    'title': heading_text,
                    'content': content,
                    'section': section,
                    'subsection': subsection,
                    'headers': headers,
                    'code_blocks': code_blocks,
                    'id': heading.get('id', heading_text.lower().replace(' ', '-'))
                }
                sections.append(section_data)
                logger.debug("Created section from heading", title=heading_text, content_length=len(content))
        
        # Also extract content blocks that might not have clear headings
        self.extract_additional_content_blocks(soup, sections)
        
        # NEW: Extract sections based on navigation structure
        nav_based_sections = self.extract_navigation_based_sections(soup, nav_sections)
        sections.extend(nav_based_sections)
        
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
    
    def extract_navigation_based_sections(self, soup, nav_sections):
        """Extract sections based on navigation structure by finding corresponding content elements."""
        nav_sections_created = []
        
        # Create a mapping of navigation titles to potential content sections
        logger.debug("Extracting navigation-based sections", nav_sections_count=len(nav_sections))
        
        # For each navigation section, try to find corresponding content
        for i, nav_section in enumerate(nav_sections):
            title = nav_section['title']
            href = nav_section['href']
            
            # Skip version links and other non-content navigation
            if any(skip_word in title.lower() for skip_word in ['0.', '1.']):
                logger.debug("Skipping version link", title=title)
                continue
            
            logger.debug("Processing navigation section", index=i, title=title, href=href)
            
            # Try to find content based on the href anchor
            content_elem = None
            if href and href.startswith('#'):
                # Look for element with matching id
                element_id = href[1:]  # Remove the #
                content_elem = soup.find(id=element_id)
                if content_elem:
                    logger.debug("Found content by ID", title=title, id=element_id)
                else:
                    logger.debug("No content found by ID", title=title, id=element_id)
            else:
                logger.debug("No href or href doesn't start with #", title=title, href=href)
            
            # If no content found by ID, try other approaches
            if not content_elem:
                logger.debug("Trying text matching for", title=title)
                # Look for elements with text matching the navigation title
                # This is a simplified approach - in a real implementation, you might want
                # to be more sophisticated about matching
                for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    heading_text = heading.get_text().strip()
                    if title.lower() in heading_text.lower() or heading_text.lower() in title.lower():
                        content_elem = heading
                        logger.debug("Found content by text match", title=title, heading_text=heading_text)
                        break
                if not content_elem:
                    logger.debug("No content found by text matching", title=title)
            
            # If we found a content element, extract its content
            if content_elem:
                logger.debug("Found content element, extracting content", title=title, element_name=content_elem.name)
                # Extract content starting from this element
                content_parts = []
                headers = [title]
                code_blocks = []
                
                # Start with the element itself
                current = content_elem
                content_length = 0
                
                # Extract content until we hit a sibling heading of same or higher level
                while current and content_length < 5000:  # Limit content size
                    if hasattr(current, 'name'):
                        # Stop at next heading of same or higher level
                        if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            current_level = int(current.name[1]) if current.name[1].isdigit() else 6
                            nav_level = int(content_elem.name[1]) if content_elem.name[1].isdigit() else 1
                            if current != content_elem and current_level <= nav_level:
                                logger.debug("Stopping at heading", current_name=current.name, current_level=current_level, nav_level=nav_level)
                                break
                        
                        # Collect content
                        if current.name in ['p', 'div', 'ul', 'ol', 'pre', 'code', 'blockquote', 'h4', 'h5', 'h6']:
                            text = current.get_text().strip()
                            if text:
                                content_parts.append(text)
                                content_length += len(text)
                                
                                # Collect headers and code blocks
                                if current.name in ['h4', 'h5', 'h6']:
                                    headers.append(text)
                                elif current.name in ['pre', 'code'] and len(text) > 10:
                                    code_blocks.append(text)
                    
                    # Move to next sibling
                    current = current.next_sibling
                
                content = ' '.join(content_parts)
                
                # Only create section if we have substantial content
                if content and len(content) > 100:
                    section_data = {
                        'title': title,
                        'content': content,
                        'section': 'navigation-based',
                        'subsection': title.lower().replace(' ', '-'),
                        'headers': headers,
                        'code_blocks': code_blocks,
                        'id': f"nav-{len(nav_sections_created)}-{title.lower().replace(' ', '-')}",
                    }
                    nav_sections_created.append(section_data)
                    logger.debug("Created navigation-based section", title=title, content_length=len(content))
                else:
                    logger.debug("Content too short or empty", title=title, content_length=len(content) if content else 0)
            else:
                logger.debug("No content element found for navigation section", title=title)
        
        logger.info("Navigation-based sections created", count=len(nav_sections_created))
        return nav_sections_created

    async def scrape_all_sections(self):
        """Scrape all documentation sections from the SPA main page and linked pages."""
        documents = []
        
        logger.info("Scraping main SPA page with Playwright", url=self.base_url)
        html = await self.fetch_page_with_playwright(self.base_url)
        
        if html:
            # Extract sections from the main SPA page
            logger.info("Extracting comprehensive sections from main SPA page")
            spa_docs = self.extract_sections_from_spa(html, self.base_url)
            documents.extend(spa_docs)
            
            # Index documents immediately after extracting from main SPA page
            if spa_docs:
                try:
                    self.index_documents(spa_docs)
                    logger.info("Indexed documents from main SPA page immediately", count=len(spa_docs))
                except Exception as index_error:
                    logger.error("Immediate indexing failed for main SPA page", error=str(index_error))
            
            # Extract navigation sections to get links to other pages
            soup = BeautifulSoup(html, 'html.parser')
            nav_sections = self.extract_navigation_sections(soup)
            
            # Fetch and extract content from navigation-linked pages
            linked_docs = await self.fetch_navigation_linked_pages(nav_sections)
            documents.extend(linked_docs)
            
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def index_documents(self, documents: List[Dict]):
        """Index documents in Elasticsearch."""
        if not documents:
            logger.warning("No documents to index")
            return
        
        # Check if Elasticsearch client is still connected
        try:
            if not self.es_client.ping():
                logger.warning("Elasticsearch connection lost, attempting to reconnect")
                self.setup_elasticsearch()
        except Exception as ping_error:
            logger.warning("Failed to ping Elasticsearch, attempting to reconnect", error=str(ping_error))
            try:
                self.setup_elasticsearch()
            except Exception as setup_error:
                logger.error("Failed to reconnect to Elasticsearch", error=str(setup_error))
                raise
        
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
                logger.error(f"{len(failed)} document(s) failed to index.")
                
        except Exception as e:
            logger.error("Failed to bulk index documents", error=str(e))
            import traceback
            logger.error("Full traceback", traceback=traceback.format_exc())
            raise
    
    async def fetch_navigation_linked_pages(self, nav_sections):
        """Fetch and extract content from navigation-linked pages."""
        documents = []
        
        # Filter navigation sections to get unique URLs that are part of our documentation
        urls_to_fetch = set()
        for nav_section in nav_sections:
            href = nav_section['href']
            title = nav_section['title']
            
            # Skip version links and external links
            if any(skip_word in title.lower() for skip_word in ['0.', '1.']):
                continue
            
            # Only process URLs that are part of our documentation
            if href and 'strandsagents.com' in href and '/documentation/docs/' in href:
                # Convert to absolute URL if needed
                if href.startswith('/'):
                    href = f"https://strandsagents.com{href}"
                urls_to_fetch.add((href, title))
        
        logger.info("Fetching content from navigation-linked pages", count=len(urls_to_fetch))
        
        # Fetch content from each URL
        for url, nav_title in urls_to_fetch:
            try:
                logger.info("Fetching page", url=url, nav_title=nav_title)
                html = await self.fetch_page_with_playwright(url)
                
                if html:
                    # Extract sections from this page
                    page_docs = self.extract_sections_from_spa(html, url)
                    documents.extend(page_docs)
                    
                    # Index documents immediately after fetching each page
                    if page_docs:
                        try:
                            self.index_documents(page_docs)
                            logger.info("Indexed documents from page immediately", url=url, count=len(page_docs))
                        except Exception as index_error:
                            logger.error("Immediate indexing failed for page", url=url, error=str(index_error))
                    
                    logger.info("Extracted sections from page", url=url, sections=len(page_docs))
                else:
                    logger.warning("Failed to fetch page", url=url)
            except Exception as e:
                logger.error("Error fetching page", url=url, error=str(e))
                continue
        
        logger.info("Finished fetching navigation-linked pages", total_documents=len(documents))
        return documents

    async def run(self):
        """Run the complete scraping and indexing process."""
        logger.info("Starting Strands Agents documentation scraper with Playwright")
        
        try:
            # Scrape all documentation (indexing happens immediately during scraping)
            documents = await self.scrape_all_sections()
            
            if not documents:
                logger.warning("No documents scraped")
                return
            
            logger.info("Scraping and indexing completed successfully", 
                       total_docs=len(documents))
            
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