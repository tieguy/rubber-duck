"""Agent module with Anthropic SDK and local tool execution."""

import logging

from rubber_duck.agent.loop import run_agent_loop, generate_nudge
from rubber_duck.agent.tools import execute_tool, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

__all__ = [
    "run_agent_loop",
    "generate_nudge",
    "execute_tool",
    "TOOL_SCHEMAS",
    "process_user_message",
    "generate_nudge_content",
]


async def generate_nudge_content(nudge_config: dict) -> str:
    """Generate nudge content using the new Anthropic agent.

    Args:
        nudge_config: Configuration containing name, context_query, prompt_hint

    Returns:
        Generated nudge message string
    """
    return await generate_nudge(nudge_config)


async def process_user_message(message: str, context: dict | None = None) -> str:
    """Process a user message and generate a response.

    Args:
        message: The user's message text
        context: Optional context (unused, for API compatibility)

    Returns:
        Response message string
    """
    logger.info(f"Processing user message: {message[:50]}...")
    return await run_agent_loop(message)
