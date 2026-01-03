# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Agent module with Anthropic SDK and local tool execution."""

import logging
import os

from rubber_duck.agent.loop import run_agent_loop, generate_nudge, _get_memory_blocks
from rubber_duck.agent.claude_code import run_claude_code, build_system_prompt
from rubber_duck.agent.tools import execute_tool, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

USE_CLAUDE_CODE = os.environ.get("USE_CLAUDE_CODE", "").lower() in ("1", "true", "yes")

__all__ = [
    "run_agent_loop",
    "generate_nudge",
    "execute_tool",
    "TOOL_SCHEMAS",
    "process_user_message",
    "generate_nudge_content",
]


async def generate_nudge_content(nudge_config: dict) -> str:
    """Generate nudge content.

    Uses Claude Code if USE_CLAUDE_CODE is set, otherwise Anthropic SDK.

    Args:
        nudge_config: Configuration containing name, context_query, prompt_hint

    Returns:
        Generated nudge message string
    """
    if USE_CLAUDE_CODE:
        return await _generate_nudge_claude_code(nudge_config)
    return await generate_nudge(nudge_config)


async def _generate_nudge_claude_code(nudge_config: dict) -> str:
    """Generate nudge content using Claude Code.

    Args:
        nudge_config: Configuration containing name, context_query, prompt_hint

    Returns:
        Generated nudge message string
    """
    name = nudge_config.get("name", "unknown")
    context_query = nudge_config.get("context_query", "")
    prompt_hint = nudge_config.get("prompt_hint", "")

    # Build system prompt from memory blocks
    memory_blocks = _get_memory_blocks()
    system_prompt = build_system_prompt(memory_blocks)

    # Create nudge prompt
    prompt = f"""Generate a {name} nudge for the owner.

Focus: {prompt_hint}

Query Todoist with filter "{context_query}" if relevant, then write a brief,
friendly nudge (2-3 sentences). Be specific if there are tasks. Don't be preachy."""

    response, _ = await run_claude_code(
        prompt=prompt,
        system_prompt=system_prompt,
    )

    return response or f"**{name.title()}** - Time for a check-in!"


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
