"""Claude Agent SDK wrapper for Rubber Duck."""

import logging
import os

logger = logging.getLogger(__name__)

# TODO: Integrate with Letta for memory
# TODO: Integrate with Todoist MCP for task queries


async def generate_nudge_content(nudge_config: dict) -> str:
    """Generate nudge content using Claude Agent SDK.

    Args:
        nudge_config: Configuration containing:
            - name: Nudge identifier
            - context_query: Query for Todoist tasks (e.g., "@asa")
            - prompt_hint: Hint for the LLM about this nudge's focus

    Returns:
        Generated nudge message string
    """
    name = nudge_config.get("name", "unknown")
    context_query = nudge_config.get("context_query", "")
    prompt_hint = nudge_config.get("prompt_hint", "")

    # For MVP, return a placeholder that shows the system is working
    # TODO: Replace with actual Claude Agent SDK call with MCP tools
    logger.info(f"Generating nudge content for '{name}'")

    # Placeholder response - will be replaced with actual agent call
    return (
        f"**{name.title()} Nudge**\n\n"
        f"_This is a placeholder nudge. Agent integration coming soon._\n\n"
        f"Context: {context_query}\n"
        f"Focus: {prompt_hint}"
    )


async def process_user_message(message: str, context: dict | None = None) -> str:
    """Process a user message and generate a response.

    Args:
        message: The user's message text
        context: Optional context from memory/previous conversation

    Returns:
        Response message string
    """
    # TODO: Implement full agent processing with:
    # 1. Check if this is a task capture ("I need to X")
    # 2. Query Letta for relevant memory
    # 3. Use Claude Agent SDK to process and respond
    # 4. Update Letta memory with this exchange

    logger.info(f"Processing user message: {message[:50]}...")

    # Placeholder - echo back for now
    return (
        f"I heard you say: _{message}_\n\n"
        "_Agent processing coming soon. For now I'm just echoing._"
    )
