"""Entry point for Rubber Duck bot."""

import asyncio
import logging
import sys

from rubber_duck.bot import run_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point."""
    logger.info("Starting Rubber Duck...")

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
