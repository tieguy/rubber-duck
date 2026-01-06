"""Deadline scanning for GTD workflows."""

from datetime import date, datetime


def _categorize_by_urgency(tasks: list, today: date) -> dict:
    """Categorize tasks by deadline urgency.

    Args:
        tasks: List of task dicts with 'id', 'content', 'due', 'project_id'
        today: Reference date for calculations

    Returns:
        Dict with overdue, due_today, due_this_week lists and summary
    """
    overdue = []
    due_today = []
    due_this_week = []

    for task in tasks:
        due = task.get("due")
        if not due or not due.get("date"):
            continue

        due_date_str = due["date"][:10]
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        days_diff = (due_date - today).days

        base_info = {
            "id": task["id"],
            "content": task["content"],
            "project": task.get("project_id", ""),
        }

        if days_diff < 0:
            overdue.append({
                **base_info,
                "days_overdue": abs(days_diff),
            })
        elif days_diff == 0:
            has_time = "datetime" in due
            due_today.append({
                **base_info,
                "has_time": has_time,
                "time": due.get("datetime", "")[-5:] if has_time else None,
            })
        elif days_diff <= 7:
            due_this_week.append({
                **base_info,
                "due_date": due_date_str,
                "days_until": days_diff,
            })

    # Sort by urgency
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    due_this_week.sort(key=lambda x: x["days_until"])

    return {
        "overdue": overdue,
        "due_today": due_today,
        "due_this_week": due_this_week,
        "summary": {
            "overdue": len(overdue),
            "due_today": len(due_today),
            "due_this_week": len(due_this_week),
        },
    }


def scan_deadlines() -> dict:
    """Scan tasks for deadline urgency.

    Returns dict with keys: overdue, due_today, due_this_week, summary
    """
    raise NotImplementedError
