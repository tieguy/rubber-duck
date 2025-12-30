# Strix-Style Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Rubber Duck from Letta-as-LLM to Letta-as-memory, using Anthropic/Opus directly for reasoning with full file/git self-modification.

**Architecture:** Three-tier memory (Core Letta blocks → Index blocks → Git files), direct Anthropic SDK for LLM with tool use, local tool execution in Python process, unified JSONL logging.

**Tech Stack:** Anthropic Python SDK, Letta (memory only), discord.py, APScheduler, Git, existing Todoist/GCal integrations.

---

## Task 1: Add Anthropic SDK Dependency

**Files:**
- Modify: `pyproject.toml:11-18`

**Step 1: Add anthropic to dependencies**

In `pyproject.toml`, add `anthropic` to the dependencies list:

```toml
dependencies = [
    "discord.py>=2.3.0",
    "anthropic>=0.40.0",
    "apscheduler>=3.10.0",
    "letta-client>=1.6.0",
    "pyyaml>=6.0",
    "todoist-api-python>=3.1.0",
]
```

Remove `claude-agent-sdk` (not needed with direct Anthropic SDK).

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Dependencies installed without errors

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add anthropic SDK, remove claude-agent-sdk"
```

---

## Task 2: Create State Directory Structure

**Files:**
- Create: `state/.gitkeep`
- Create: `state/inbox.md`
- Create: `state/today.md`
- Create: `state/insights/.gitkeep`

**Step 1: Create state directory with initial files**

```bash
mkdir -p state/insights
touch state/.gitkeep
touch state/insights/.gitkeep
```

**Step 2: Create inbox.md**

```markdown
# Inbox

Unprocessed thoughts and quick captures. Review during weekly review.

---
```

**Step 3: Create today.md**

```markdown
# Today's Focus

Current priorities (max 3). Updated each morning.

---

1. (empty - set during morning planning)
2.
3.
```

**Step 4: Commit**

```bash
git add state/
git commit -m "feat: create state directory structure for Strix memory"
```

---

## Task 3: Create Tool Definitions Module

**Files:**
- Create: `src/rubber_duck/agent/tools.py`
- Create: `src/rubber_duck/agent/__init__.py`

**Step 1: Create agent package init**

Create `src/rubber_duck/agent/__init__.py`:

```python
"""Agent module with Anthropic SDK and local tool execution."""
```

**Step 2: Create tools.py with tool definitions**

Create `src/rubber_duck/agent/tools.py` with tool function definitions and Anthropic tool schemas.

The file should contain:

1. **File operations**: `read_file`, `write_file`, `list_directory`
2. **Git operations**: `git_commit`, `git_status`
3. **Letta memory**: `get_memory_blocks`, `set_memory_block`, `search_memory`
4. **Todoist tools**: Port existing tools to local execution (sync wrapper around existing `todoist.py`)
5. **GCal tools**: Port `query_gcal` to local execution

Each tool needs:
- A Python function that executes the action
- An Anthropic tool schema dict for the messages API

```python
"""Local tool definitions for Rubber Duck agent.

Tools execute in the main Python process, not in Letta's sandbox.
Each tool returns a string result suitable for the LLM.
"""

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Base paths
REPO_ROOT = Path(__file__).parent.parent.parent.parent
STATE_DIR = REPO_ROOT / "state"
CONFIG_DIR = REPO_ROOT / "config"

# Safety: paths the bot cannot read/write
FORBIDDEN_PATHS = {".git", ".env", "secrets"}


def _is_safe_path(path: str) -> bool:
    """Check if path is safe to read/write."""
    path_parts = Path(path).parts
    return not any(part in FORBIDDEN_PATHS for part in path_parts)


# =============================================================================
# File Operations
# =============================================================================

def read_file(path: str) -> str:
    """Read a file from the repository.

    Args:
        path: Relative path from repository root

    Returns:
        File contents or error message
    """
    if not _is_safe_path(path):
        return f"Error: Cannot read from protected path: {path}"

    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Error: File not found: {path}"
    if not full_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        # Limit file size
        if full_path.stat().st_size > 100_000:
            return f"Error: File too large (>100KB): {path}"
        return full_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file in the repository.

    Args:
        path: Relative path from repository root
        content: Content to write

    Returns:
        Success or error message
    """
    if not _is_safe_path(path):
        return f"Error: Cannot write to protected path: {path}"

    full_path = REPO_ROOT / path

    try:
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str = ".") -> str:
    """List contents of a directory.

    Args:
        path: Relative path from repository root (default: root)

    Returns:
        Directory listing or error message
    """
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Error: Directory not found: {path}"
    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = []
        for entry in sorted(full_path.iterdir()):
            if entry.name.startswith("."):
                continue  # Skip hidden files
            entry_type = "dir" if entry.is_dir() else "file"
            entries.append(f"  {entry_type}: {entry.name}")

        if not entries:
            return f"{path}/ (empty)"
        return f"{path}/\n" + "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


# =============================================================================
# Git Operations
# =============================================================================

def git_status() -> str:
    """Get current git status.

    Returns:
        Git status output or error message
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or "(working tree clean)"
    except Exception as e:
        return f"Error running git status: {e}"


def git_commit(message: str, paths: list[str] | None = None) -> str:
    """Commit changes to git.

    Args:
        message: Commit message
        paths: Specific paths to commit (default: all changes)

    Returns:
        Commit result or error message
    """
    try:
        # Stage files
        if paths:
            for path in paths:
                subprocess.run(
                    ["git", "add", path],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    timeout=10,
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=REPO_ROOT,
                capture_output=True,
                timeout=10,
            )

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                return "Nothing to commit (working tree clean)"
            return f"Error: {result.stderr}"

        return f"Committed: {message}"
    except Exception as e:
        return f"Error committing: {e}"


# =============================================================================
# Letta Memory Operations
# =============================================================================

def get_memory_blocks() -> str:
    """Get all Letta memory blocks.

    Returns:
        JSON-formatted memory blocks or error message
    """
    from rubber_duck.integrations.memory import get_client, get_or_create_agent
    import asyncio

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        # Get agent ID (may need to create)
        agent_id = asyncio.get_event_loop().run_until_complete(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        # Get memory blocks
        agent = client.agents.get(agent_id)
        blocks = {}
        for block in agent.memory.blocks:
            blocks[block.label] = block.value

        return json.dumps(blocks, indent=2)
    except Exception as e:
        return f"Error getting memory blocks: {e}"


def set_memory_block(name: str, value: str) -> str:
    """Update a Letta memory block.

    Args:
        name: Block label (e.g., "persona", "current_focus")
        value: New block value

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.memory import get_client, get_or_create_agent
    import asyncio

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        agent_id = asyncio.get_event_loop().run_until_complete(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        # Find and update block
        agent = client.agents.get(agent_id)
        for block in agent.memory.blocks:
            if block.label == name:
                client.agents.memory.update_block(
                    agent_id=agent_id,
                    block_label=name,
                    value=value,
                )
                return f"Updated memory block '{name}'"

        return f"Error: Block '{name}' not found"
    except Exception as e:
        return f"Error updating memory block: {e}"


def search_memory(query: str) -> str:
    """Search Letta archival memory.

    Args:
        query: Search query

    Returns:
        Search results or error message
    """
    from rubber_duck.integrations.memory import get_client, get_or_create_agent
    import asyncio

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        agent_id = asyncio.get_event_loop().run_until_complete(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        results = client.agents.archival_memory.search(
            agent_id=agent_id,
            query=query,
            limit=10,
        )

        if not results:
            return "No results found"

        lines = [f"Found {len(results)} result(s):"]
        for r in results:
            lines.append(f"- {r.text[:200]}...")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching memory: {e}"


# =============================================================================
# Todoist Operations (wrap existing integration)
# =============================================================================

def query_todoist(filter_query: str) -> str:
    """Query tasks from Todoist.

    Args:
        filter_query: Todoist filter (e.g., "today", "@label", "#Project")

    Returns:
        Formatted task list or error message
    """
    from rubber_duck.integrations.todoist import get_client
    import asyncio

    client = get_client()
    if not client:
        return "Error: Todoist not configured"

    try:
        tasks = asyncio.get_event_loop().run_until_complete(
            asyncio.to_thread(client.get_tasks, filter=filter_query)
        )

        if not tasks:
            return f"No tasks found matching '{filter_query}'"

        lines = [f"Found {len(tasks)} task(s):"]
        for t in tasks[:20]:
            due = f" (due: {t.due.string})" if t.due else ""
            labels = f" [{', '.join(t.labels)}]" if t.labels else ""
            lines.append(f"- [ID:{t.id}] {t.content}{due}{labels}")

        if len(tasks) > 20:
            lines.append(f"... and {len(tasks) - 20} more")

        return "\n".join(lines)
    except Exception as e:
        return f"Error querying Todoist: {e}"


def create_todoist_task(
    content: str,
    due_string: str | None = None,
    project_id: str | None = None,
    labels: list[str] | None = None,
) -> str:
    """Create a task in Todoist.

    Args:
        content: Task content
        due_string: Natural language due date (e.g., "tomorrow", "next monday")
        project_id: Project ID to add task to
        labels: List of label names

    Returns:
        Created task info or error message
    """
    from rubber_duck.integrations.todoist import get_client
    import asyncio

    client = get_client()
    if not client:
        return "Error: Todoist not configured"

    try:
        kwargs = {"content": content}
        if due_string:
            kwargs["due_string"] = due_string
        if project_id:
            kwargs["project_id"] = project_id
        if labels:
            kwargs["labels"] = labels

        task = asyncio.get_event_loop().run_until_complete(
            asyncio.to_thread(client.add_task, **kwargs)
        )

        return f"Created task: {task.content} [ID:{task.id}]\nURL: {task.url}"
    except Exception as e:
        return f"Error creating task: {e}"


def complete_todoist_task(task_id: str) -> str:
    """Mark a Todoist task as complete.

    Args:
        task_id: Task ID to complete

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.todoist import get_client
    import asyncio

    client = get_client()
    if not client:
        return "Error: Todoist not configured"

    try:
        asyncio.get_event_loop().run_until_complete(
            asyncio.to_thread(client.close_task, task_id=task_id)
        )
        return f"Completed task {task_id}"
    except Exception as e:
        return f"Error completing task: {e}"


# =============================================================================
# Google Calendar Operations
# =============================================================================

def query_gcal(days: int = 7) -> str:
    """Query Google Calendar events.

    Args:
        days: Number of days to look ahead (default: 7)

    Returns:
        Formatted calendar events or error message
    """
    from rubber_duck.integrations.gcal import get_events
    from datetime import datetime, timedelta
    import asyncio

    try:
        now = datetime.now()
        end = now + timedelta(days=days)

        events = asyncio.get_event_loop().run_until_complete(
            get_events(time_min=now, time_max=end)
        )

        if not events:
            return f"No events in the next {days} days"

        lines = [f"Events in the next {days} days:"]
        for e in events:
            start = e.get("start", "")
            summary = e.get("summary", "(No title)")
            if e.get("all_day"):
                lines.append(f"- {start[:10]}: {summary} (all day)")
            else:
                lines.append(f"- {start}: {summary}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error querying calendar: {e}"


# =============================================================================
# Tool Schemas for Anthropic API
# =============================================================================

TOOL_SCHEMAS = [
    {
        "name": "read_file",
        "description": "Read a file from the repository. Use to load state files, config, or code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repository root (e.g., 'state/inbox.md')",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Use to update state, notes, or config.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repository root",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory to see what files exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path (default: repository root)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "git_status",
        "description": "See current git status - what files have changed.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "git_commit",
        "description": "Commit changes to git. Use for important updates you want persisted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message describing the change",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific paths to commit (default: all changes)",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "get_memory_blocks",
        "description": "Get all Letta memory blocks (core identity, patterns, guidelines).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "set_memory_block",
        "description": "Update a Letta memory block. Use for persistent identity/preference changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Block label (e.g., 'persona', 'patterns', 'current_focus')",
                },
                "value": {
                    "type": "string",
                    "description": "New block value",
                },
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "search_memory",
        "description": "Search archival memory for past conversations and context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_todoist",
        "description": "Query tasks from Todoist. Filters: 'today', 'overdue', '@label', '#Project', 'all'",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_query": {
                    "type": "string",
                    "description": "Todoist filter string",
                }
            },
            "required": ["filter_query"],
        },
    },
    {
        "name": "create_todoist_task",
        "description": "Create a new task in Todoist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Task content/title",
                },
                "due_string": {
                    "type": "string",
                    "description": "Natural language due date (e.g., 'tomorrow', 'next monday')",
                },
                "project_id": {
                    "type": "string",
                    "description": "Project ID to add task to",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Label names to apply",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "complete_todoist_task",
        "description": "Mark a task as complete in Todoist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to complete",
                }
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "query_gcal",
        "description": "Query Google Calendar events for upcoming days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Days to look ahead (default: 7)",
                }
            },
            "required": [],
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "git_status": git_status,
    "git_commit": git_commit,
    "get_memory_blocks": get_memory_blocks,
    "set_memory_block": set_memory_block,
    "search_memory": search_memory,
    "query_todoist": query_todoist,
    "create_todoist_task": create_todoist_task,
    "complete_todoist_task": complete_todoist_task,
    "query_gcal": query_gcal,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with arguments.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool result string
    """
    if name not in TOOL_FUNCTIONS:
        return f"Error: Unknown tool '{name}'"

    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except Exception as e:
        logger.exception(f"Error executing tool {name}: {e}")
        return f"Error executing {name}: {e}"
```

**Step 3: Verify syntax**

Run: `python -m py_compile src/rubber_duck/agent/tools.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add src/rubber_duck/agent/
git commit -m "feat: add local tool definitions for Strix architecture"
```

---

## Task 4: Create Agent Loop Module

**Files:**
- Create: `src/rubber_duck/agent/loop.py`

**Step 1: Create the agent loop**

This module orchestrates: context assembly → Anthropic call → tool execution → response.

```python
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

from anthropic import Anthropic

from rubber_duck.agent.tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

# Model configuration
MODEL = "claude-sonnet-4-20250514"  # Use Sonnet for speed; Opus for important tasks
MAX_TOOL_CALLS = 20
TIMEOUT = 60

# Journal for unified logging
JOURNAL_PATH = "state/journal.jsonl"


def _log_to_journal(event_type: str, data: dict) -> None:
    """Append event to journal.jsonl."""
    from pathlib import Path

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

## Key Principles
- If you didn't write it down, you won't remember it next message
- Commit important changes to git for provenance
- Update memory blocks when you learn something persistent
- Use state files for working memory and tasks

## Tools
You have tools for: file operations (read/write/list), git (status/commit),
Letta memory (get/set blocks, search), Todoist (query/create/complete tasks),
and Google Calendar (query events).
"""


def _get_memory_blocks() -> dict:
    """Load memory blocks from Letta."""
    from rubber_duck.integrations.memory import get_client
    import asyncio

    try:
        from rubber_duck.integrations.memory import get_or_create_agent

        client = get_client()
        if not client:
            return {}

        agent_id = asyncio.get_event_loop().run_until_complete(get_or_create_agent())
        if not agent_id:
            return {}

        agent = client.agents.get(agent_id)
        return {block.label: block.value for block in agent.memory.blocks}
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

    client = Anthropic(api_key=api_key)

    # Load memory blocks for system prompt
    memory_blocks = _get_memory_blocks()
    system_prompt = _build_system_prompt(memory_blocks)

    # Build initial message
    if context:
        full_message = f"[Context: {context}]\n\n{user_message}"
    else:
        full_message = user_message

    messages = [{"role": "user", "content": full_message}]

    # Log user message
    _log_to_journal("user_message", {"content": user_message, "context": context})

    tool_calls = 0

    while tool_calls < MAX_TOOL_CALLS:
        try:
            response = client.messages.create(
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

            _log_to_journal("tool_call", {"tool": tool_name, "args": tool_input})

            result = execute_tool(tool_name, tool_input)

            _log_to_journal("tool_result", {"tool": tool_name, "result": result[:500]})

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
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/rubber_duck/agent/loop.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/rubber_duck/agent/loop.py
git commit -m "feat: add Anthropic-powered agent loop with tool execution"
```

---

## Task 5: Initialize Letta Memory Blocks

**Files:**
- Modify: `src/rubber_duck/integrations/memory.py`

This task updates the Letta agent creation to include all Strix-tier memory blocks.

**Step 1: Update memory block initialization**

In `memory.py`, update the `get_or_create_agent` function to create the full set of memory blocks:

```python
# Add these blocks to the agent creation:
memory_blocks=[
    # Core identity blocks (Tier 1)
    {"label": "persona", "value": "My owner. I'm learning about them."},
    {"label": "bot_values", "value": "I am Rubber Duck, a competent and efficient executive assistant. I help my owner stay organized using GTD principles."},
    {"label": "patterns", "value": "Still observing behavioral patterns."},
    {"label": "guidelines", "value": "Be concise and actionable. Suggest specific next actions. Don't be preachy."},
    {"label": "communication", "value": "Direct, efficient, no fluff. Include task IDs for reference."},
    # Index blocks (Tier 2)
    {"label": "current_focus", "value": "No specific focus set."},
    {"label": "schedule", "value": "Check calendar for schedule context."},
    {"label": "file_index", "value": "state/inbox.md - unprocessed captures\nstate/today.md - current priorities\nstate/insights/ - dated insight files\nconfig/nudges.yaml - nudge schedule"},
]
```

Note: We keep the existing SYSTEM_PROMPT for now as fallback, but the new agent loop will build its own from blocks.

**Step 2: Test agent creation**

Run: `uv run python -c "from rubber_duck.integrations.memory import get_or_create_agent; import asyncio; print(asyncio.run(get_or_create_agent()))"`
Expected: Agent ID printed (or error if LETTA_API_KEY not set)

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/memory.py
git commit -m "feat: initialize full Strix-tier memory blocks in Letta"
```

---

## Task 6: Wire Discord Handler to New Agent

**Files:**
- Modify: `src/rubber_duck/agent.py`
- Modify: `src/rubber_duck/handlers/conversation.py`

**Step 1: Update agent.py to use new loop**

Replace the contents of `agent.py` to delegate to the new agent loop:

```python
"""Agent module for Rubber Duck - orchestrates memory and tasks."""

import logging

from rubber_duck.agent.loop import run_agent_loop, generate_nudge as _generate_nudge

logger = logging.getLogger(__name__)


async def generate_nudge_content(nudge_config: dict) -> str:
    """Generate nudge content using the new Anthropic agent.

    Args:
        nudge_config: Configuration containing name, context_query, prompt_hint

    Returns:
        Generated nudge message string
    """
    return await _generate_nudge(nudge_config)


async def process_user_message(message: str, context: dict | None = None) -> str:
    """Process a user message and generate a response.

    Args:
        message: The user's message text
        context: Optional context (unused, for API compatibility)

    Returns:
        Response message string
    """
    logger.info(f"Processing user message: {message[:50]}...")

    # The new agent loop handles everything including task capture
    return await run_agent_loop(message)
```

**Step 2: Verify imports work**

Run: `uv run python -c "from rubber_duck.agent import process_user_message; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add src/rubber_duck/agent.py
git commit -m "refactor: wire agent.py to new Anthropic-powered agent loop"
```

---

## Task 7: Update Package Exports

**Files:**
- Modify: `src/rubber_duck/agent/__init__.py`

**Step 1: Export key functions**

Update `src/rubber_duck/agent/__init__.py`:

```python
"""Agent module with Anthropic SDK and local tool execution."""

from rubber_duck.agent.loop import run_agent_loop, generate_nudge
from rubber_duck.agent.tools import execute_tool, TOOL_SCHEMAS

__all__ = ["run_agent_loop", "generate_nudge", "execute_tool", "TOOL_SCHEMAS"]
```

**Step 2: Verify**

Run: `uv run python -c "from rubber_duck.agent import run_agent_loop; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add src/rubber_duck/agent/__init__.py
git commit -m "chore: export agent functions from package"
```

---

## Task 8: Add GTD Workflow Tools

**Files:**
- Modify: `src/rubber_duck/agent/tools.py`

The new agent can call Todoist directly, but the GTD workflow tools (morning planning, weekly review) provide synthesized views. Port these as local tools.

**Step 1: Add morning_planning tool**

Add to `tools.py`:

```python
def run_morning_planning() -> str:
    """Run morning planning workflow.

    Returns prioritized plan for today with calendar + tasks.
    """
    # Import and run the existing tool logic
    from rubber_duck.integrations.tools.morning_planning import run_morning_planning as _run
    return _run()


def run_weekly_review() -> str:
    """Run weekly review workflow.

    Returns project health, overdue items, waiting-for status.
    """
    from rubber_duck.integrations.tools.weekly_review import run_weekly_review as _run
    return _run()
```

**Step 2: Add tool schemas**

Add to TOOL_SCHEMAS:

```python
{
    "name": "run_morning_planning",
    "description": "Run morning planning - prioritized plan with calendar + tasks for today.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
},
{
    "name": "run_weekly_review",
    "description": "Run weekly review - project health, overdue items, waiting-for status.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
},
```

**Step 3: Add to TOOL_FUNCTIONS**

```python
TOOL_FUNCTIONS = {
    # ... existing tools ...
    "run_morning_planning": run_morning_planning,
    "run_weekly_review": run_weekly_review,
}
```

**Step 4: Commit**

```bash
git add src/rubber_duck/agent/tools.py
git commit -m "feat: add GTD workflow tools (morning planning, weekly review)"
```

---

## Task 9: Test Locally

**Files:**
- Create: `scripts/test_agent.py`

**Step 1: Create test script**

```python
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
```

**Step 2: Run test**

Run: `ANTHROPIC_API_KEY=<key> uv run python scripts/test_agent.py`
Expected: Agent responds with calendar info (or says calendar not configured)

**Step 3: Commit**

```bash
git add scripts/test_agent.py
git commit -m "test: add local agent test script"
```

---

## Task 10: Update Environment Variables Documentation

**Files:**
- Modify: `README.md` or create `docs/environment.md`

**Step 1: Document required variables**

Add documentation for:
- `ANTHROPIC_API_KEY` (required) - API key for Claude
- `LETTA_API_KEY` (required) - For persistent memory
- `DISCORD_BOT_TOKEN` (required) - Discord bot token
- `DISCORD_OWNER_ID` (required) - Owner's Discord user ID
- `TODOIST_API_KEY` (optional) - For task management
- `GOOGLE_SERVICE_ACCOUNT_JSON` (optional) - Base64-encoded service account

**Step 2: Commit**

```bash
git add docs/
git commit -m "docs: document environment variables for Strix architecture"
```

---

## Task 11: Deploy and Verify

**Step 1: Update Fly secrets**

```bash
fly secrets set ANTHROPIC_API_KEY=<key> --app rubber-duck
```

**Step 2: Deploy**

```bash
fly deploy
```

**Step 3: Test via Discord**

Send a message to the bot and verify it responds using the new agent loop. Check logs:

```bash
fly logs --app rubber-duck
```

**Step 4: Verify journal logging**

```bash
fly ssh console --app rubber-duck
cat /app/state/journal.jsonl
```

---

## Task 12: Clean Up Legacy Code

**Files:**
- Archive or remove: `src/rubber_duck/integrations/letta_tools.py`
- Archive or remove: `src/rubber_duck/integrations/tools/*.py` (Letta sandbox versions)

After verifying the new architecture works:

**Step 1: Archive old tools**

```bash
mkdir -p archive/letta-sandbox-tools
mv src/rubber_duck/integrations/tools/*.py archive/letta-sandbox-tools/
mv src/rubber_duck/integrations/letta_tools.py archive/letta-sandbox-tools/
```

Keep the `integrations/todoist.py` and `integrations/gcal.py` as they're used by the new local tools.

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: archive Letta sandbox tools (replaced by local execution)"
```

---

## Summary

After completing all tasks, the architecture will be:

```
Discord → Handler → Agent Loop (Anthropic SDK)
                        ↓
              [Tool calls executed locally]
                        ↓
         ┌──────────────┼──────────────┐
         ↓              ↓              ↓
    File/Git       Letta Memory    Todoist/GCal
    (state/)       (blocks only)   (integrations/)
```

Key capabilities gained:
- Direct Opus/Claude reasoning via Anthropic SDK
- Self-modification via file/git tools
- Persistent identity via Letta memory blocks
- Unified logging in journal.jsonl
- Local tool execution (faster, no sandbox limitations)
