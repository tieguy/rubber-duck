# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Claude Code subprocess executor.

Runs Claude Code CLI and parses streaming NDJSON output.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Session storage
SESSION_FILE = Path("state/claude_sessions.json")


@dataclass
class ClaudeCodeEvent:
    """Parsed event from Claude Code NDJSON stream."""

    type: str  # "assistant", "tool_use", "tool_result", "result", "error"
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    session_id: str = ""
    raw: dict = field(default_factory=dict)


def parse_ndjson_line(line: str) -> ClaudeCodeEvent | None:
    """Parse a single NDJSON line into a ClaudeCodeEvent."""
    try:
        data = json.loads(line.strip())
    except json.JSONDecodeError:
        return None

    event_type = data.get("type", "")

    # Result event (final)
    if event_type == "result":
        return ClaudeCodeEvent(
            type="result",
            text=data.get("result", ""),
            session_id=data.get("session_id", ""),
            raw=data,
        )

    # Assistant message with content blocks
    if event_type == "assistant":
        message = data.get("message", {})
        content = message.get("content", [])

        for block in content:
            block_type = block.get("type", "")

            if block_type == "text":
                return ClaudeCodeEvent(
                    type="assistant",
                    text=block.get("text", ""),
                    raw=data,
                )

            if block_type == "tool_use":
                return ClaudeCodeEvent(
                    type="tool_use",
                    tool_name=block.get("name", ""),
                    tool_id=block.get("id", ""),
                    raw=data,
                )

    # Error event
    if event_type == "error":
        return ClaudeCodeEvent(
            type="error",
            text=data.get("error", {}).get("message", str(data)),
            raw=data,
        )

    return None


@dataclass
class ClaudeCodeCallbacks:
    """Callbacks for Claude Code execution progress."""

    on_tool_start: Callable[[str], Awaitable[None]] | None = None
    on_tool_end: Callable[[str, bool], Awaitable[None]] | None = None
    on_text: Callable[[str], Awaitable[None]] | None = None


async def stream_claude_code(
    prompt: str,
    system_prompt: str = "",
    session_id: str | None = None,
    callbacks: ClaudeCodeCallbacks | None = None,
) -> AsyncIterator[ClaudeCodeEvent]:
    """Stream events from Claude Code CLI.

    Args:
        prompt: User message
        system_prompt: Additional system prompt content
        session_id: Optional session ID to resume
        callbacks: Optional callbacks for progress reporting

    Yields:
        ClaudeCodeEvent objects as they arrive
    """
    cmd = [
        "claude",
        "-p", prompt,
        "--verbose",
        "--output-format", "stream-json",
        "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
    ]

    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])

    if session_id:
        cmd.extend(["--resume", session_id])

    logger.info(f"Running Claude Code: {' '.join(cmd[:6])}...")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(Path(__file__).parent.parent.parent.parent),  # repo root
    )

    current_tool: str | None = None

    async for line in process.stdout:
        line_str = line.decode("utf-8").strip()
        if not line_str:
            continue

        event = parse_ndjson_line(line_str)
        if not event:
            continue

        # Handle tool lifecycle callbacks
        if event.type == "tool_use":
            if current_tool and callbacks and callbacks.on_tool_end:
                await callbacks.on_tool_end(current_tool, True)
            current_tool = event.tool_name
            if callbacks and callbacks.on_tool_start:
                await callbacks.on_tool_start(event.tool_name)

        # Handle text streaming
        if event.type == "assistant" and event.text:
            if callbacks and callbacks.on_text:
                await callbacks.on_text(event.text)

        yield event

    # Clean up final tool
    if current_tool and callbacks and callbacks.on_tool_end:
        await callbacks.on_tool_end(current_tool, True)

    # Read any stderr output
    stderr_output = await process.stderr.read()
    if stderr_output:
        logger.warning(f"Claude Code stderr: {stderr_output.decode('utf-8')}")

    exit_code = await process.wait()
    if exit_code != 0:
        logger.warning(f"Claude Code exited with code {exit_code}")


async def run_claude_code(
    prompt: str,
    system_prompt: str = "",
    session_id: str | None = None,
    callbacks: ClaudeCodeCallbacks | None = None,
) -> tuple[str, str | None]:
    """Run Claude Code and return final response.

    Args:
        prompt: User message
        system_prompt: Additional system prompt content
        session_id: Optional session ID to resume
        callbacks: Optional callbacks for progress reporting

    Returns:
        Tuple of (response_text, new_session_id)
    """
    result_text = ""
    new_session_id = None

    async for event in stream_claude_code(prompt, system_prompt, session_id, callbacks):
        if event.type == "result":
            result_text = event.text
            new_session_id = event.session_id
        elif event.type == "error":
            result_text = f"Error: {event.text}"

    return result_text, new_session_id


def load_session(channel_id: int) -> str | None:
    """Load session ID for a channel."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text())
        return data.get(str(channel_id))
    except Exception as e:
        logger.debug(f"Could not load session: {e}")
        return None


def save_session(channel_id: int, session_id: str) -> None:
    """Save session ID for a channel."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
        except Exception as e:
            logger.debug(f"Could not load session: {e}")
    data[str(channel_id)] = session_id
    SESSION_FILE.write_text(json.dumps(data, indent=2))


def build_system_prompt(memory_blocks: dict) -> str:
    """Build system prompt from Letta memory blocks.

    This is appended to Claude Code's default system prompt.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M %Z")

    return f"""Current time: {current_time}

## About the Owner
{memory_blocks.get('persona', 'Learning about them.')}

## Observed Patterns
{memory_blocks.get('patterns', 'Still observing.')}

## Current Focus
{memory_blocks.get('current_focus', 'No specific focus set.')}

## Communication Style
{memory_blocks.get('communication', 'Be concise and actionable.')}

## Guidelines
{memory_blocks.get('guidelines', 'Help stay organized using GTD principles.')}

## Available Tools
You have skills for Todoist tasks, Google Calendar, and memory operations.
Use them when the user asks about tasks, schedule, or wants to remember something.

For task operations, prefer the todoist skill over direct file manipulation.
For past context, use the memory skill to search archival memory.

## Journal
Conversation history is in state/journal.jsonl (JSONL format, one entry per line).
Use Grep to search for past conversations, decisions, or context.
"""
