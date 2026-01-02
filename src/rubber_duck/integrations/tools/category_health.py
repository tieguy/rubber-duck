# src/rubber_duck/integrations/tools/category_health.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Category health sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    group_by_project,
    calculate_task_age_days,
)


def run_category_health() -> str:
    """Analyze task distribution across projects/categories."""
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run category health."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        tasks_by_project = group_by_project(tasks)
        project_stats = []
        total_tasks = len(tasks)

        for proj in projects:
            pid = proj["id"]
            proj_tasks = tasks_by_project.get(pid, [])
            if not proj_tasks:
                continue

            count = len(proj_tasks)
            aging = sum(1 for t in proj_tasks if (age := calculate_task_age_days(t, today)) and age > 14)

            project_stats.append({
                "name": proj["name"],
                "count": count,
                "aging": aging,
                "percent": round(count / total_tasks * 100) if total_tasks else 0,
            })

        project_stats.sort(key=lambda x: x["count"], reverse=True)

        overloaded = [p for p in project_stats if p["count"] > 15 or p["aging"] > 5]
        neglected = [p for p in project_stats if p["aging"] == p["count"] and p["count"] > 0]

        lines = ["## Category Health", ""]
        lines.append("### Task Distribution")
        lines.append("")

        for stat in project_stats[:10]:
            bar_len = min(stat["percent"] // 5, 20)
            bar = "█" * bar_len
            aging_note = f" ({stat['aging']} aging)" if stat["aging"] > 0 else ""
            lines.append(f"- **{stat['name']}**: {stat['count']} tasks ({stat['percent']}%) {bar}{aging_note}")

        if len(project_stats) > 10:
            remaining = sum(p["count"] for p in project_stats[10:])
            lines.append(f"- *...and {len(project_stats) - 10} more projects with {remaining} tasks*")
        lines.append("")

        if overloaded:
            lines.append("### ⚠️ Potentially Overloaded")
            lines.append("*Consider: defer some tasks, break into smaller chunks*")
            lines.append("")
            for stat in overloaded[:5]:
                lines.append(f"- **{stat['name']}**: {stat['count']} tasks, {stat['aging']} aging")
            lines.append("")

        if neglected:
            lines.append("### 🔴 All Tasks Aging")
            lines.append("*No recent activity - either activate or move to backburner*")
            lines.append("")
            for stat in neglected[:5]:
                lines.append(f"- **{stat['name']}**: {stat['count']} tasks, all 2+ weeks old")
            lines.append("")

        total_aging = sum(p["aging"] for p in project_stats)
        lines.append("---")
        lines.append(f"**Summary:** {total_tasks} tasks across {len(project_stats)} projects ({total_aging} aging)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running category health: {str(e)}"
