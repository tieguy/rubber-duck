# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

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
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from anthropic import AsyncAnthropic

from rubber_duck.agent.tools import TOOL_SCHEMAS, execute_tool
from rubber_duck.agent.utils import run_async


@dataclass
class AgentCallbacks:
    """Callbacks for interactive agent progress reporting.

    All callbacks are optional. If not provided, the agent runs silently.
    """

    on_tool_start: Callable[[str], Awaitable[None]] | None = None  # tool name
    on_tool_end: Callable[[str, bool], Awaitable[None]] | None = None  # tool name, success
    check_cancelled: Callable[[], Awaitable[bool]] | None = None  # returns True if cancelled
    on_checkpoint: Callable[[int], Awaitable[bool]] | None = None  # tools used → continue?

logger = logging.getLogger(__name__)

# Model configuration
MODEL_OPUS = "claude-opus-4-5-20251101"  # Best reasoning, use for quality interactions
MODEL_SONNET = "claude-sonnet-4-20250514"  # Fast execution, use for simple tasks
MAX_TOOL_CALLS = 20
MAX_TOOL_CALLS_SIMPLE = 5  # Tighter limit for simple operations
TIMEOUT = 60

# Patterns for simple execution tasks (use Sonnet)
# These use re.search so they can match anywhere in the message
SIMPLE_TASK_PATTERNS = [
    r"\b(complete|close|finish|done|check off|mark.{0,20}done)\b",  # Task completion
    r"\b(add|create|make)\s+(a\s+)?(task|todo|reminder)\b",  # Task creation
    r"^(yes|no|ok|sure|yep|nope|do it|go ahead|sounds good)\b",  # Confirmations
    r"^query\s+",  # Raw queries
]


def _is_simple_task(user_message: str) -> bool:
    """Check if message matches simple task patterns."""
    msg_lower = user_message.lower().strip()
    return any(re.search(pattern, msg_lower) for pattern in SIMPLE_TASK_PATTERNS)


def _select_model(user_message: str, is_nudge: bool = False) -> str:
    """Select model based on task complexity.

    Uses Opus for quality interactions (nudges, advice, planning).
    Uses Sonnet for pure execution (complete task, add task, raw queries).
    """
    if is_nudge:
        return MODEL_OPUS  # Nudges always need quality thinking

    if _is_simple_task(user_message):
        return MODEL_SONNET

    # Default to Opus for everything else (advice, questions, show/list, etc.)
    return MODEL_OPUS

# Journal for unified logging
JOURNAL_PATH = "state/journal.jsonl"
RECENT_CONTEXT_LIMIT = 3  # Number of recent exchanges to inject as context


def _parse_journal_entry(line: str) -> dict | None:
    """Parse a single journal line into a message dict if valid."""
    try:
        entry = json.loads(line.strip())
        entry_type = entry.get("type")
        content = entry.get("content", "")

        if entry_type == "user_message" and content:
            return {"role": "user", "content": content}
        elif entry_type == "assistant_message" and content:
            return {"role": "assistant", "content": content}
    except json.JSONDecodeError:
        pass
    return None


def _validate_message_alternation(messages: list[dict]) -> list[dict]:
    """Ensure messages alternate user/assistant and end with assistant."""
    if not messages:
        return []

    # Find first user message
    start_idx = next(
        (i for i, msg in enumerate(messages) if msg["role"] == "user"),
        len(messages)
    )

    # Build validated list with proper alternation
    validated = []
    expected_role = "user"
    for msg in messages[start_idx:]:
        if msg["role"] == expected_role:
            validated.append(msg)
            expected_role = "assistant" if expected_role == "user" else "user"

    # Must end with assistant (so we can add new user message)
    if validated and validated[-1]["role"] == "user":
        validated = validated[:-1]

    return validated


def _get_recent_context() -> list[dict]:
    """Read recent conversation turns from journal for context.

    Returns list of message dicts suitable for Anthropic messages API.
    Only includes user_message and assistant_message entries, not tool calls.
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    journal = repo_root / JOURNAL_PATH

    if not journal.exists():
        return []

    try:
        with open(journal) as f:
            lines = f.readlines()

        # Parse entries from end, collecting only user/assistant messages
        # Read more lines since tool_call/tool_result entries are filtered out
        messages = []
        for line in reversed(lines[-200:]):  # Check last 200 lines
            msg = _parse_journal_entry(line)
            if msg:
                messages.append(msg)
                # Stop once we have enough messages
                if len(messages) >= RECENT_CONTEXT_LIMIT * 2 + 2:
                    break

        # Reverse back to chronological order
        messages.reverse()

        # Get last N exchanges and validate alternation
        recent = messages[-(RECENT_CONTEXT_LIMIT * 2):]
        return _validate_message_alternation(recent)

    except Exception as e:
        logger.warning(f"Could not read journal for context: {e}")
        return []


def _log_to_journal(event_type: str, data: dict) -> None:
    """Append event to journal.jsonl."""
    repo_root = Path(__file__).parent.parent.parent.parent
    journal = repo_root / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        **data,
    }

    with open(journal, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _build_system_prompt(memory_blocks: dict) -> str:
    """Build system prompt from Letta memory blocks."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M %Z")
    return f"""Current time: {current_time}

You are Rubber Duck, a helpful executive assistant for your owner.

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

## Efficiency Guidelines
- For simple task operations (complete, add, query), use ONLY the required tool and respond immediately
- Don't search memory, update blocks, or archive for routine task operations
- Minimize tool calls - each one costs time and money
- If you can answer from context, don't call tools

## Tools

**Personal Tasks (Todoist)** - Owner's personal task management:
- query_todoist, create_todoist_task, complete_todoist_task

**Code Issues (bd)** - Development issues for THIS BOT's codebase only:
- bd_ready, bd_show, bd_update, bd_close, bd_sync, bd_create
- These track bugs/features for rubber-duck itself, NOT personal tasks

**File ops**: read_file, write_file, edit_file, list_directory
**Git**: git_status, git_commit, git_push, git_pull
**Self-modify**: edit_file (for code changes), git_commit, git_push, restart_self (ONLY after git_push to reload code)
**Memory**: get_memory_blocks, set_memory_block, search_memory, archive_to_memory, read_journal
**Calendar**: query_gcal
**GTD workflows**: run_morning_planning, run_weekly_review

## Weekly Review Sessions

When the user wants to do a weekly review, use the weekly_review_conductor to manage the session:

1. Call `weekly_review_conductor("start")` to begin
2. Follow the conductor's guidance - it tells you which tool to call next
3. After each sub-review, discuss the results with the user
4. When user is ready (says "next", "continue", etc.), call `weekly_review_conductor("next")`
5. Handle user requests between steps (add tasks, answer questions) naturally
6. The conductor tracks progress - just follow its instructions
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


def _execute_tool_block(tool_block) -> dict:
    """Execute a single tool block and return the result dict."""
    tool_name = tool_block.name
    tool_input = tool_block.input if isinstance(tool_block.input, dict) else {}

    _log_to_journal("tool_call", {"tool": tool_name, "args": tool_input})

    result = execute_tool(tool_name, tool_input)

    result_log = result[:500] + ("..." if len(result) > 500 else "")
    _log_to_journal("tool_result", {"tool": tool_name, "result": result_log})

    return {
        "type": "tool_result",
        "tool_use_id": tool_block.id,
        "content": result,
    }


def _extract_final_text(text_blocks: list) -> str:
    """Extract and log final response text from text blocks."""
    final_text = "\n".join(b.text for b in text_blocks)
    _log_to_journal("assistant_message", {"content": final_text})
    return final_text


def _tool_succeeded(result: str) -> bool:
    """Check if a tool result indicates success (no error signals)."""
    error_signals = [
        "error:", "failed:", "exception:", "not found", "denied",
        "unauthorized", "timeout", "could not", "unable to",
    ]
    result_lower = result.lower()
    return not any(signal in result_lower for signal in error_signals)


def _is_intent_text(text: str) -> bool:
    """Check if text is announcing intent rather than providing a final response.

    When Claude calls tools, it often says "Let me search..." or "I'll complete that..."
    This is intent text - announcing what it's about to do. We should NOT return this
    as the final response; we need to wait for Claude to see the tool result and respond.
    """
    text = text.strip()
    if not text:
        return True  # Empty text is not a final response

    # Text ending with colon is announcing next action
    if text.endswith(":"):
        return True

    # Check for intent phrases near the end of the text
    # Look at last 100 chars to catch trailing intent
    tail = text[-100:].lower() if len(text) > 100 else text.lower()
    intent_phrases = [
        "let me ",
        "i'll ",
        "i will ",
        "i'm going to ",
        "let's ",
    ]
    return any(phrase in tail for phrase in intent_phrases)


async def run_agent_loop(user_message: str, context: str = "", is_nudge: bool = False) -> str:
    """Run the agent loop for a user message.

    Args:
        user_message: The user's message
        context: Optional additional context
        is_nudge: Whether this is a scheduled nudge (always uses Opus)

    Returns:
        Agent's response text
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "I'm not properly configured. ANTHROPIC_API_KEY is missing."

    client = AsyncAnthropic(api_key=api_key)

    # Select model and determine limits based on task complexity
    is_simple = _is_simple_task(user_message) and not is_nudge
    model = MODEL_SONNET if is_simple else _select_model(user_message, is_nudge=is_nudge)
    max_tools = MAX_TOOL_CALLS_SIMPLE if is_simple else MAX_TOOL_CALLS
    logger.info(f"Using model: {model}, max_tools: {max_tools}, simple: {is_simple}")
    system_prompt = _build_system_prompt(_get_memory_blocks())

    # Build initial message with context
    full_message = f"[Context: {context}]\n\n{user_message}" if context else user_message
    messages = _get_recent_context()
    messages.append({"role": "user", "content": full_message})

    _log_to_journal("user_message", {"content": user_message, "context": context})

    tool_calls = 0
    while tool_calls < max_tools:
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except Exception as e:
            logger.exception(f"Anthropic API error: {e}")
            return "I encountered an error communicating with my brain. Please try again."

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        # No tools means final response
        if not tool_use_blocks:
            return _extract_final_text(text_blocks)

        # Execute all tools and collect results
        tool_results = [_execute_tool_block(block) for block in tool_use_blocks]
        tool_calls += len(tool_results)

        # Success-gated early return: if Claude gave us a final response AND all tools
        # succeeded, return immediately without another LLM call.
        # But skip if the text is just announcing intent ("Let me search...")
        all_succeeded = all(_tool_succeeded(r["content"]) for r in tool_results)
        response_text = "\n".join(b.text for b in text_blocks) if text_blocks else ""
        if text_blocks and all_succeeded and not _is_intent_text(response_text):
            logger.info("Early return: tools succeeded and final response available")
            return _extract_final_text(text_blocks)

        # Otherwise, send results back to Claude for next step
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "I've made too many tool calls. Let me know what else you need."


@dataclass
class ToolStatus:
    """Track tool execution status for progress reporting."""

    name: str
    success: bool | None = None  # None = in progress

    def to_str(self) -> str:
        if self.success is None:
            return f"🔧 {self.name} ..."
        elif self.success:
            return f"🔧 {self.name} ✓"
        else:
            return f"🔧 {self.name} ✗"


def _format_tool_log(tools: list[ToolStatus]) -> str:
    """Format tool status list for display."""
    return "\n".join(t.to_str() for t in tools)


async def run_agent_loop_interactive(
    user_message: str,
    callbacks: AgentCallbacks,
    context: str = "",
) -> str:
    """Run the agent loop with interactive progress reporting.

    Args:
        user_message: The user's message
        callbacks: Callbacks for progress updates and cancellation
        context: Optional additional context

    Returns:
        Agent's response text or cancellation message
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "I'm not properly configured. ANTHROPIC_API_KEY is missing."

    client = AsyncAnthropic(api_key=api_key)

    # Interactive mode always uses Opus and full tool limit
    model = MODEL_OPUS
    logger.info(f"Interactive mode: using {model}")
    system_prompt = _build_system_prompt(_get_memory_blocks())

    # Build initial message with context
    full_message = f"[Context: {context}]\n\n{user_message}" if context else user_message
    messages = _get_recent_context()
    messages.append({"role": "user", "content": full_message})

    _log_to_journal("user_message", {"content": user_message, "context": context})

    tool_calls = 0
    tool_log: list[ToolStatus] = []  # Track all tools for summary

    while True:
        # Check for cancellation before each API call
        if callbacks.check_cancelled and await callbacks.check_cancelled():
            summary = " → ".join(t.to_str() for t in tool_log) if tool_log else "nothing yet"
            return f"Cancelled. Was working on: {summary}"

        # Check if we've hit the checkpoint
        if tool_calls >= MAX_TOOL_CALLS and tool_calls % MAX_TOOL_CALLS == 0:
            if callbacks.on_checkpoint:
                should_continue = await callbacks.on_checkpoint(tool_calls)
                if not should_continue:
                    summary = " → ".join(t.to_str() for t in tool_log)
                    return f"Stopped at checkpoint ({tool_calls} tools). Progress: {summary}"
            else:
                # No checkpoint callback, use old behavior
                return "I've made too many tool calls. Let me know what else you need."

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except Exception as e:
            logger.exception(f"Anthropic API error: {e}")
            return "I encountered an error communicating with my brain. Please try again."

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        # No tools means final response
        if not tool_use_blocks:
            return _extract_final_text(text_blocks)

        # Execute tools with progress callbacks
        tool_results = []
        for block in tool_use_blocks:
            tool_name = block.name

            # Check cancellation before each tool
            if callbacks.check_cancelled and await callbacks.check_cancelled():
                summary = " → ".join(t.to_str() for t in tool_log)
                return f"Cancelled. Was working on: {summary}"

            # Report tool start
            status = ToolStatus(name=tool_name)
            tool_log.append(status)
            if callbacks.on_tool_start:
                await callbacks.on_tool_start(tool_name)

            # Execute tool
            tool_input = block.input if isinstance(block.input, dict) else {}
            _log_to_journal("tool_call", {"tool": tool_name, "args": tool_input})
            result = execute_tool(tool_name, tool_input)
            result_log = result[:500] + ("..." if len(result) > 500 else "")
            _log_to_journal("tool_result", {"tool": tool_name, "result": result_log})

            success = _tool_succeeded(result)
            status.success = success

            # Report tool end
            if callbacks.on_tool_end:
                await callbacks.on_tool_end(tool_name, success)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        tool_calls += len(tool_results)

        # Success-gated early return
        all_succeeded = all(_tool_succeeded(r["content"]) for r in tool_results)
        response_text = "\n".join(b.text for b in text_blocks) if text_blocks else ""
        if text_blocks and all_succeeded and not _is_intent_text(response_text):
            logger.info("Early return: tools succeeded and final response available")
            return _extract_final_text(text_blocks)

        # Continue loop
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


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

    return await run_agent_loop(prompt, context=f"Scheduled nudge: {name}", is_nudge=True)
