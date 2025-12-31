"""Agent loop for Rubber Duck using Anthropic SDK.

Implements the Strix-style agent pattern:
1. Load context from Letta memory blocks
2. Call Anthropic with tools
3. Execute tool calls locally
4. Return response (or loop for more tools)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from anthropic import AsyncAnthropic

from rubber_duck.agent.tools import TOOL_SCHEMAS, execute_tool
from rubber_duck.agent.utils import run_async

logger = logging.getLogger(__name__)

# Model configuration
MODEL = "claude-opus-4-5-20251101"  # Opus 4.5 for best reasoning
MAX_TOOL_CALLS = 20
TIMEOUT = 60

# Journal for unified logging
JOURNAL_PATH = "state/journal.jsonl"
RECENT_CONTEXT_LIMIT = 3  # Number of recent exchanges to inject as context


def _get_recent_context() -> list[dict]:
    """Read recent conversation turns from journal for context.

    Returns list of message dicts suitable for Anthropic messages API.
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    journal = repo_root / JOURNAL_PATH

    if not journal.exists():
        return []

    try:
        with open(journal) as f:
            lines = f.readlines()

        # Get recent entries (user_message and assistant_message only)
        messages = []
        for line in lines[-20:]:  # Look at last 20 entries to find recent exchanges
            try:
                entry = json.loads(line.strip())
                if entry.get("type") == "user_message":
                    content = entry.get("content", "")
                    if content:
                        messages.append({"role": "user", "content": content})
                elif entry.get("type") == "assistant_message":
                    content = entry.get("content", "")
                    if content:
                        messages.append({"role": "assistant", "content": content})
            except json.JSONDecodeError:
                continue

        # Return last N exchanges (user + assistant pairs)
        # Ensure we start with a user message and alternate properly
        recent = messages[-(RECENT_CONTEXT_LIMIT * 2):]

        # Validate message alternation (Anthropic requires user/assistant/user/...)
        if not recent:
            return []

        # Find first user message to start from
        start_idx = 0
        for i, msg in enumerate(recent):
            if msg["role"] == "user":
                start_idx = i
                break

        validated = []
        expected_role = "user"
        for msg in recent[start_idx:]:
            if msg["role"] == expected_role:
                validated.append(msg)
                expected_role = "assistant" if expected_role == "user" else "user"

        # Must end with assistant message (so we can add new user message)
        if validated and validated[-1]["role"] == "user":
            validated = validated[:-1]

        return validated

    except Exception as e:
        logger.warning(f"Could not read journal for context: {e}")
        return []


def _log_to_journal(event_type: str, data: dict) -> None:
    """Append event to journal.jsonl."""
    repo_root = Path(__file__).parent.parent.parent.parent
    journal = repo_root / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "type": event_type,
        **data,
    }

    with open(journal, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _build_system_prompt(memory_blocks: dict) -> str:
    """Build system prompt from Letta memory blocks."""
    return f"""You are Rubber Duck, a helpful executive assistant for your owner.

## Core Identity
{memory_blocks.get('bot_values', 'A friendly, competent assistant.')}

## Communication Style
{memory_blocks.get('communication', 'Be concise and actionable. No fluff.')}

## Guidelines
{memory_blocks.get('guidelines', 'Help the owner stay organized using GTD principles.')}

## About Your Owner
{memory_blocks.get('persona', 'Learning about them.')}

## Observed Patterns
{memory_blocks.get('patterns', 'Still observing.')}

## Current Focus
{memory_blocks.get('current_focus', 'No specific focus set.')}

## Schedule Awareness
{memory_blocks.get('schedule', 'Check calendar for today.')}

## Available State Files
{memory_blocks.get('file_index', 'state/inbox.md, state/today.md, state/insights/')}

## Memory Architecture

You have a three-tier memory system:

**Tier 1 - Core Identity (Memory Blocks)**: Persistent facts loaded at startup.
Update with `set_memory_block` when you learn something that should always be true.
- persona: facts about your owner
- patterns: behavioral patterns you've observed
- current_focus: what owner is working on now

**Tier 2 - Long-Term Memory (Archival)**: Searchable conversation history.
- `search_memory(query)`: Find past conversations, insights, context
- `archive_to_memory(content)`: Save important information for later
- Archive insights, decisions, preferences, project context

**Tier 3 - Working Memory (Journal + Files)**: Recent session context.
- `read_journal(limit)`: See recent conversations in this session
- `read_file("state/inbox.md")`: Unprocessed captures
- `read_file("state/today.md")`: Current priorities

## Key Principles
- You automatically receive the last few conversation turns as context
- For longer-term memory, archive important information to Tier 2
- Search archival memory when asked about past conversations
- Update memory blocks for persistent identity changes
- Commit important file changes to git for provenance

## Tools
- File ops: read_file, write_file, edit_file, list_directory
- Git: git_status, git_commit, git_push, git_pull
- Self-modify: edit_file (for code changes), git_commit, git_push, restart_self (ONLY after git_push to reload code)
- Issues: bd_ready, bd_show, bd_update, bd_close, bd_sync, bd_create
- Memory: get_memory_blocks, set_memory_block, search_memory, archive_to_memory, read_journal
- Tasks: query_todoist, create_todoist_task, complete_todoist_task
- Calendar: query_gcal
- GTD: run_morning_planning, run_weekly_review
"""


def _get_memory_blocks() -> dict:
    """Load memory blocks from Letta."""
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    try:
        client = get_client()
        if not client:
            return {}

        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return {}

        block_list = client.agents.blocks.list(agent_id=agent_id)
        blocks = {}
        for block in block_list:
            label = getattr(block, 'label', None) or getattr(block, 'name', 'unknown')
            value = getattr(block, 'value', '') or getattr(block, 'content', '')
            blocks[label] = value
        return blocks
    except Exception as e:
        logger.warning(f"Could not load memory blocks: {e}")
        return {}


async def run_agent_loop(user_message: str, context: str = "") -> str:
    """Run the agent loop for a user message.

    Args:
        user_message: The user's message
        context: Optional additional context

    Returns:
        Agent's response text
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "I'm not properly configured. ANTHROPIC_API_KEY is missing."

    client = AsyncAnthropic(api_key=api_key)

    # Load memory blocks for system prompt
    memory_blocks = _get_memory_blocks()
    system_prompt = _build_system_prompt(memory_blocks)

    # Build initial message
    if context:
        full_message = f"[Context: {context}]\n\n{user_message}"
    else:
        full_message = user_message

    # Start with recent conversation context from journal
    messages = _get_recent_context()
    messages.append({"role": "user", "content": full_message})

    # Log user message
    _log_to_journal("user_message", {"content": user_message, "context": context})

    tool_calls = 0

    while tool_calls < MAX_TOOL_CALLS:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except Exception as e:
            logger.exception(f"Anthropic API error: {e}")
            return "I encountered an error communicating with my brain. Please try again."

        # Check for tool use
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if not tool_use_blocks:
            # No tools, we have final response
            final_text = "\n".join(b.text for b in text_blocks)
            _log_to_journal("assistant_message", {"content": final_text})
            return final_text

        # Execute tools
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input

            # Validate tool_input is a dict before calling execute_tool
            if not isinstance(tool_input, dict):
                tool_input = {}

            _log_to_journal("tool_call", {"tool": tool_name, "args": tool_input})

            result = execute_tool(tool_name, tool_input)

            result_log = result[:500] + ("..." if len(result) > 500 else "")
            _log_to_journal("tool_result", {"tool": tool_name, "result": result_log})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result,
            })
            tool_calls += 1

        messages.append({"role": "user", "content": tool_results})

        # Check stop reason
        if response.stop_reason == "end_turn":
            final_text = "\n".join(b.text for b in text_blocks)
            _log_to_journal("assistant_message", {"content": final_text})
            return final_text

    return "I've made too many tool calls. Let me know what else you need."


async def generate_nudge(nudge_config: dict) -> str:
    """Generate a nudge message using the agent.

    Args:
        nudge_config: Nudge configuration with name, context_query, prompt_hint

    Returns:
        Generated nudge message
    """
    name = nudge_config.get("name", "unknown")
    context_query = nudge_config.get("context_query", "")
    prompt_hint = nudge_config.get("prompt_hint", "")

    prompt = f"""Generate a {name} nudge for the owner.

Focus: {prompt_hint}

Query Todoist with filter "{context_query}" if relevant, then write a brief,
friendly nudge (2-3 sentences). Be specific if there are tasks. Don't be preachy."""

    return await run_agent_loop(prompt, context=f"Scheduled nudge: {name}")
