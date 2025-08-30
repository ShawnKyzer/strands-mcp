FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and UV
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project files (when Railway builds from /scraper root directory)
COPY pyproject.toml uv.lock ./
COPY . ./scraper/

# Install dependencies with UV (using full path to ensure it's found)
RUN /root/.cargo/bin/uv sync

# Install Playwright browsers in the UV environment
RUN /root/.cargo/bin/uv run playwright install chromium

# Set environment variable for Elasticsearch URL
ENV ELASTICSEARCH_URL=http://elasticsearch:9200

# Run scraper with UV (using full path)
CMD ["/root/.cargo/bin/uv", "run", "scraper"]
