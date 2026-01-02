# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

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
from rubber_duck.integrations.tools.weekly_conductor import weekly_review_conductor
from rubber_duck.integrations.tools.calendar_review import run_calendar_review
from rubber_duck.integrations.tools.deadline_scan import run_deadline_scan
from rubber_duck.integrations.tools.waiting_for_review import run_waiting_for_review
from rubber_duck.integrations.tools.project_review import run_project_review
from rubber_duck.integrations.tools.category_health import run_category_health
from rubber_duck.integrations.tools.someday_maybe_review import run_someday_maybe_review
from rubber_duck.integrations.project_metadata import (
    get_project_meta,
    set_project_metadata as _set_project_metadata,
)

logger = logging.getLogger(__name__)

# Error message constants
ERR_LETTA_NOT_CONFIGURED = "Error: Letta not configured"
ERR_AGENT_NOT_FOUND = "Error: Could not get agent"
ERR_TODOIST_NOT_CONFIGURED = "Error: Todoist not configured"
ERR_BD_NOT_INSTALLED = "Error: bd CLI not installed"

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


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing text (like sed).

    This is more efficient than read+write for small changes.
    The old_text must match exactly (including whitespace).

    Args:
        path: Relative path from repository root
        old_text: Exact text to find and replace
        new_text: Text to replace it with

    Returns:
        Success message or error
    """
    if not _is_safe_path(path):
        return f"Error: Cannot edit protected path: {path}"

    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Error: File not found: {path}"
    if not full_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        content = full_path.read_text()

        if old_text not in content:
            # Show a snippet to help debug
            snippet = content[:500] + "..." if len(content) > 500 else content
            return f"Error: old_text not found in file. File starts with:\n{snippet}"

        # Count occurrences
        count = content.count(old_text)
        if count > 1:
            return f"Error: old_text found {count} times. Must be unique. Be more specific."

        # Perform replacement
        new_content = content.replace(old_text, new_text, 1)
        full_path.write_text(new_content)

        return f"Successfully edited {path}: replaced {len(old_text)} chars with {len(new_text)} chars"
    except Exception as e:
        return f"Error editing file: {e}"


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


def git_push() -> str:
    """Push commits to remote repository.

    Returns:
        Success message or error
    """
    try:
        result = subprocess.run(
            ["git", "push"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error pushing: {result.stderr}"

        return f"Pushed to remote: {result.stdout or 'success'}"
    except Exception as e:
        return f"Error pushing: {e}"


def git_pull() -> str:
    """Pull latest changes from remote repository.

    Returns:
        Success message or error
    """
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error pulling: {result.stderr}"

        return f"Pulled from remote: {result.stdout or 'success'}"
    except Exception as e:
        return f"Error pulling: {e}"


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
        return ERR_LETTA_NOT_CONFIGURED

    try:
        # Get agent ID (may need to create)
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return ERR_AGENT_NOT_FOUND

        # Get memory blocks via blocks API
        block_list = client.agents.blocks.list(agent_id=agent_id)
        blocks = {}
        for block in block_list:
            label = getattr(block, 'label', None) or getattr(block, 'name', 'unknown')
            value = getattr(block, 'value', '') or getattr(block, 'content', '')
            blocks[label] = value

        return json.dumps(blocks, indent=2)
    except Exception as e:
        return f"Error getting memory blocks: {e}"


def set_memory_block(name: str, value: str) -> str:
    """Create or update a Letta memory block.

    Args:
        name: Block label (e.g., "persona", "current_focus", "communication")
        value: New block value

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.memory import get_client, get_or_create_agent

    client = get_client()
    if not client:
        return ERR_LETTA_NOT_CONFIGURED

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return ERR_AGENT_NOT_FOUND

        # Try to update existing block first
        try:
            client.agents.blocks.update(
                agent_id=agent_id,
                block_label=name,
                value=value,
            )
            return f"Updated memory block '{name}'"
        except Exception as update_err:
            # If block doesn't exist, create it and attach to agent
            if "404" in str(update_err) or "not found" in str(update_err).lower():
                # Create block at top level, then attach to agent
                block = client.blocks.create(label=name, value=value)
                client.agents.blocks.attach(block.id, agent_id=agent_id)
                return f"Created memory block '{name}'"
            raise  # Re-raise if it's a different error
    except Exception as e:
        return f"Error setting memory block: {e}"


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
        return ERR_LETTA_NOT_CONFIGURED

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return ERR_AGENT_NOT_FOUND

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
        return ERR_LETTA_NOT_CONFIGURED

    try:
        agent_id = run_async(get_or_create_agent())
        if not agent_id:
            return ERR_AGENT_NOT_FOUND

        # Try different method names as SDK may vary
        passages = client.agents.passages
        if hasattr(passages, 'create'):
            passages.create(agent_id=agent_id, content=content)
        elif hasattr(passages, 'insert'):
            passages.insert(agent_id=agent_id, content=content)
        elif hasattr(passages, 'add'):
            passages.add(agent_id=agent_id, content=content)
        else:
            # List available methods for debugging
            methods = [m for m in dir(passages) if not m.startswith('_')]
            return f"Error: No insert method found. Available: {methods}"
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
    from rubber_duck.integrations.todoist import get_tasks_by_filter, get_projects

    try:
        tasks = run_async(get_tasks_by_filter(filter_query))

        if not tasks:
            return f"No tasks found matching '{filter_query}'"

        # Get project names for display
        project_map = run_async(get_projects())

        lines = [f"Found {len(tasks)} task(s):"]
        for t in tasks[:20]:
            due = f" (due: {t['due']})" if t.get("due") else ""
            labels = f" [{', '.join(t['labels'])}]" if t.get("labels") else ""
            proj_id = t.get("project_id")
            project = f" (project: {project_map.get(proj_id, proj_id)})" if proj_id else ""
            lines.append(f"- [ID:{t['id']}] {t['content']}{due}{labels}{project}")

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
    from rubber_duck.integrations.todoist import create_task

    try:
        task = run_async(create_task(
            content=content,
            due_string=due_string,
            project_id=project_id,
            labels=labels,
        ))

        if not task:
            return ERR_TODOIST_NOT_CONFIGURED

        return f"Created task: {task['content']} [ID:{task['id']}]\nURL: {task['url']}"
    except Exception as e:
        return f"Error creating task: {e}"


def complete_todoist_task(task_id: str) -> str:
    """Mark a Todoist task as complete.

    Args:
        task_id: Task ID to complete

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.todoist import complete_task

    success = run_async(complete_task(task_id))
    if success:
        return f"Completed task {task_id}"
    return f"Error: Failed to complete task {task_id} (check logs)"


def list_todoist_projects() -> str:
    """List all Todoist projects with their IDs.

    Returns:
        Formatted project list with IDs
    """
    from rubber_duck.integrations.todoist import list_projects

    try:
        projects = run_async(list_projects())

        if not projects:
            return "No projects found (or Todoist not configured)"

        lines = ["Projects:"]
        for p in projects:
            indent = "  " if p.get("parent_id") else ""
            lines.append(f"{indent}- {p['name']} [ID:{p['id']}]")

        return "\n".join(lines)
    except Exception as e:
        return f"Error listing projects: {e}"


def update_todoist_task(
    task_id: str,
    content: str | None = None,
    due_string: str | None = None,
    labels: list[str] | None = None,
) -> str:
    """Update an existing Todoist task (content, due date, labels).

    Note: Cannot move tasks between projects - use move_todoist_task for that.

    Args:
        task_id: Task ID to update
        content: New task content (optional)
        due_string: New due date (optional)
        labels: New labels (optional)

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.todoist import update_task

    if not any([content, due_string, labels is not None]):
        return "Error: No updates specified"

    success = run_async(update_task(
        task_id=task_id,
        content=content,
        due_string=due_string,
        labels=labels,
    ))

    if success:
        return f"Updated task {task_id}"
    return f"Error: Failed to update task {task_id} (check logs)"


def create_todoist_project(
    name: str,
    parent_id: str | None = None,
) -> str:
    """Create a project in Todoist.

    Args:
        name: Project name
        parent_id: Parent project ID for sub-projects (optional)

    Returns:
        Created project info or error message
    """
    from rubber_duck.integrations.todoist import create_project

    try:
        project = run_async(create_project(
            name=name,
            parent_id=parent_id,
        ))

        if not project:
            return ERR_TODOIST_NOT_CONFIGURED

        return f"Created project: {project['name']} [ID:{project['id']}]\nURL: {project['url']}"
    except Exception as e:
        return f"Error creating project: {e}"


def move_todoist_task(task_id: str, project_id: str) -> str:
    """Move a task to a different project using Todoist Sync API.

    Args:
        task_id: Task ID to move
        project_id: Destination project ID

    Returns:
        Success or error message
    """
    from rubber_duck.integrations.todoist import move_task

    success = run_async(move_task(task_id, project_id))

    if success:
        return f"Moved task {task_id} to project {project_id}"
    return f"Error: Failed to move task {task_id} (check logs)"


def set_project_metadata(
    project_name: str,
    project_type: str,
    goal: str | None = None,
    context: str | None = None,
    due: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Set metadata for a Todoist project or category.

    Args:
        project_name: Exact Todoist project name
        project_type: "project" or "category"
        goal: Definition of done (projects only)
        context: Background info
        due: Deadline as ISO date
        links: Reference URLs or file paths

    Returns:
        Confirmation message
    """
    return _set_project_metadata(
        project_name=project_name,
        project_type=project_type,
        goal=goal,
        context=context,
        due=due,
        links=links,
    )


def get_project_metadata(project_name: str) -> str:
    """Get metadata for a Todoist project or category.

    Args:
        project_name: Exact Todoist project name

    Returns:
        Formatted metadata or message if not found
    """
    meta = get_project_meta(project_name)
    if not meta:
        return f"No metadata found for '{project_name}'."

    lines = [f"**{project_name}** ({meta.get('type', 'unknown')})"]

    if goal := meta.get("goal"):
        lines.append(f"**Goal:** {goal}")
    if due := meta.get("due"):
        lines.append(f"**Due:** {due}")
    if context := meta.get("context"):
        lines.append(f"**Context:** {context}")
    if links := meta.get("links"):
        lines.append("**Links:**")
        for link in links:
            lines.append(f"  - {link}")

    return "\n".join(lines)


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
# Self-Modification Tools
# =============================================================================

def restart_self(confirm: str = "") -> str:
    """Restart the bot process to reload code after git_push.

    ONLY use this immediately after git_push succeeds. This restarts the bot
    to pick up code changes you just pushed. Do NOT use for any other purpose.

    Args:
        confirm: Must be exactly "I just pushed code" to proceed.

    Returns:
        Error message if confirm is wrong, otherwise does not return.
    """
    if confirm != "I just pushed code":
        return "Error: restart_self requires confirm='I just pushed code'. Only use after git_push."

    import sys

    logger.info("Exiting to trigger container restart and pick up code changes...")

    # Flush any pending output
    sys.stdout.flush()
    sys.stderr.flush()

    # Exit cleanly - Fly.io will restart the container, which runs entrypoint.sh
    # entrypoint.sh does git reset --hard origin/main to get the latest code
    sys.exit(0)

    # This line is never reached
    return "Restarting..."


# =============================================================================
# Issue Tracking (bd) Tools
# =============================================================================

def bd_ready() -> str:
    """List issues ready to work on.

    Returns:
        List of ready issues or error message
    """
    try:
        result = subprocess.run(
            ["bd", "ready"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout or result.stderr or "No ready issues"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd ready: {e}"


def bd_show(issue_id: str) -> str:
    """Show details of a specific issue.

    Args:
        issue_id: The issue ID to show

    Returns:
        Issue details or error message
    """
    try:
        result = subprocess.run(
            ["bd", "show", issue_id],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout or result.stderr or f"No issue found: {issue_id}"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd show: {e}"


def bd_update(issue_id: str, status: str) -> str:
    """Update the status of an issue.

    Args:
        issue_id: The issue ID to update
        status: New status (e.g., 'in_progress', 'blocked', 'done')

    Returns:
        Success or error message
    """
    try:
        result = subprocess.run(
            ["bd", "update", issue_id, "--status", status],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or f"Updated {issue_id} to {status}"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd update: {e}"


def bd_close(issue_id: str) -> str:
    """Close a completed issue.

    Args:
        issue_id: The issue ID to close

    Returns:
        Success or error message
    """
    try:
        result = subprocess.run(
            ["bd", "close", issue_id],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or f"Closed issue {issue_id}"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd close: {e}"


def bd_sync() -> str:
    """Sync bd issues with git.

    Returns:
        Sync result or error message
    """
    try:
        result = subprocess.run(
            ["bd", "sync"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or "Synced"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd sync: {e}"


def bd_create(title: str, description: str = "", priority: str = "medium") -> str:
    """Create a new issue.

    Args:
        title: Issue title
        description: Issue description (optional)
        priority: Priority level (low, medium, high)

    Returns:
        Created issue ID or error message
    """
    try:
        cmd = ["bd", "create", "--title", title, "--priority", priority]
        if description:
            cmd.extend(["--description", description])

        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or "Issue created"
    except FileNotFoundError:
        return ERR_BD_NOT_INSTALLED
    except Exception as e:
        return f"Error running bd create: {e}"


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
        "name": "edit_file",
        "description": "Edit a file by replacing text (like sed). More efficient than read+write for small changes. old_text must match exactly and be unique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repository root",
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find (must be unique in file)",
                },
                "new_text": {
                    "type": "string",
                    "description": "Text to replace it with",
                },
            },
            "required": ["path", "old_text", "new_text"],
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
        "name": "list_todoist_projects",
        "description": "List all Todoist projects with their IDs. Use to find project IDs for moving tasks.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_todoist_task",
        "description": "Update task content, due date, or labels. To move between projects, use move_todoist_task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to update",
                },
                "content": {
                    "type": "string",
                    "description": "New task content (optional)",
                },
                "due_string": {
                    "type": "string",
                    "description": "New due date (optional)",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New labels (optional)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "create_todoist_project",
        "description": "Create a new project in Todoist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name",
                },
                "parent_id": {
                    "type": "string",
                    "description": "Parent project ID for sub-projects (optional)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "move_todoist_task",
        "description": "Move a task to a different project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to move",
                },
                "project_id": {
                    "type": "string",
                    "description": "Destination project ID",
                },
            },
            "required": ["task_id", "project_id"],
        },
    },
    {
        "name": "set_project_metadata",
        "description": "Set metadata for a Todoist project or category. Use to store goals, context, due dates, and links that Todoist cannot hold.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Exact Todoist project name",
                },
                "project_type": {
                    "type": "string",
                    "enum": ["project", "category"],
                    "description": "project (has goal/end state) or category (ongoing, no end state)",
                },
                "goal": {
                    "type": "string",
                    "description": "Definition of done (for projects)",
                },
                "context": {
                    "type": "string",
                    "description": "Background, constraints, stakeholders",
                },
                "due": {
                    "type": "string",
                    "description": "Deadline as ISO date, e.g. '2026-06-01'",
                },
                "links": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Reference URLs or file paths",
                },
            },
            "required": ["project_name", "project_type"],
        },
    },
    {
        "name": "get_project_metadata",
        "description": "Get stored metadata for a Todoist project or category. Returns goal, context, due date, and links.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Exact Todoist project name",
                },
            },
            "required": ["project_name"],
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
    # Weekly review step tools
    {
        "name": "weekly_review_conductor",
        "description": "Manage weekly review session. Actions: 'start' (begin review), 'status' (current step), 'next' (advance), 'complete' (end), 'abandon' (cancel).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: start, status, next, complete, abandon"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "run_calendar_review",
        "description": "Weekly review step 1: Check calendar for tasks to create. (Currently scaffolded)",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_deadline_scan",
        "description": "Weekly review step 2: Scan tasks by deadline urgency (overdue, this week, next week).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_waiting_for_review",
        "description": "Weekly review step 3: Review waiting-for items with follow-up recommendations.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_project_review",
        "description": "Weekly review step 4: Assess project health (ACTIVE/STALLED/WAITING/INCOMPLETE).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_category_health",
        "description": "Weekly review step 5: Analyze task distribution, identify overloaded/neglected areas.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_someday_maybe_review",
        "description": "Weekly review step 6: Triage backburner items (delete, review, or keep).",
        "input_schema": {"type": "object", "properties": {}}
    },
    # Git push/pull
    {
        "name": "git_push",
        "description": "Push commits to remote repository.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "git_pull",
        "description": "Pull latest changes from remote repository.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Self-modification
    {
        "name": "restart_self",
        "description": "Restart the bot to reload code. REQUIRES confirm='I just pushed code' as a safety check.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "string",
                    "description": "Must be exactly 'I just pushed code' to confirm this action.",
                }
            },
            "required": ["confirm"],
        },
    },
    # Issue tracking (bd) - for rubber-duck CODEBASE issues, NOT personal tasks
    {
        "name": "bd_ready",
        "description": "List development issues for the rubber-duck CODEBASE that are ready to work on. These are code/feature issues, NOT personal tasks - use Todoist for personal tasks.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "bd_show",
        "description": "Show details of a rubber-duck codebase development issue. NOT for personal tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "string",
                    "description": "The issue ID (e.g., 'rubber-duck-abc')",
                }
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "bd_update",
        "description": "Update the status of a rubber-duck codebase development issue. NOT for personal tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "string",
                    "description": "The issue ID to update (e.g., 'rubber-duck-abc')",
                },
                "status": {
                    "type": "string",
                    "description": "New status (e.g., 'in_progress', 'blocked', 'done')",
                },
            },
            "required": ["issue_id", "status"],
        },
    },
    {
        "name": "bd_close",
        "description": "Close a completed rubber-duck codebase development issue. NOT for personal tasks - use complete_todoist_task for those.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "string",
                    "description": "The issue ID to close (e.g., 'rubber-duck-abc')",
                }
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "bd_sync",
        "description": "Sync rubber-duck codebase issues with git. For development workflow only.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "bd_create",
        "description": "Create a new development issue for tracking work on the rubber-duck CODEBASE. NOT for personal tasks - use create_todoist_task for those.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Issue title",
                },
                "description": {
                    "type": "string",
                    "description": "Issue description (optional)",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level: low, medium, high (default: medium)",
                },
            },
            "required": ["title"],
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "edit_file": edit_file,
    "git_status": git_status,
    "git_commit": git_commit,
    "git_push": git_push,
    "git_pull": git_pull,
    "get_memory_blocks": get_memory_blocks,
    "set_memory_block": set_memory_block,
    "search_memory": search_memory,
    "archive_to_memory": archive_to_memory,
    "read_journal": read_journal,
    "query_todoist": query_todoist,
    "create_todoist_task": create_todoist_task,
    "complete_todoist_task": complete_todoist_task,
    "list_todoist_projects": list_todoist_projects,
    "update_todoist_task": update_todoist_task,
    "create_todoist_project": create_todoist_project,
    "move_todoist_task": move_todoist_task,
    "set_project_metadata": set_project_metadata,
    "get_project_metadata": get_project_metadata,
    "query_gcal": query_gcal,
    "run_morning_planning": run_morning_planning,
    "run_weekly_review": run_weekly_review,
    "weekly_review_conductor": lambda action: weekly_review_conductor(action),
    "run_calendar_review": lambda: run_calendar_review(),
    "run_deadline_scan": lambda: run_deadline_scan(),
    "run_waiting_for_review": lambda: run_waiting_for_review(),
    "run_project_review": lambda: run_project_review(),
    "run_category_health": lambda: run_category_health(),
    "run_someday_maybe_review": lambda: run_someday_maybe_review(),
    "restart_self": restart_self,
    "bd_ready": bd_ready,
    "bd_show": bd_show,
    "bd_update": bd_update,
    "bd_close": bd_close,
    "bd_sync": bd_sync,
    "bd_create": bd_create,
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
