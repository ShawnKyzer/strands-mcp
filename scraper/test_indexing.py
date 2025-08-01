#!/usr/bin/env python3
"""
Test script to isolate the Elasticsearch indexing issue.
"""

import os
from elasticsearch import Elasticsearch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test document
TEST_DOCUMENT = {
    "url": "https://strandsagents.com/test",
    "title": "Test Document",
    "content": "This is a test document to verify Elasticsearch indexing is working.",
    "section": "test",
    "subsection": "test-subsection",
    "headers": "Test Header",
    "code_blocks": "",
    "scraped_at": "2025-08-01T00:00:00Z",
    "version": "1.1.x"
}

def test_elasticsearch_connection():
    """Test basic Elasticsearch connection."""
    elasticsearch_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    print(f"Testing Elasticsearch connection to: {elasticsearch_url}")
    
    try:
        es_client = Elasticsearch([elasticsearch_url])
        if es_client.ping():
            print("Elasticsearch connection successful")
            return es_client
        else:
            print("Elasticsearch ping failed")
            return None
    except Exception as e:
        print(f"Elasticsearch connection failed: {e}")
        return None

def test_index_creation(es_client, index_name="test-index"):
    """Test index creation."""
    try:
        # Delete index if it exists
        if es_client.indices.exists(index=index_name):
            es_client.indices.delete(index=index_name)
            print(f"Deleted existing index: {index_name}")
        
        # Create index
        es_client.indices.create(index=index_name)
        print(f"Created index: {index_name}")
        return True
    except Exception as e:
        print(f"Index creation failed: {e}")
        return False

def test_document_indexing(es_client, index_name="test-index"):
    """Test document indexing."""
    try:
        # Index a single document
        result = es_client.index(
            index=index_name,
            document=TEST_DOCUMENT
        )
        print(f"Document indexing result: {result}")
        
        # Refresh the index to make the document searchable
        es_client.indices.refresh(index=index_name)
        
        # Check document count
        count_result = es_client.count(index=index_name)
        print(f"Document count: {count_result['count']}")
        
        return count_result['count'] > 0
    except Exception as e:
        print(f"Document indexing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("Starting Elasticsearch indexing test...")
    
    # Test connection
    es_client = test_elasticsearch_connection()
    if not es_client:
        return
    
    # Test index creation
    index_name = "strands-agents-docs-test"
    if not test_index_creation(es_client, index_name):
        return
    
    # Test document indexing
    if test_document_indexing(es_client, index_name):
        print("\nAll tests passed! Elasticsearch indexing is working.")
    else:
        print("\nDocument indexing test failed.")
    
    # Clean up
    try:
        if es_client.indices.exists(index=index_name):
            es_client.indices.delete(index=index_name)
            print(f"Cleaned up test index: {index_name}")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    main()
