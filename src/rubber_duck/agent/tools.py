"""Local tool definitions for Rubber Duck agent.

Tools execute in the main Python process, not in Letta's sandbox.
Each tool returns a string result suitable for the LLM.
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from rubber_duck.agent.utils import run_async

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
                result = subprocess.run(
                    ["git", "add", path],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return f"Error staging {path}: {result.stderr}"
        else:
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return f"Error staging files: {result.stderr}"

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

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        # Get agent ID (may need to create)
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        # Get memory blocks
        agent = client.agents.retrieve(agent_id=agent_id)
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

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        # Find and update block
        agent = client.agents.retrieve(agent_id=agent_id)
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

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        response = client.agents.passages.search(
            agent_id=agent_id,
            query=query,
        )

        # Handle PassageSearchResponse - extract passages list
        passages = getattr(response, 'passages', None) or getattr(response, 'results', None) or []
        if hasattr(response, '__iter__') and not passages:
            passages = list(response)

        if not passages:
            return "No results found"

        lines = [f"Found {len(passages)} result(s):"]
        for r in passages:
            text = getattr(r, 'content', None) or getattr(r, 'text', None) or str(r)
            lines.append(f"- {text[:200]}...")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching memory: {e}"


def archive_to_memory(content: str) -> str:
    """Archive important information to persistent memory.

    Use this to save insights, patterns, preferences, or context you want
    to remember across conversations. This is your long-term memory.

    Args:
        content: Text to archive (be descriptive - include date/context)

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    client = get_client()
    if not client:
        return "Error: Letta not configured"

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return "Error: Could not get agent"

        client.agents.passages.insert(
            agent_id=agent_id,
            content=content,
        )
        return f"Archived to memory: {content[:100]}..."
    except Exception as e:
        return f"Error archiving to memory: {e}"


def read_journal(limit: int = 50) -> str:
    """Read recent entries from the conversation journal.

    The journal contains a log of recent conversations, tool calls,
    and events. Use this to recall what happened in recent interactions.

    Args:
        limit: Maximum number of entries to return (default: 50)

    Returns:
        Recent journal entries or error message
    """
    from pathlib import Path
    import json

    repo_root = Path(__file__).parent.parent.parent.parent
    journal_path = repo_root / "state" / "journal.jsonl"

    if not journal_path.exists():
        return "No journal entries yet"

    try:
        entries = []
        with open(journal_path, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        # Get last N entries
        recent = entries[-limit:] if len(entries) > limit else entries

        if not recent:
            return "No journal entries yet"

        lines = [f"Last {len(recent)} journal entries:"]
        for entry in recent:
            ts = entry.get("ts", "")[:19]  # Trim to readable timestamp
            event_type = entry.get("type", "unknown")
            if event_type == "user_message":
                content = entry.get("content", "")[:1000]
                lines.append(f"[{ts}] USER: {content}")
            elif event_type == "assistant_message":
                content = entry.get("content", "")[:2000]
                lines.append(f"[{ts}] ASSISTANT: {content}")
            elif event_type == "tool_call":
                tool = entry.get("tool", "")
                args = str(entry.get("args", {}))[:200]
                lines.append(f"[{ts}] TOOL: {tool}({args})")
            # Skip tool_result for brevity

        return "\n".join(lines)
    except Exception as e:
        return f"Error reading journal: {e}"


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

    client = get_client()
    if not client:
        return "Error: Todoist not configured"

    try:
        # filter_tasks returns an Iterator[list[Task]], flatten it
        task_batches = run_async(
            asyncio.to_thread(lambda: list(client.filter_tasks(query=filter_query)))
        )
        # Flatten the list of lists
        tasks = [task for batch in task_batches for task in batch]

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

        task = run_async(
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

    client = get_client()
    if not client:
        return "Error: Todoist not configured"

    try:
        run_async(
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

    try:
        now = datetime.now()
        end = now + timedelta(days=days)

        events = run_async(
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
# GTD Workflow Tools
# =============================================================================

def run_morning_planning() -> str:
    """Run morning planning workflow.

    Returns prioritized plan for today with calendar + tasks.
    """
    from rubber_duck.integrations.tools.morning_planning import run_morning_planning as _run
    return _run()


def run_weekly_review() -> str:
    """Run weekly review workflow.

    Returns project health, overdue items, waiting-for status.
    """
    from rubber_duck.integrations.tools.weekly_review import run_weekly_review as _run
    return _run()


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
        "name": "archive_to_memory",
        "description": "Save important information to persistent long-term memory. Use for insights, patterns, preferences, or context to remember across conversations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Text to archive (include date/context for searchability)",
                }
            },
            "required": ["content"],
        },
    },
    {
        "name": "read_journal",
        "description": "Read recent conversation history from the journal. Shows user messages, your responses, and tool calls.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default: 50)",
                }
            },
            "required": [],
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
    "archive_to_memory": archive_to_memory,
    "read_journal": read_journal,
    "query_todoist": query_todoist,
    "create_todoist_task": create_todoist_task,
    "complete_todoist_task": complete_todoist_task,
    "query_gcal": query_gcal,
    "run_morning_planning": run_morning_planning,
    "run_weekly_review": run_weekly_review,
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
