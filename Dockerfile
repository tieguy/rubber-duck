FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (git, curl for bd install)
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

# Install bd CLI (script installs directly to /usr/local/bin)
RUN curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash

# Install uv for fast dependency management
RUN pip install uv

# Copy entrypoint and dependency files (for initial uv cache)
COPY entrypoint.sh pyproject.toml uv.lock* ./
RUN chmod +x entrypoint.sh

# Pre-cache dependencies (speeds up startup)
RUN uv sync --frozen --no-dev || true

# The actual code is cloned at runtime via entrypoint.sh
CMD ["./entrypoint.sh"]
