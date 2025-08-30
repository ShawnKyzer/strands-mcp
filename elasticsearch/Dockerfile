FROM docker.elastic.co/elasticsearch/elasticsearch:8.11.1

# Configure Elasticsearch for Railway - use environment variables
ENV discovery.type=single-node
ENV xpack.security.enabled=false
ENV ES_JAVA_OPTS="-Xms512m -Xmx1g"
ENV cluster.name=railway-elasticsearch
ENV network.host=0.0.0.0
ENV http.port=9200
ENV bootstrap.memory_lock=false
ENV action.destructive_requires_name=false

# Create elasticsearch user and data directory
USER root
RUN mkdir -p /usr/share/elasticsearch/data && \
    chown -R elasticsearch:elasticsearch /usr/share/elasticsearch/data

# Switch back to elasticsearch user
USER elasticsearch

# Expose port
EXPOSE 9200

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:9200/_cluster/health || exit 1
