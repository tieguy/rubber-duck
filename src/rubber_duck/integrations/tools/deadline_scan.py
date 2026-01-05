# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Deadline scan sub-review for weekly review."""

from datetime import date, timedelta

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_days_until_due,
    task_url,
)


def run_deadline_scan() -> str:
    """Scan tasks for deadline issues.

    Groups tasks by urgency:
    - OVERDUE: Past their deadline
    - DUE THIS WEEK: 0-7 days
    - DUE NEXT WEEK: 8-14 days

    Returns:
        Formatted deadline scan results with action recommendations
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run deadline scan."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        # Categorize by urgency
        overdue = []
        due_this_week = []
        due_next_week = []

        for task in tasks:
            days = calculate_days_until_due(task, today)
            if days is None:
                continue

            if days < 0:
                overdue.append((task, days))
            elif days <= 7:
                due_this_week.append((task, days))
            elif days <= 14:
                due_next_week.append((task, days))

        # Sort by urgency
        overdue.sort(key=lambda x: x[1])  # Most overdue first
        due_this_week.sort(key=lambda x: x[1])
        due_next_week.sort(key=lambda x: x[1])

        # Build output
        lines = ["## Deadline Scan", ""]

        if overdue:
            lines.append("### OVERDUE - Decision Required")
            lines.append("*For each: reschedule realistically, complete now, or delete if no longer needed*")
            lines.append("")
            for task, days in overdue[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                link = task_url(task["id"])
                lines.append(f"- [ ] {link} **{task['content']}** ({abs(days)}d overdue) - {proj_name}")
            lines.append("")
        else:
            lines.append("### OVERDUE")
            lines.append("*None - great job staying on top of deadlines!*")
            lines.append("")

        if due_this_week:
            lines.append("### DUE THIS WEEK")
            lines.append("*Schedule specific time blocks for these*")
            lines.append("")
            for task, days in due_this_week[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                day_name = (today + timedelta(days=days)).strftime("%A") if days > 0 else "Today"
                link = task_url(task["id"])
                lines.append(f"- [ ] {link} **{task['content']}** (due {day_name}) - {proj_name}")
            lines.append("")

        if due_next_week:
            lines.append("### DUE NEXT WEEK")
            lines.append("*Identify any preparation needed*")
            lines.append("")
            for task, days in due_next_week[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                day_name = (today + timedelta(days=days)).strftime("%A, %b %d")
                link = task_url(task["id"])
                lines.append(f"- [ ] {link} **{task['content']}** (due {day_name}) - {proj_name}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(f"**Summary:** {len(overdue)} overdue, {len(due_this_week)} due this week, {len(due_next_week)} due next week")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running deadline scan: {str(e)}"
