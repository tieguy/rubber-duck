#!/usr/bin/env python3
"""Test the new agent loop locally."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rubber_duck.agent.loop import run_agent_loop


async def main():
    print("Testing agent loop...")
    print("=" * 50)

    # Test simple message
    response = await run_agent_loop("What's on my calendar today?")
    print(f"Response:\n{response}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
