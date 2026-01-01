# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Weekly review workflow for GTD-based project health assessment."""

import os
from datetime import date, datetime, timedelta

import requests

# Label sets for categorization
BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}
SOMEDAY_PROJECT_NAMES = {"someday-maybe", "someday maybe", "someday/maybe", "someday"}


def _fetch_todoist_data(api_key: str) -> tuple[list, list, list]:
    """Fetch projects, tasks, and completed tasks from Todoist."""
    headers = {"Authorization": f"Bearer {api_key}"}

    proj_resp = requests.get(
        "https://api.todoist.com/rest/v2/projects",
        headers=headers
    )
    proj_resp.raise_for_status()
    projects = proj_resp.json()

    task_resp = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers=headers
    )
    task_resp.raise_for_status()
    all_tasks = task_resp.json()

    since = (datetime.now() - timedelta(days=7)).isoformat()
    completed_resp = requests.post(
        "https://api.todoist.com/sync/v9/completed/get_all",
        headers=headers,
        json={"since": since, "limit": 200}
    )
    completed_resp.raise_for_status()
    completed_tasks = completed_resp.json().get("items", [])

    return projects, all_tasks, completed_tasks


def _group_by_project(items: list, key: str = "project_id") -> dict:
    """Group items by project ID."""
    grouped = {}
    for item in items:
        pid = item.get(key)
        if pid not in grouped:
            grouped[pid] = []
        grouped[pid].append(item)
    return grouped


def _categorize_tasks(all_tasks: list, today: date) -> dict:
    """Categorize tasks into waiting-for, overdue, and due this week."""
    result = {
        "by_project": {},
        "waiting_for": [],
        "overdue": [],
        "due_this_week": [],
    }

    for task in all_tasks:
        pid = task.get("project_id")
        if pid not in result["by_project"]:
            result["by_project"][pid] = []
        result["by_project"][pid].append(task)

        labels = task.get("labels", [])
        if "waiting" in labels or "waiting-for" in labels:
            result["waiting_for"].append(task)

        due = task.get("due")
        if due:
            due_date_str = due.get("date", "")[:10]
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_until = (due_date - today).days
                if days_until < 0:
                    result["overdue"].append((task, days_until))
                elif days_until <= 7:
                    result["due_this_week"].append((task, days_until))
            except ValueError:
                pass

    return result


def _is_someday_maybe(project_id: str, proj_by_id: dict) -> bool:
    """Check if project or any ancestor is named 'someday-maybe'."""
    current_id = project_id
    while current_id:
        proj = proj_by_id.get(current_id)
        if not proj:
            break
        if proj.get("name", "").lower().strip() in SOMEDAY_PROJECT_NAMES:
            return True
        current_id = proj.get("parent_id")
    return False


def _compute_project_status(tasks: list, completions: list) -> str:
    """Compute project health status based on GTD principles."""
    if completions:
        return "ACTIVE"

    next_actions = []
    waiting_actions = []

    for task in tasks:
        labels = {label.lower() for label in task.get("labels", [])}
        if labels & BACKBURNER_LABELS:
            continue
        elif labels & WAITING_LABELS:
            waiting_actions.append(task)
        else:
            next_actions.append(task)

    if not next_actions and not waiting_actions:
        return "INCOMPLETE"
    if not next_actions and waiting_actions:
        return "WAITING"
    return "STALLED"


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


def _format_overdue_section(overdue: list, proj_by_id: dict) -> list[str]:
    """Format overdue items section."""
    if not overdue:
        return []

    lines = ["### OVERDUE ITEMS"]
    for task, days in sorted(overdue, key=lambda x: x[1])[:10]:
        proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
        lines.append(f"- [{proj_name}] [ID:{task['id']}] {task['content']} ({abs(days)}d overdue)")
    lines.append("")
    return lines


def _format_due_this_week_section(due_this_week: list, today: date, proj_by_id: dict) -> list[str]:
    """Format due this week section."""
    if not due_this_week:
        return []

    lines = ["### DUE THIS WEEK"]
    for task, days in sorted(due_this_week, key=lambda x: x[1])[:10]:
        day_name = (today + timedelta(days=days)).strftime("%A")
        proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
        lines.append(f"- {day_name}: [{proj_name}] {task['content']}")
    lines.append("")
    return lines


def _format_project_status_section(status: str, projects: list, emoji: str, description: str) -> list[str]:
    """Format a project status category."""
    if not projects:
        return []

    lines = [f"**{status}** ({description}):"]
    for proj_data in projects[:6 if status == "ACTIVE" else 5]:
        proj = proj_data[0]
        task_count = proj_data[1]

        if status == "ACTIVE":
            comp_count = proj_data[2]
            lines.append(f"- {emoji} {proj['name']}: {comp_count} done, {task_count} open")
        elif status == "STALLED":
            next_task = proj_data[3]
            next_str = f" → {next_task['content'][:40]}" if next_task else ""
            lines.append(f"- {emoji} {proj['name']}: {task_count} tasks{next_str}")
        elif status == "WAITING":
            lines.append(f"- {emoji} {proj['name']}: {task_count} waiting-for items")
        else:  # INCOMPLETE
            lines.append(f"- {emoji} {proj['name']}: needs next action defined")

    lines.append("")
    return lines


def _format_someday_maybe_section(projects: list) -> list[str]:
    """Format someday-maybe projects section."""
    if not projects:
        return []

    lines = ["**SOMEDAY-MAYBE** (on hold, not assessed):"]
    for proj, task_count in projects[:5]:
        lines.append(f"- 💤 {proj['name']}: {task_count} tasks")
    if len(projects) > 5:
        lines.append(f"  ... and {len(projects) - 5} more")
    lines.append("")
    return lines


def _calculate_waiting_age(created: str, today: date) -> str:
    """Calculate and format waiting-for item age."""
    if not created:
        return ""
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
        age = (today - created_date).days
        if age > 14:
            return f" !! {age}d - follow up!"
        elif age > 7:
            return f" ({age}d - gentle check-in)"
        return f" ({age}d)"
    except (ValueError, AttributeError):
        return ""


def _format_waiting_for_section(waiting_for: list, today: date, proj_by_id: dict) -> list[str]:
    """Format waiting-for items section."""
    if not waiting_for:
        return []

    lines = ["### WAITING-FOR ITEMS", "*Review for follow-up:*"]
    for task in waiting_for[:8]:
        proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
        age_str = _calculate_waiting_age(task.get("created_at", ""), today)
        lines.append(f"- [{proj_name}] {task['content']}{age_str}")
    lines.append("")
    return lines


def _format_summary(all_tasks: list, completed_tasks: list, overdue: list,
                    due_this_week: list, waiting_for: list, projects_by_status: dict,
                    someday_count: int) -> list[str]:
    """Format summary and recommendations section."""
    lines = [
        "---",
        "**Summary:**",
        f"- Total open tasks: {len(all_tasks)}",
        f"- Completed this week: {len(completed_tasks)}",
        f"- Overdue: {len(overdue)}",
        f"- Due this week: {len(due_this_week)}",
        f"- Waiting-for: {len(waiting_for)}",
        f"- Projects: {len(projects_by_status['ACTIVE'])} active, "
        f"{len(projects_by_status['STALLED'])} stalled, "
        f"{len(projects_by_status['WAITING'])} waiting, "
        f"{len(projects_by_status['INCOMPLETE'])} incomplete, "
        f"{someday_count} someday-maybe",
        "",
        "**Recommended Actions:**",
    ]

    action_num = 1
    if overdue:
        lines.append(f"{action_num}. Address overdue items first")
        action_num += 1
    if projects_by_status["STALLED"]:
        lines.append(f"{action_num}. Make progress on stalled projects (they have next actions)")
        action_num += 1
    if projects_by_status["INCOMPLETE"]:
        lines.append(f"{action_num}. Define next actions for incomplete projects")
        action_num += 1
    if waiting_for:
        lines.append(f"{action_num}. Check waiting-for items older than 2 weeks")

    return lines


def run_weekly_review() -> str:
    """Run the weekly review workflow.

    This comprehensive GTD review covers:
    1. Project health - which projects are active, stalled, or incomplete?
    2. Waiting-for items - what needs follow-up?
    3. Overdue/upcoming deadlines
    4. Task volume by project

    Returns:
        Comprehensive weekly review with project status and recommendations
    """
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run weekly review."

    try:
        projects, all_tasks, completed_tasks = _fetch_todoist_data(api_key)
        today = date.today()

        # Organize data
        task_data = _categorize_tasks(all_tasks, today)
        completions_by_project = _group_by_project(completed_tasks)
        proj_by_id = {p["id"]: p for p in projects}

        # Assess project health
        projects_by_status = {"ACTIVE": [], "STALLED": [], "WAITING": [], "INCOMPLETE": []}
        someday_maybe_projects = []

        for proj in projects:
            pid = proj["id"]
            tasks = task_data["by_project"].get(pid, [])
            completions = completions_by_project.get(pid, [])

            if not tasks and not completions:
                continue

            if _is_someday_maybe(pid, proj_by_id):
                someday_maybe_projects.append((proj, len(tasks)))
                continue

            status = _compute_project_status(tasks, completions)
            next_action = _get_next_action(tasks)
            projects_by_status[status].append((proj, len(tasks), len(completions), next_action))

        # Build output
        lines = [
            f"## Weekly Review - Week of {today.strftime('%B %d, %Y')}",
            "",
        ]

        lines.extend(_format_overdue_section(task_data["overdue"], proj_by_id))
        lines.extend(_format_due_this_week_section(task_data["due_this_week"], today, proj_by_id))

        lines.extend(["### PROJECT HEALTH", ""])
        lines.extend(_format_project_status_section("ACTIVE", projects_by_status["ACTIVE"], "✓", "completed tasks this week"))
        lines.extend(_format_project_status_section("STALLED", projects_by_status["STALLED"], "⚠️", "next actions exist but no recent progress"))
        lines.extend(_format_project_status_section("WAITING", projects_by_status["WAITING"], "⏳", "all tasks waiting-for"))
        lines.extend(_format_project_status_section("INCOMPLETE", projects_by_status["INCOMPLETE"], "🔴", "no actionable next actions"))
        lines.extend(_format_someday_maybe_section(someday_maybe_projects))

        lines.extend(_format_waiting_for_section(task_data["waiting_for"], today, proj_by_id))
        lines.extend(_format_summary(
            all_tasks, completed_tasks, task_data["overdue"],
            task_data["due_this_week"], task_data["waiting_for"],
            projects_by_status, len(someday_maybe_projects)
        ))

        return "\n".join(lines)

    except Exception as e:
        return f"Error running weekly review: {str(e)}"
