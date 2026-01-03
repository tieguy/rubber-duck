# Claude Code Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace direct Anthropic SDK calls with Claude Code subprocess calls to use Max subscription instead of API tokens.

**Architecture:** Hybrid tool model - Claude Code handles file/git/bash/web natively, Python CLI wrappers expose Todoist/Calendar/Memory via Claude Code skills. Sessions are per-task with Letta providing persistent memory.

**Tech Stack:** Python 3.11+, Claude Code CLI, asyncio subprocess, NDJSON parsing

---

## Task 1: Create CLI Entry Point for Tool Wrappers

**Files:**
- Create: `src/rubber_duck/cli/__init__.py`
- Create: `src/rubber_duck/cli/tools.py`
- Test: `tests/test_cli_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_tools.py
"""Tests for CLI tool wrappers."""

import json
import subprocess
import sys


def test_cli_todoist_query_returns_json():
    """CLI todoist query returns valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "todoist", "query", "today"],
        capture_output=True,
        text=True,
    )
    # Should return valid JSON (even if empty or error)
    output = json.loads(result.stdout)
    assert "success" in output or "error" in output


def test_cli_memory_get_blocks_returns_json():
    """CLI memory get-blocks returns valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "memory", "get-blocks"],
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)
    assert "success" in output or "error" in output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_tools.py -v`
Expected: FAIL with "No module named 'rubber_duck.cli'"

**Step 3: Create package structure**

```python
# src/rubber_duck/cli/__init__.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""CLI tools for Claude Code integration."""
```

**Step 4: Write CLI tool wrapper**

```python
# src/rubber_duck/cli/tools.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""CLI wrapper for Rubber Duck tools.

Provides command-line access to Todoist, Calendar, and Memory tools
for Claude Code skills to invoke via Bash.

Usage:
    python -m rubber_duck.cli.tools todoist query "today | overdue"
    python -m rubber_duck.cli.tools todoist create "Task content" --due "tomorrow"
    python -m rubber_duck.cli.tools memory get-blocks
    python -m rubber_duck.cli.tools memory search "query"
"""

import argparse
import asyncio
import json
import sys
from typing import Any


def output_json(data: dict[str, Any]) -> None:
    """Print JSON output to stdout."""
    print(json.dumps(data, indent=2, default=str))


def output_error(message: str) -> None:
    """Print error as JSON to stdout."""
    output_json({"success": False, "error": message})


# --- Todoist Commands ---

async def todoist_query(filter_query: str) -> dict:
    """Query Todoist tasks by filter."""
    from rubber_duck.integrations.todoist import get_tasks_by_filter, get_projects

    tasks = await get_tasks_by_filter(filter_query)
    projects = await get_projects()

    # Enrich tasks with project names
    for task in tasks:
        task["project_name"] = projects.get(task.get("project_id", ""), "Unknown")

    return {"success": True, "tasks": tasks, "count": len(tasks)}


async def todoist_create(
    content: str,
    due: str | None = None,
    project: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    """Create a Todoist task."""
    from rubber_duck.integrations.todoist import create_task, list_projects

    # Resolve project name to ID if provided
    project_id = None
    if project:
        projects = await list_projects()
        for p in projects:
            if p["name"].lower() == project.lower():
                project_id = p["id"]
                break
        if not project_id:
            return {"success": False, "error": f"Project '{project}' not found"}

    result = await create_task(
        content=content,
        due_string=due,
        project_id=project_id,
        labels=labels or [],
    )

    if result:
        return {"success": True, "task": result}
    return {"success": False, "error": "Failed to create task"}


async def todoist_complete(task_id: str) -> dict:
    """Complete a Todoist task."""
    from rubber_duck.integrations.todoist import complete_task

    success = await complete_task(task_id)
    return {"success": success}


async def todoist_list_projects() -> dict:
    """List all Todoist projects."""
    from rubber_duck.integrations.todoist import list_projects

    projects = await list_projects()
    return {"success": True, "projects": projects}


# --- Memory Commands ---

async def memory_get_blocks() -> dict:
    """Get all memory blocks from Letta."""
    from rubber_duck.agent.utils import run_async
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Letta not configured"}

        agent_id = await get_or_create_agent()
        if not agent_id:
            return {"success": False, "error": "Could not get agent"}

        block_list = client.agents.blocks.list(agent_id=agent_id)
        blocks = {}
        for block in block_list:
            label = getattr(block, "label", None) or getattr(block, "name", "unknown")
            value = getattr(block, "value", "") or getattr(block, "content", "")
            blocks[label] = value

        return {"success": True, "blocks": blocks}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def memory_set_block(label: str, value: str) -> dict:
    """Set a memory block value."""
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Letta not configured"}

        agent_id = await get_or_create_agent()
        if not agent_id:
            return {"success": False, "error": "Could not get agent"}

        # Find block by label
        block_list = client.agents.blocks.list(agent_id=agent_id)
        for block in block_list:
            block_label = getattr(block, "label", None) or getattr(block, "name", "")
            if block_label == label:
                client.agents.blocks.update(
                    agent_id=agent_id,
                    block_id=block.id,
                    value=value,
                )
                return {"success": True, "label": label}

        return {"success": False, "error": f"Block '{label}' not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def memory_search(query: str, limit: int = 10) -> dict:
    """Search archival memory."""
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Letta not configured"}

        agent_id = await get_or_create_agent()
        if not agent_id:
            return {"success": False, "error": "Could not get agent"}

        results = client.agents.archival_memory.search(
            agent_id=agent_id,
            query=query,
            limit=limit,
        )

        passages = [
            {"text": r.text, "created_at": str(r.created_at)}
            for r in results
        ]

        return {"success": True, "results": passages, "count": len(passages)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def memory_archive(content: str) -> dict:
    """Archive content to long-term memory."""
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    try:
        client = get_client()
        if not client:
            return {"success": False, "error": "Letta not configured"}

        agent_id = await get_or_create_agent()
        if not agent_id:
            return {"success": False, "error": "Could not get agent"}

        client.agents.archival_memory.insert(
            agent_id=agent_id,
            memory=content,
        )

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Calendar Commands ---

async def gcal_query(time_min: str | None = None, time_max: str | None = None) -> dict:
    """Query Google Calendar events."""
    from rubber_duck.integrations.gcal import get_events

    events = await get_events(time_min=time_min, time_max=time_max)
    return {"success": True, "events": events, "count": len(events)}


# --- Main Entry Point ---

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Rubber Duck CLI tools")
    subparsers = parser.add_subparsers(dest="command", help="Tool category")

    # Todoist commands
    todoist_parser = subparsers.add_parser("todoist", help="Todoist task management")
    todoist_sub = todoist_parser.add_subparsers(dest="action")

    query_parser = todoist_sub.add_parser("query", help="Query tasks")
    query_parser.add_argument("filter", help="Todoist filter expression")

    create_parser = todoist_sub.add_parser("create", help="Create task")
    create_parser.add_argument("content", help="Task content")
    create_parser.add_argument("--due", help="Due date string")
    create_parser.add_argument("--project", help="Project name")
    create_parser.add_argument("--labels", nargs="+", help="Labels")

    complete_parser = todoist_sub.add_parser("complete", help="Complete task")
    complete_parser.add_argument("task_id", help="Task ID")

    todoist_sub.add_parser("projects", help="List projects")

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="action")

    memory_sub.add_parser("get-blocks", help="Get all memory blocks")

    set_block_parser = memory_sub.add_parser("set-block", help="Set memory block")
    set_block_parser.add_argument("label", help="Block label")
    set_block_parser.add_argument("value", help="Block value")

    search_parser = memory_sub.add_parser("search", help="Search archival memory")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")

    archive_parser = memory_sub.add_parser("archive", help="Archive to memory")
    archive_parser.add_argument("content", help="Content to archive")

    # Calendar commands
    gcal_parser = subparsers.add_parser("gcal", help="Google Calendar")
    gcal_sub = gcal_parser.add_subparsers(dest="action")

    gcal_query_parser = gcal_sub.add_parser("query", help="Query events")
    gcal_query_parser.add_argument("--time-min", help="Start time (ISO format)")
    gcal_query_parser.add_argument("--time-max", help="End time (ISO format)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "todoist":
            if args.action == "query":
                result = asyncio.run(todoist_query(args.filter))
            elif args.action == "create":
                result = asyncio.run(todoist_create(
                    args.content,
                    due=args.due,
                    project=args.project,
                    labels=args.labels,
                ))
            elif args.action == "complete":
                result = asyncio.run(todoist_complete(args.task_id))
            elif args.action == "projects":
                result = asyncio.run(todoist_list_projects())
            else:
                output_error(f"Unknown todoist action: {args.action}")
                sys.exit(1)

        elif args.command == "memory":
            if args.action == "get-blocks":
                result = asyncio.run(memory_get_blocks())
            elif args.action == "set-block":
                result = asyncio.run(memory_set_block(args.label, args.value))
            elif args.action == "search":
                result = asyncio.run(memory_search(args.query, args.limit))
            elif args.action == "archive":
                result = asyncio.run(memory_archive(args.content))
            else:
                output_error(f"Unknown memory action: {args.action}")
                sys.exit(1)

        elif args.command == "gcal":
            if args.action == "query":
                result = asyncio.run(gcal_query(args.time_min, args.time_max))
            else:
                output_error(f"Unknown gcal action: {args.action}")
                sys.exit(1)

        else:
            output_error(f"Unknown command: {args.command}")
            sys.exit(1)

        output_json(result)

    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_tools.py -v`
Expected: PASS (tests will show success:false due to missing API keys, but JSON is valid)

**Step 6: Commit**

```bash
git add src/rubber_duck/cli/ tests/test_cli_tools.py
git commit -m "feat: add CLI tool wrappers for Claude Code skills"
```

---

## Task 2: Create Claude Code Skills

**Files:**
- Create: `.claude/skills/todoist/SKILL.md`
- Create: `.claude/skills/memory/SKILL.md`
- Create: `.claude/skills/gcal/SKILL.md`

**Step 1: Create Todoist skill**

```markdown
<!-- .claude/skills/todoist/SKILL.md -->
---
name: todoist-tasks
description: Query, create, update, and complete Todoist tasks. Use when user mentions tasks, todos, to-dos, Todoist, or needs to manage work items.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Todoist Task Management

Query, create, and complete tasks in the user's Todoist.

## Query Tasks

```bash
uv run python -m rubber_duck.cli.tools todoist query "today | overdue"
```

Common filters:
- `today` - tasks due today
- `overdue` - overdue tasks
- `today | overdue` - both
- `#ProjectName` - tasks in a project
- `@label` - tasks with a label
- `all` - all tasks

## Create Task

```bash
uv run python -m rubber_duck.cli.tools todoist create "Task content" --due "tomorrow" --project "Inbox"
```

Options:
- `--due` - due date (e.g., "tomorrow", "next monday", "Jan 15")
- `--project` - project name
- `--labels` - space-separated labels

## Complete Task

```bash
uv run python -m rubber_duck.cli.tools todoist complete TASK_ID
```

## List Projects

```bash
uv run python -m rubber_duck.cli.tools todoist projects
```

## Output Format

All commands return JSON:
```json
{"success": true, "tasks": [...], "count": 5}
{"success": false, "error": "Error message"}
```
```

**Step 2: Create Memory skill**

```markdown
<!-- .claude/skills/memory/SKILL.md -->
---
name: letta-memory
description: Access persistent memory - get/set memory blocks, search past conversations, archive insights. Use for remembering user preferences, patterns, past discussions.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Memory Operations

Access the user's persistent memory stored in Letta.

## Memory Blocks (Core Identity)

Get all blocks:
```bash
uv run python -m rubber_duck.cli.tools memory get-blocks
```

Update a block:
```bash
uv run python -m rubber_duck.cli.tools memory set-block "patterns" "New observed patterns..."
```

Available blocks:
- `persona` - facts about the owner
- `bot_values` - bot identity
- `patterns` - observed behavioral patterns
- `guidelines` - operating principles
- `communication` - tone and style
- `current_focus` - what owner is working on
- `schedule` - schedule awareness

## Search Past Conversations

```bash
uv run python -m rubber_duck.cli.tools memory search "query about past topic" --limit 10
```

## Archive Information

Save important information for future reference:
```bash
uv run python -m rubber_duck.cli.tools memory archive "User prefers morning meetings"
```

## Output Format

All commands return JSON:
```json
{"success": true, "blocks": {"persona": "...", "patterns": "..."}}
{"success": true, "results": [{"text": "...", "created_at": "..."}]}
```
```

**Step 3: Create Calendar skill**

```markdown
<!-- .claude/skills/gcal/SKILL.md -->
---
name: google-calendar
description: Query Google Calendar events. Use when user asks about schedule, meetings, appointments, or calendar.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Google Calendar

Query the user's Google Calendar events.

## Query Events

```bash
uv run python -m rubber_duck.cli.tools gcal query
```

With time range:
```bash
uv run python -m rubber_duck.cli.tools gcal query --time-min "2026-01-03T00:00:00Z" --time-max "2026-01-04T00:00:00Z"
```

## Output Format

```json
{
  "success": true,
  "events": [
    {"summary": "Meeting", "start": "2026-01-03T10:00:00", "end": "2026-01-03T11:00:00"}
  ],
  "count": 1
}
```
```

**Step 4: Commit**

```bash
git add .claude/skills/
git commit -m "feat: add Claude Code skills for todoist, memory, gcal"
```

---

## Task 3: Create Claude Code Executor

**Files:**
- Create: `src/rubber_duck/agent/claude_code.py`
- Test: `tests/test_claude_code.py`

**Step 1: Write the failing test**

```python
# tests/test_claude_code.py
"""Tests for Claude Code executor."""

import pytest
from rubber_duck.agent.claude_code import parse_ndjson_line, ClaudeCodeEvent


def test_parse_ndjson_text_event():
    """Parse a text content event."""
    line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "assistant"
    assert event.text == "Hello"


def test_parse_ndjson_tool_use_event():
    """Parse a tool use event."""
    line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"123"}]}}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "tool_use"
    assert event.tool_name == "Read"


def test_parse_ndjson_result_event():
    """Parse a final result event."""
    line = '{"type":"result","result":"Final response","session_id":"abc123"}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "result"
    assert event.text == "Final response"
    assert event.session_id == "abc123"


def test_parse_invalid_json():
    """Invalid JSON returns None."""
    event = parse_ndjson_line("not json")
    assert event is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_code.py -v`
Expected: FAIL with "No module named 'rubber_duck.agent.claude_code'"

**Step 3: Write Claude Code executor**

```python
# src/rubber_duck/agent/claude_code.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Claude Code subprocess executor.

Runs Claude Code CLI and parses streaming NDJSON output.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable, Awaitable

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

    # System events we can ignore
    if event_type in ("system", "user"):
        return None

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

    await process.wait()


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
    except Exception:
        return None


def save_session(channel_id: int, session_id: str) -> None:
    """Save session ID for a channel."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    data[str(channel_id)] = session_id
    SESSION_FILE.write_text(json.dumps(data, indent=2))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_code.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/agent/claude_code.py tests/test_claude_code.py
git commit -m "feat: add Claude Code executor with NDJSON parsing"
```

---

## Task 4: Build System Prompt from Memory Blocks

**Files:**
- Modify: `src/rubber_duck/agent/claude_code.py`
- Test: `tests/test_claude_code.py`

**Step 1: Add test for system prompt building**

Add to `tests/test_claude_code.py`:

```python
def test_build_system_prompt_includes_blocks():
    """System prompt includes memory block content."""
    from rubber_duck.agent.claude_code import build_system_prompt

    blocks = {
        "persona": "Test owner info",
        "patterns": "Test patterns",
    }
    prompt = build_system_prompt(blocks)

    assert "Test owner info" in prompt
    assert "Test patterns" in prompt
    assert "Current time:" in prompt
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_code.py::test_build_system_prompt_includes_blocks -v`
Expected: FAIL with "cannot import name 'build_system_prompt'"

**Step 3: Implement build_system_prompt**

Add to `src/rubber_duck/agent/claude_code.py`:

```python
from datetime import datetime


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
"""
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_code.py::test_build_system_prompt_includes_blocks -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/agent/claude_code.py tests/test_claude_code.py
git commit -m "feat: add system prompt builder from memory blocks"
```

---

## Task 5: Update Conversation Handler

**Files:**
- Modify: `src/rubber_duck/handlers/conversation.py`
- Keep: Old `run_agent_loop_interactive` as fallback

**Step 1: Create new handler function**

Add to `src/rubber_duck/handlers/conversation.py`:

```python
from rubber_duck.agent.claude_code import (
    ClaudeCodeCallbacks,
    build_system_prompt,
    run_claude_code,
    load_session,
    save_session,
)


async def handle_message_claude_code(bot, message: discord.Message) -> None:
    """Handle message using Claude Code subprocess.

    This is the new handler that uses Claude Code CLI instead of
    direct Anthropic SDK calls.
    """
    content = message.content.strip()
    if not content:
        return

    channel_id = message.channel.id

    # Check for active session
    if channel_id in _active_sessions:
        logger.info(f"Message during active session: {content[:50]}")
        return

    logger.info(f"Handling message via Claude Code: {content[:50]}...")

    try:
        status_msg = await message.reply("🤔 Starting...")

        # Load memory blocks for system prompt
        from rubber_duck.agent.loop import _get_memory_blocks
        memory_blocks = _get_memory_blocks()
        system_prompt = build_system_prompt(memory_blocks)

        # Check for existing session (for follow-ups)
        session_id = load_session(channel_id)

        # Track tool progress
        tool_log: list[str] = []

        async def on_tool_start(name: str) -> None:
            tool_log.append(f"🔧 {name} ...")
            try:
                await status_msg.edit(content="\n".join(tool_log))
            except discord.HTTPException:
                pass

        async def on_tool_end(name: str, success: bool) -> None:
            symbol = "✓" if success else "✗"
            for i in range(len(tool_log) - 1, -1, -1):
                if name in tool_log[i]:
                    tool_log[i] = f"🔧 {name} {symbol}"
                    break
            try:
                await status_msg.edit(content="\n".join(tool_log))
            except discord.HTTPException:
                pass

        callbacks = ClaudeCodeCallbacks(
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

        response, new_session_id = await run_claude_code(
            prompt=content,
            system_prompt=system_prompt,
            session_id=session_id,
            callbacks=callbacks,
        )

        # Save session for potential follow-up
        if new_session_id:
            save_session(channel_id, new_session_id)

        await status_msg.edit(content=response)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await message.reply("Sorry, something went wrong.")
```

**Step 2: Add feature flag**

Add to `src/rubber_duck/handlers/conversation.py`:

```python
import os

USE_CLAUDE_CODE = os.environ.get("USE_CLAUDE_CODE", "").lower() in ("1", "true", "yes")


async def handle_message(bot, message: discord.Message) -> None:
    """Route to appropriate handler based on feature flag."""
    if USE_CLAUDE_CODE:
        await handle_message_claude_code(bot, message)
    else:
        await handle_message_sdk(bot, message)


# Rename existing handle_message to handle_message_sdk
```

**Step 3: Commit**

```bash
git add src/rubber_duck/handlers/conversation.py
git commit -m "feat: add Claude Code handler with feature flag"
```

---

## Task 6: Update Nudge Handler

**Files:**
- Modify: `src/rubber_duck/nudge.py`

**Step 1: Read current nudge.py**

Check how nudges currently work and add Claude Code support.

**Step 2: Add Claude Code nudge generation**

Similar pattern to conversation handler - use `run_claude_code` with nudge-specific prompt when `USE_CLAUDE_CODE` is enabled.

**Step 3: Commit**

```bash
git add src/rubber_duck/nudge.py
git commit -m "feat: add Claude Code support for nudge generation"
```

---

## Task 7: Add Journal Logging

**Files:**
- Modify: `src/rubber_duck/agent/claude_code.py`

**Step 1: Add journal logging to Claude Code calls**

Log user messages and final responses to `state/journal.jsonl` for continuity with existing system.

```python
def _log_to_journal(event_type: str, data: dict) -> None:
    """Append event to journal.jsonl."""
    from rubber_duck.agent.loop import _log_to_journal as log_journal
    log_journal(event_type, data)
```

Add calls in `run_claude_code`:
- Log `user_message` before calling Claude Code
- Log `assistant_message` after getting result

**Step 2: Commit**

```bash
git add src/rubber_duck/agent/claude_code.py
git commit -m "feat: add journal logging to Claude Code executor"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/test_integration_claude_code.py`

**Step 1: Write integration test**

```python
# tests/test_integration_claude_code.py
"""Integration tests for Claude Code executor."""

import pytest
import os

# Skip if no Claude Code available
pytestmark = pytest.mark.skipif(
    os.system("which claude > /dev/null 2>&1") != 0,
    reason="Claude Code CLI not installed"
)


@pytest.mark.asyncio
async def test_simple_prompt():
    """Test simple prompt execution."""
    from rubber_duck.agent.claude_code import run_claude_code

    response, session_id = await run_claude_code(
        prompt="What is 2+2? Reply with just the number.",
    )

    assert "4" in response
    assert session_id is not None
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_integration_claude_code.py -v`

**Step 3: Commit**

```bash
git add tests/test_integration_claude_code.py
git commit -m "test: add Claude Code integration tests"
```

---

## Task 9: Update Environment Configuration

**Files:**
- Modify: `.env.example` (if exists)
- Modify: `docs/plans/2026-01-03-claude-code-refactor-design.md`

**Step 1: Document environment variables**

Add to documentation:
- `USE_CLAUDE_CODE=true` - enable Claude Code instead of SDK
- Ensure `~/.claude/.credentials.json` exists for auth

**Step 2: Commit**

```bash
git add docs/
git commit -m "docs: update environment config for Claude Code"
```

---

## Task 10: Final Cleanup

**Step 1: Remove Anthropic SDK dependency (optional)**

If fully migrated, can remove `anthropic` from dependencies. Keep for now as fallback.

**Step 2: Update bead status**

```bash
bd update rubber-duck-etf --status in_progress
bd show rubber-duck-etf
```

**Step 3: Run full test suite**

```bash
uv run pytest -v
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Claude Code refactor - ready for testing"
```

---

## Execution Checklist

- [ ] Task 1: CLI tool wrappers
- [ ] Task 2: Claude Code skills
- [ ] Task 3: Claude Code executor
- [ ] Task 4: System prompt builder
- [ ] Task 5: Conversation handler update
- [ ] Task 6: Nudge handler update
- [ ] Task 7: Journal logging
- [ ] Task 8: Integration testing
- [ ] Task 9: Environment configuration
- [ ] Task 10: Final cleanup

---

Plan complete and saved to `docs/plans/2026-01-03-claude-code-refactor-impl.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
