# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""CLI tool wrappers for Claude Code skills.

This module provides a CLI interface to Rubber Duck's integrations,
allowing Claude Code to invoke them via its Bash tool.

All commands output JSON to stdout for easy parsing.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta


def output_json(data: dict) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data, default=str))


def output_error(message: str) -> None:
    """Print error as JSON to stdout."""
    output_json({"success": False, "error": message})


def output_success(data: dict | list | None = None) -> None:
    """Print success result as JSON to stdout."""
    result = {"success": True}
    if data is not None:
        result["data"] = data
    output_json(result)


# =============================================================================
# Todoist Commands
# =============================================================================


def todoist_query(args: argparse.Namespace) -> bool:
    """Query Todoist tasks by filter."""
    from rubber_duck.integrations import todoist

    try:
        tasks = asyncio.run(todoist.get_tasks_by_filter(args.filter))
        output_success(tasks)
        return True
    except Exception as e:
        output_error(f"Failed to query Todoist: {e}")
        return False


def todoist_create(args: argparse.Namespace) -> bool:
    """Create a Todoist task."""
    from rubber_duck.integrations import todoist

    try:
        labels = args.labels.split(",") if args.labels else None
        task = asyncio.run(
            todoist.create_task(
                content=args.content,
                description=args.description or "",
                labels=labels,
                due_string=args.due,
                project_id=args.project_id,
            )
        )
        if task:
            output_success(task)
            return True
        else:
            output_error("Failed to create task (no API key or error)")
            return False
    except Exception as e:
        output_error(f"Failed to create task: {e}")
        return False


def todoist_complete(args: argparse.Namespace) -> bool:
    """Complete a Todoist task."""
    from rubber_duck.integrations import todoist

    try:
        success = asyncio.run(todoist.complete_task(args.task_id))
        if success:
            output_success({"task_id": args.task_id, "completed": True})
            return True
        else:
            output_error("Failed to complete task (no API key or error)")
            return False
    except Exception as e:
        output_error(f"Failed to complete task: {e}")
        return False


def todoist_projects(args: argparse.Namespace) -> bool:
    """List Todoist projects."""
    from rubber_duck.integrations import todoist

    try:
        projects = asyncio.run(todoist.list_projects())
        output_success(projects)
        return True
    except Exception as e:
        output_error(f"Failed to list projects: {e}")
        return False


# =============================================================================
# Memory Commands
# =============================================================================


def memory_get_blocks(args: argparse.Namespace) -> bool:
    """Get all memory blocks from Letta."""
    from rubber_duck.integrations import memory

    try:
        client = memory.get_client()
        if not client:
            output_error("Letta client not configured (LETTA_API_KEY not set)")
            return False

        agent_id = asyncio.run(memory.get_or_create_agent())
        if not agent_id:
            output_error("Failed to get or create agent")
            return False

        blocks = client.agents.blocks.list(agent_id=agent_id)
        block_data = [
            {
                "label": b.label,
                "value": b.value,
                "id": b.id,
            }
            for b in blocks
        ]
        output_success(block_data)
        return True
    except Exception as e:
        output_error(f"Failed to get memory blocks: {e}")
        return False


def memory_set_block(args: argparse.Namespace) -> bool:
    """Set a memory block value in Letta."""
    from rubber_duck.integrations import memory

    try:
        client = memory.get_client()
        if not client:
            output_error("Letta client not configured (LETTA_API_KEY not set)")
            return False

        agent_id = asyncio.run(memory.get_or_create_agent())
        if not agent_id:
            output_error("Failed to get or create agent")
            return False

        # Find the block by label
        blocks = client.agents.blocks.list(agent_id=agent_id)
        block_id = None
        for b in blocks:
            if b.label == args.label:
                block_id = b.id
                break

        if not block_id:
            output_error(f"Block with label '{args.label}' not found")
            return False

        # Update the block
        client.agents.blocks.update(block_id=block_id, value=args.value)
        output_success({"label": args.label, "updated": True})
        return True
    except Exception as e:
        output_error(f"Failed to set memory block: {e}")
        return False


def memory_search(args: argparse.Namespace) -> bool:
    """Search archival memory in Letta."""
    from rubber_duck.integrations import memory

    try:
        client = memory.get_client()
        if not client:
            output_error("Letta client not configured (LETTA_API_KEY not set)")
            return False

        agent_id = asyncio.run(memory.get_or_create_agent())
        if not agent_id:
            output_error("Failed to get or create agent")
            return False

        results = client.agents.archival_memory.search(
            agent_id=agent_id,
            query=args.query,
            limit=args.limit,
        )
        memory_data = [
            {
                "id": r.id,
                "text": r.text,
                "created_at": r.created_at,
            }
            for r in results
        ]
        output_success(memory_data)
        return True
    except Exception as e:
        output_error(f"Failed to search memory: {e}")
        return False


def memory_archive(args: argparse.Namespace) -> bool:
    """Archive text to Letta archival memory."""
    from rubber_duck.integrations import memory

    try:
        client = memory.get_client()
        if not client:
            output_error("Letta client not configured (LETTA_API_KEY not set)")
            return False

        agent_id = asyncio.run(memory.get_or_create_agent())
        if not agent_id:
            output_error("Failed to get or create agent")
            return False

        result = client.agents.archival_memory.insert(
            agent_id=agent_id,
            text=args.text,
        )
        output_success({"archived": True, "id": result.id if hasattr(result, "id") else None})
        return True
    except Exception as e:
        output_error(f"Failed to archive to memory: {e}")
        return False


# =============================================================================
# Google Calendar Commands
# =============================================================================


def gcal_query(args: argparse.Namespace) -> bool:
    """Query Google Calendar events."""
    from rubber_duck.integrations import gcal

    try:
        # Parse time range
        time_min = None
        time_max = None

        if args.range == "today":
            now = datetime.now()
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif args.range == "tomorrow":
            tomorrow = datetime.now() + timedelta(days=1)
            time_min = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif args.range == "week":
            now = datetime.now()
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=7)
        # else: use defaults (now to end of today)

        events = asyncio.run(
            gcal.get_events(
                calendar_id=args.calendar_id,
                time_min=time_min,
                time_max=time_max,
                max_results=args.max_results,
            )
        )
        output_success(events)
        return True
    except Exception as e:
        output_error(f"Failed to query calendar: {e}")
        return False


# =============================================================================
# CLI Parser
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="rubber_duck.cli.tools",
        description="CLI tool wrappers for Rubber Duck integrations",
    )
    subparsers = parser.add_subparsers(dest="service", required=True)

    # ---------------------------------------------------------------------
    # Todoist commands
    # ---------------------------------------------------------------------
    todoist_parser = subparsers.add_parser("todoist", help="Todoist operations")
    todoist_subparsers = todoist_parser.add_subparsers(dest="command", required=True)

    # todoist query
    query_parser = todoist_subparsers.add_parser("query", help="Query tasks by filter")
    query_parser.add_argument("filter", help="Todoist filter (e.g., 'today', '@home', '#Project')")
    query_parser.set_defaults(func=todoist_query)

    # todoist create
    create_parser = todoist_subparsers.add_parser("create", help="Create a task")
    create_parser.add_argument("content", help="Task content/title")
    create_parser.add_argument("--due", help="Due date string (e.g., 'tomorrow')")
    create_parser.add_argument("--project-id", dest="project_id", help="Project ID")
    create_parser.add_argument("--labels", help="Comma-separated labels")
    create_parser.add_argument("--description", help="Task description")
    create_parser.set_defaults(func=todoist_create)

    # todoist complete
    complete_parser = todoist_subparsers.add_parser("complete", help="Complete a task")
    complete_parser.add_argument("task_id", help="Task ID to complete")
    complete_parser.set_defaults(func=todoist_complete)

    # todoist projects
    projects_parser = todoist_subparsers.add_parser("projects", help="List projects")
    projects_parser.set_defaults(func=todoist_projects)

    # ---------------------------------------------------------------------
    # Memory commands
    # ---------------------------------------------------------------------
    memory_parser = subparsers.add_parser("memory", help="Letta memory operations")
    memory_subparsers = memory_parser.add_subparsers(dest="command", required=True)

    # memory get-blocks
    get_blocks_parser = memory_subparsers.add_parser("get-blocks", help="Get all memory blocks")
    get_blocks_parser.set_defaults(func=memory_get_blocks)

    # memory set-block
    set_block_parser = memory_subparsers.add_parser("set-block", help="Set a memory block")
    set_block_parser.add_argument("label", help="Block label")
    set_block_parser.add_argument("value", help="Block value")
    set_block_parser.set_defaults(func=memory_set_block)

    # memory search
    search_parser = memory_subparsers.add_parser("search", help="Search archival memory")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    search_parser.set_defaults(func=memory_search)

    # memory archive
    archive_parser = memory_subparsers.add_parser("archive", help="Archive to memory")
    archive_parser.add_argument("text", help="Text to archive")
    archive_parser.set_defaults(func=memory_archive)

    # ---------------------------------------------------------------------
    # Google Calendar commands
    # ---------------------------------------------------------------------
    gcal_parser = subparsers.add_parser("gcal", help="Google Calendar operations")
    gcal_subparsers = gcal_parser.add_subparsers(dest="command", required=True)

    # gcal query
    gcal_query_parser = gcal_subparsers.add_parser("query", help="Query calendar events")
    gcal_query_parser.add_argument(
        "--range",
        choices=["today", "tomorrow", "week"],
        default="today",
        help="Time range to query",
    )
    gcal_query_parser.add_argument(
        "--calendar-id",
        dest="calendar_id",
        default="primary",
        help="Calendar ID",
    )
    gcal_query_parser.add_argument(
        "--max-results",
        dest="max_results",
        type=int,
        default=20,
        help="Maximum number of events",
    )
    gcal_query_parser.set_defaults(func=gcal_query)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "func"):
        success = args.func(args)
        if not success:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
