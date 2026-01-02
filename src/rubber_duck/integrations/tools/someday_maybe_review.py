# src/rubber_duck/integrations/tools/someday_maybe_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Someday-maybe review sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_task_age_days,
    is_someday_maybe_project,
    BACKBURNER_LABELS,
)


def _get_triage_recommendation(age_days: int | None) -> str:
    """Get triage recommendation based on age."""
    if age_days is None:
        return "keep"
    elif age_days > 365:
        return "delete"
    elif age_days > 180:
        return "review"
    else:
        return "keep"


def run_someday_maybe_review() -> str:
    """Review backburner/someday-maybe items for triage."""
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run someday-maybe review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        backburner_items = []
        for task in tasks:
            labels = {label.lower() for label in task.get("labels", [])}
            is_backburner_label = bool(labels & BACKBURNER_LABELS)
            is_backburner_project = is_someday_maybe_project(task.get("project_id"), proj_by_id)

            if is_backburner_label or is_backburner_project:
                age = calculate_task_age_days(task, today)
                rec = _get_triage_recommendation(age)
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                backburner_items.append((task, age, rec, proj_name))

        backburner_items.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)

        lines = ["## Someday-Maybe Review", ""]

        if not backburner_items:
            lines.append("*No someday-maybe items found.*")
            return "\n".join(lines)

        consider_delete = [i for i in backburner_items if i[2] == "delete"]
        needs_review = [i for i in backburner_items if i[2] == "review"]
        keep = [i for i in backburner_items if i[2] == "keep"]

        if consider_delete:
            lines.append("### 🗑️ CONSIDER DELETING")
            lines.append("*Over 1 year in backburner - still relevant?*")
            lines.append("")
            for task, age, _, proj_name in consider_delete[:5]:
                age_str = f"{age}d" if age else "?"
                lines.append(f"- [ ] **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        if needs_review:
            lines.append("### 🤔 NEEDS DECISION")
            lines.append("*6+ months old - activate or delete?*")
            lines.append("")
            for task, age, _, proj_name in needs_review[:5]:
                age_str = f"{age}d" if age else "?"
                lines.append(f"- [ ] **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        if keep:
            lines.append("### ✓ KEEP ON BACKBURNER")
            lines.append("*Still interesting, check next review*")
            lines.append("")
            for task, age, _, proj_name in keep[:10]:
                age_str = f"{age}d" if age else "new"
                lines.append(f"- {task['content']} ({age_str}) - {proj_name}")
            if len(keep) > 10:
                lines.append(f"- *...and {len(keep) - 10} more*")
            lines.append("")

        lines.append("---")
        lines.append(f"**Summary:** {len(backburner_items)} someday-maybe items ({len(consider_delete)} to delete, {len(needs_review)} to review)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running someday-maybe review: {str(e)}"
