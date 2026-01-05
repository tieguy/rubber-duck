# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Waiting-for review sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_task_age_days,
    task_url,
    WAITING_LABELS,
)


def _get_follow_up_recommendation(age_days: int | None) -> tuple[str, str]:
    """Get follow-up timing and suggested wording based on age."""
    if age_days is None or age_days < 4:
        return ("wait", "Still within normal timeline - no action needed yet.")
    elif age_days < 8:
        return ("gentle", "Just checking in on this. No rush, wanted to ensure it's on your radar.")
    elif age_days < 15:
        return ("firm", f"Following up on this from {age_days} days ago. Could you provide a status update?")
    elif age_days < 22:
        return ("urgent", f"This has been pending for {age_days} days. Need a firm timeline or we should explore alternatives.")
    else:
        return ("escalate", f"Waiting {age_days} days. May need to escalate or find workaround.")


def run_waiting_for_review() -> str:
    """Review all waiting-for items for follow-up actions."""
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run waiting-for review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        # Find waiting-for items
        waiting_items = []
        for task in tasks:
            labels = {label.lower() for label in task.get("labels", [])}
            if labels & WAITING_LABELS:
                age = calculate_task_age_days(task, today)
                action, wording = _get_follow_up_recommendation(age)
                waiting_items.append((task, age, action, wording))

        # Sort by age (oldest first)
        waiting_items.sort(key=lambda x: x[1] if x[1] is not None else -1, reverse=True)

        # Build output
        lines = ["## Waiting-For Review", ""]

        if not waiting_items:
            lines.append("*No waiting-for items found.*")
            return "\n".join(lines)

        # Group by action level
        needs_action = [w for w in waiting_items if w[2] in ("firm", "urgent", "escalate")]
        gentle_check = [w for w in waiting_items if w[2] == "gentle"]
        still_waiting = [w for w in waiting_items if w[2] == "wait"]

        if needs_action:
            lines.append("### NEEDS FOLLOW-UP")
            lines.append("")
            for task, age, action, wording in needs_action:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "?"
                icon = "🔴" if action == "escalate" else "⚠️"
                link = task_url(task["id"])
                lines.append(f"- {icon} {link} **{task['content']}** ({age_str}) - {proj_name}")
                lines.append(f"      Suggested: \"{wording}\"")
                lines.append("")

        if gentle_check:
            lines.append("### GENTLE CHECK-IN")
            lines.append("")
            for task, age, action, wording in gentle_check:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "?"
                link = task_url(task["id"])
                lines.append(f"- {link} **{task['content']}** ({age_str}) - {proj_name}")
                lines.append(f"      Suggested: \"{wording}\"")
                lines.append("")

        if still_waiting:
            lines.append("### STILL WITHIN TIMELINE")
            lines.append("")
            for task, age, action, wording in still_waiting:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "new"
                link = task_url(task["id"])
                lines.append(f"- {link} {task['content']} ({age_str}) - {proj_name}")
            lines.append("")

        lines.append("---")
        lines.append(f"**Summary:** {len(waiting_items)} waiting-for items ({len(needs_action)} need follow-up)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running waiting-for review: {str(e)}"
