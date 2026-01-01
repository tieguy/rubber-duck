FROM python:3.11-slim

WORKDIR /app

# Install system dependencies, bd CLI, and uv
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash && \
    pip install uv

# Copy entrypoint and dependency files (for initial uv cache)
COPY entrypoint.sh pyproject.toml uv.lock* ./

# Make entrypoint executable and pre-cache dependencies
RUN chmod +x entrypoint.sh && \
    (uv sync --frozen --no-dev || true)

# The actual code is cloned at runtime via entrypoint.sh
CMD ["./entrypoint.sh"]
