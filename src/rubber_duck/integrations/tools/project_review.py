# src/rubber_duck/integrations/tools/project_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Project review sub-review for weekly review."""

from rubber_duck.integrations.project_metadata import load_project_metadata
from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    fetch_completed_tasks,
    group_by_project,
    compute_project_status,
    is_someday_maybe_project,
    task_url,
    BACKBURNER_LABELS,
    WAITING_LABELS,
)


def _get_next_action(tasks: list) -> dict | None:
    """Get highest priority actionable task."""
    actionable = [
        t for t in tasks
        if not ({label.lower() for label in t.get("labels", [])} & (BACKBURNER_LABELS | WAITING_LABELS))
    ]
    if not actionable:
        return None
    prioritized = [t for t in actionable if t.get("priority", 4) < 4]
    if prioritized:
        return min(prioritized, key=lambda t: t.get("priority", 4))
    return actionable[0]


def _format_project_line(proj: dict, meta: dict | None, task_count: int, extra: str = "") -> str:
    """Format a project line with optional metadata."""
    name = proj["name"]
    due_str = ""
    goal_line = ""

    if meta:
        if due := meta.get("due"):
            due_str = f" (due {due})"
        if goal := meta.get("goal"):
            goal_line = f"\n  Goal: {goal}"

    return f"- **{name}**{due_str}: {task_count} tasks{extra}{goal_line}"


def run_project_review() -> str:
    """Review all projects for health status."""
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run project review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        completed = fetch_completed_tasks(api_key, days=7)

        proj_by_id = {p["id"]: p for p in projects}
        tasks_by_project = group_by_project(tasks)
        completions_by_project = group_by_project(completed)

        # Load project metadata
        project_metadata = load_project_metadata()

        by_status = {"ACTIVE": [], "STALLED": [], "WAITING": [], "INCOMPLETE": []}
        someday_maybe = []

        for proj in projects:
            pid = proj["id"]
            proj_tasks = tasks_by_project.get(pid, [])
            proj_completions = completions_by_project.get(pid, [])

            if not proj_tasks and not proj_completions:
                continue

            if is_someday_maybe_project(pid, proj_by_id):
                someday_maybe.append((proj, len(proj_tasks)))
                continue

            # Get metadata for this project
            meta = project_metadata.get(proj["name"])

            # Skip categories from STALLED/INCOMPLETE tracking
            if meta and meta.get("type") == "category":
                continue

            status = compute_project_status(proj_tasks, proj_completions)
            next_action = _get_next_action(proj_tasks)
            by_status[status].append((proj, proj_tasks, proj_completions, next_action, meta))

        lines = ["## Project Review", ""]

        if by_status["ACTIVE"]:
            lines.append("### ✓ ACTIVE (making progress)")
            lines.append("")
            for proj, proj_tasks, proj_completions, _, meta in by_status["ACTIVE"][:6]:
                extra = f", {len(proj_completions)} done this week, {len(proj_tasks)} open"
                # Remove " tasks" suffix since extra already has counts
                line = _format_project_line(proj, meta, 0, extra).replace(": 0 tasks,", ":")
                lines.append(line)
            lines.append("")

        if by_status["STALLED"]:
            lines.append("### ⚠️ STALLED (has next actions, no progress)")
            lines.append("*Decision needed: better next action? defer? abandon?*")
            lines.append("")
            for proj, proj_tasks, _, next_action, meta in by_status["STALLED"][:5]:
                if next_action:
                    link = task_url(next_action['id'])
                    next_str = f" -> {link} {next_action['content'][:50]}"
                else:
                    next_str = ""
                lines.append(_format_project_line(proj, meta, len(proj_tasks), next_str))
            lines.append("")

        if by_status["WAITING"]:
            lines.append("### ⏳ WAITING (all tasks waiting-for)")
            lines.append("")
            for proj, proj_tasks, _, _, meta in by_status["WAITING"][:5]:
                lines.append(_format_project_line(proj, meta, len(proj_tasks), " waiting-for items").replace(" tasks ", " "))
            lines.append("")

        if by_status["INCOMPLETE"]:
            lines.append("### 🔴 INCOMPLETE (needs next action)")
            lines.append("*GTD requires every project have a next action*")
            lines.append("")
            for proj, proj_tasks, _, _, meta in by_status["INCOMPLETE"][:5]:
                lines.append(_format_project_line(proj, meta, len(proj_tasks), ", needs next action defined"))
            lines.append("")

        lines.append("---")
        lines.append(f"**Summary:** {len(by_status['ACTIVE'])} active, {len(by_status['STALLED'])} stalled, {len(by_status['WAITING'])} waiting, {len(by_status['INCOMPLETE'])} incomplete")
        if someday_maybe:
            lines.append(f"*(Plus {len(someday_maybe)} someday-maybe projects)*")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running project review: {str(e)}"
