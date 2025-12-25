FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ src/
COPY config/ config/

# Run the bot
CMD ["uv", "run", "python", "-m", "rubber_duck"]
