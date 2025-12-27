"""Custom Letta tools for Rubber Duck.

These tools are registered with Letta and can be called by the agent
during conversations.
"""

import logging
import os

from letta_client import Letta

logger = logging.getLogger(__name__)

# Tool source code - this gets sent to Letta and executed in their sandbox
# Note: Must be self-contained, can't import from our codebase
TODOIST_QUERY_TOOL_SOURCE = '''
def query_todoist(filter_query: str) -> str:
    """Query tasks from Todoist.

    Use this tool when the user asks about their tasks, todos, or what they
    should work on. Common filters:
    - "today" - tasks due today
    - "overdue" - overdue tasks
    - "@label" - tasks with a specific label (e.g., "@asa", "@krissa")
    - "#Project" - tasks in a specific project
    - "all" - all incomplete tasks

    Args:
        filter_query: Todoist filter string

    Returns:
        Formatted list of matching tasks, or a message if none found
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot query tasks."

    try:
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filter": filter_query} if filter_query and filter_query != "all" else {}
        )
        response.raise_for_status()
        tasks = response.json()

        if not tasks:
            return f"No tasks found matching '{filter_query}'."

        # Format tasks with IDs for update/complete operations
        lines = [f"Found {len(tasks)} task(s):"]
        for task in tasks[:20]:  # Limit to 20
            due = ""
            if task.get("due"):
                due = f" (due: {task['due'].get('string', task['due'].get('date', ''))})"
            labels = ""
            if task.get("labels"):
                labels = f" [{', '.join(task['labels'])}]"
            # Include task ID so it can be used for updates
            lines.append(f"- [ID:{task['id']}] {task['content']}{due}{labels}")

        if len(tasks) > 20:
            lines.append(f"... and {len(tasks) - 20} more")

        return "\\n".join(lines)

    except Exception as e:
        return f"Error querying Todoist: {str(e)}"
'''

TODOIST_UPDATE_TOOL_SOURCE = '''
def update_todoist_task(task_id: str, due_string: str = None, content: str = None) -> str:
    """Update an existing task in Todoist.

    Use this tool when the user wants to reschedule a task, change its due date,
    or modify the task content. You need the task_id from a previous query.

    Args:
        task_id: The Todoist task ID (from query results)
        due_string: New due date in natural language (e.g., "tomorrow", "Dec 29")
        content: New task content/title (optional)

    Returns:
        Confirmation message or error
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot update task."

    try:
        payload = {}
        if due_string:
            payload["due_string"] = due_string
        if content:
            payload["content"] = content

        if not payload:
            return "Nothing to update. Provide due_string or content."

        response = requests.post(
            f"https://api.todoist.com/rest/v2/tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        task = response.json()

        return f"Updated task: {task['content']}\\nNew due: {task.get('due', {}).get('string', 'none')}"

    except Exception as e:
        return f"Error updating task: {str(e)}"
'''

TODOIST_COMPLETE_TOOL_SOURCE = '''
def complete_todoist_task(task_id: str) -> str:
    """Mark a task as complete in Todoist.

    Use this tool when the user says they finished a task or wants to check it off.

    Args:
        task_id: The Todoist task ID (from query results)

    Returns:
        Confirmation message or error
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot complete task."

    try:
        response = requests.post(
            f"https://api.todoist.com/rest/v2/tasks/{task_id}/close",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        return "Task marked as complete!"

    except Exception as e:
        return f"Error completing task: {str(e)}"
'''

TODOIST_LIST_PROJECTS_SOURCE = '''
def list_todoist_projects() -> str:
    """List all projects in Todoist with their task counts.

    Use this tool to see the project hierarchy and understand how tasks are organized.
    Useful for weekly reviews or when helping the user decide what to work on.

    Returns:
        Formatted list of projects with task counts
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        # Get projects
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()

        # Get all tasks to count per project
        task_resp = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        task_resp.raise_for_status()
        tasks = task_resp.json()

        # Count tasks per project
        task_counts = {}
        for task in tasks:
            pid = task.get("project_id")
            task_counts[pid] = task_counts.get(pid, 0) + 1

        # Build project tree
        proj_by_id = {p["id"]: p for p in projects}
        roots = [p for p in projects if not p.get("parent_id")]

        def format_project(proj, indent=0):
            pid = proj["id"]
            count = task_counts.get(pid, 0)
            prefix = "  " * indent
            line = f"{prefix}- [ID:{pid}] {proj['name']} ({count} tasks)"
            children = [p for p in projects if p.get("parent_id") == pid]
            child_lines = [format_project(c, indent + 1) for c in children]
            return "\\n".join([line] + child_lines)

        lines = [format_project(r) for r in roots]
        return f"Projects:\\n" + "\\n".join(lines)

    except Exception as e:
        return f"Error listing projects: {str(e)}"
'''

TODOIST_CREATE_PROJECT_SOURCE = '''
def create_todoist_project(name: str, parent_id: str = None) -> str:
    """Create a new project in Todoist.

    Use this when the user wants to start a new project or organize tasks into a new category.

    Args:
        name: The project name
        parent_id: Optional parent project ID for nested projects

    Returns:
        Confirmation with new project details
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        payload = {"name": name}
        if parent_id:
            payload["parent_id"] = parent_id

        response = requests.post(
            "https://api.todoist.com/rest/v2/projects",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        project = response.json()

        return f"Created project: {project['name']}\\nID: {project['id']}\\nURL: {project['url']}"

    except Exception as e:
        return f"Error creating project: {str(e)}"
'''

TODOIST_ARCHIVE_PROJECT_SOURCE = '''
def archive_todoist_project(project_id: str) -> str:
    """Archive (close) a project in Todoist.

    Use this when a project is complete or no longer needed. Archived projects
    can be restored later if needed.

    Args:
        project_id: The project ID to archive

    Returns:
        Confirmation message
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        # Todoist REST API doesn't have direct archive - we delete instead
        # Note: This is permanent! For true archive, would need Sync API
        response = requests.delete(
            f"https://api.todoist.com/rest/v2/projects/{project_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()

        return f"Project {project_id} has been deleted."

    except Exception as e:
        return f"Error archiving project: {str(e)}"
'''

# =============================================================================
# GTD WORKFLOW TOOLS
# =============================================================================

GTD_MORNING_PLANNING_SOURCE = '''
def run_morning_planning() -> str:
    """Run the morning planning workflow.

    This tool queries Todoist and generates a prioritized, time-blocked plan
    for TODAY based on GTD principles:
    1. Identify overdue and due-today tasks (highest priority)
    2. Check for tasks that slipped from yesterday
    3. Apply 3-step priority algorithm (urgency → feasibility → strategic value)
    4. Generate realistic schedule for remaining day

    Call this when the user asks for:
    - "What should I work on today?"
    - "Morning planning" or "daily planning"
    - "Help me plan my day"
    - "What's on my plate?"

    Returns:
        Formatted morning plan with TOP 3 priorities and time blocks
    """
    import os
    import requests
    from datetime import datetime, date

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run morning planning."

    try:
        # Get all tasks
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()
        today_str = today.isoformat()

        # Categorize tasks by urgency
        overdue = []
        due_today = []
        due_this_week = []
        scheduled_today = []
        no_date = []

        for task in all_tasks:
            due = task.get("due")
            if not due:
                no_date.append(task)
                continue

            due_date_str = due.get("date", "")[:10]  # YYYY-MM-DD
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_until = (due_date - today).days

                if days_until < 0:
                    overdue.append((task, days_until))
                elif days_until == 0:
                    due_today.append(task)
                elif days_until <= 7:
                    due_this_week.append((task, days_until))

                # Check for scheduled (has datetime, not just date)
                if due.get("datetime") and due_date == today:
                    scheduled_today.append(task)
            except ValueError:
                no_date.append(task)

        # Sort by urgency
        overdue.sort(key=lambda x: x[1])  # Most overdue first
        due_this_week.sort(key=lambda x: x[1])  # Soonest first

        # Build the morning plan
        now = datetime.now()
        lines = []
        lines.append(f"## Morning Planning - {today.strftime('%A, %B %d')}")
        lines.append(f"*Generated at {now.strftime('%I:%M %p')}*")
        lines.append("")

        # Critical alerts
        if overdue:
            lines.append("### ⚠️ OVERDUE (Address First)")
            for task, days in overdue[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} ({abs(days)} days overdue)")
            lines.append("")

        # Today's focus
        lines.append("### 🎯 TODAY'S TOP 3 PRIORITIES")
        top_3 = []

        # Priority order: overdue, then due today, then strategic
        for task, _ in overdue[:3]:
            if len(top_3) < 3:
                top_3.append(task)
        for task in due_today:
            if len(top_3) < 3 and task not in top_3:
                top_3.append(task)
        for task, _ in due_this_week[:3]:
            if len(top_3) < 3 and task not in top_3:
                top_3.append(task)

        if top_3:
            for i, task in enumerate(top_3, 1):
                due_info = ""
                if task.get("due"):
                    due_info = f" (due: {task['due'].get('string', task['due'].get('date', ''))})"
                lines.append(f"{i}. [ID:{task['id']}] {task['content']}{due_info}")
        else:
            lines.append("*No urgent tasks - consider strategic work or clearing backlog*")
        lines.append("")

        # Scheduled tasks
        if scheduled_today:
            lines.append("### 📅 Scheduled for Today")
            for task in scheduled_today:
                time_str = task['due'].get('datetime', '')
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        time_str = dt.strftime('%I:%M %p')
                    except:
                        pass
                lines.append(f"- {time_str}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Due today (not scheduled)
        remaining_today = [t for t in due_today if t not in scheduled_today and t not in top_3]
        if remaining_today:
            lines.append("### 📋 Also Due Today")
            for task in remaining_today[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Coming up this week
        upcoming = [(t, d) for t, d in due_this_week if t not in top_3]
        if upcoming:
            lines.append("### 📆 Coming This Week")
            for task, days in upcoming[:5]:
                day_name = (today + __import__('datetime').timedelta(days=days)).strftime('%A')
                lines.append(f"- {day_name}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Summary stats
        lines.append("---")
        lines.append(f"*{len(overdue)} overdue | {len(due_today)} due today | {len([t for t, _ in due_this_week])} due this week | {len(no_date)} unscheduled*")

        return "\\n".join(lines)

    except Exception as e:
        return f"Error running morning planning: {str(e)}"
'''

GTD_END_OF_DAY_SOURCE = '''
def run_end_of_day_review() -> str:
    """Run the end-of-day review workflow.

    This tool reviews today's work and prepares for tomorrow:
    1. Identify tasks that were due today (did they get done?)
    2. Suggest rescheduling for slipped tasks
    3. Generate priority-ordered list for tomorrow

    Call this when the user asks for:
    - "End of day review"
    - "Wrap up my day"
    - "What do I need to do tomorrow?"
    - "Review my tasks"

    Returns:
        End-of-day summary with suggestions for tomorrow
    """
    import os
    import requests
    from datetime import datetime, date, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run end-of-day review."

    try:
        # Get all open tasks
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()
        tomorrow = today + timedelta(days=1)
        today_str = today.isoformat()
        tomorrow_str = tomorrow.isoformat()

        # Categorize
        overdue = []
        due_today_incomplete = []
        due_tomorrow = []
        due_this_week = []
        waiting_for = []

        for task in all_tasks:
            # Check for waiting-for label
            labels = task.get("labels", [])
            if "waiting" in labels or "waiting-for" in labels:
                waiting_for.append(task)
                continue

            due = task.get("due")
            if not due:
                continue

            due_date_str = due.get("date", "")[:10]
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_until = (due_date - today).days

                if days_until < 0:
                    overdue.append((task, days_until))
                elif days_until == 0:
                    due_today_incomplete.append(task)
                elif days_until == 1:
                    due_tomorrow.append(task)
                elif days_until <= 7:
                    due_this_week.append((task, days_until))
            except ValueError:
                pass

        # Sort
        overdue.sort(key=lambda x: x[1])

        # Build review
        now = datetime.now()
        lines = []
        lines.append(f"## End-of-Day Review - {today.strftime('%A, %B %d')}")
        lines.append(f"*Generated at {now.strftime('%I:%M %p')}*")
        lines.append("")

        # Today's incomplete work
        if due_today_incomplete or overdue:
            lines.append("### 🔄 Needs Rescheduling")
            lines.append("*These were due today/earlier but still open:*")
            for task in due_today_incomplete[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} → suggest: tomorrow")
            for task, days in overdue[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} ({abs(days)}d overdue) → suggest: tomorrow AM")
            lines.append("")
            lines.append("*Use update_todoist_task to reschedule these.*")
            lines.append("")

        # Tomorrow's priorities
        lines.append("### 🎯 TOMORROW'S PRIORITIES")

        # Build tomorrow's list: rescheduled today + already due tomorrow
        tomorrow_candidates = []
        for task in due_today_incomplete:
            tomorrow_candidates.append((task, "rescheduled from today"))
        for task, _ in overdue:
            tomorrow_candidates.append((task, "overdue"))
        for task in due_tomorrow:
            tomorrow_candidates.append((task, "due tomorrow"))

        if tomorrow_candidates:
            for i, (task, reason) in enumerate(tomorrow_candidates[:7], 1):
                lines.append(f"{i}. [ID:{task['id']}] {task['content']} ({reason})")
        else:
            lines.append("*No urgent tasks for tomorrow - check projects for strategic work*")
        lines.append("")

        # Waiting-for check
        if waiting_for:
            lines.append("### ⏳ Waiting-For Items")
            lines.append("*Consider following up on these:*")
            for task in waiting_for[:5]:
                created = task.get("created_at", "")
                if created:
                    try:
                        created_date = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
                        age = (today - created_date).days
                        age_str = f" ({age}d ago)"
                    except:
                        age_str = ""
                else:
                    age_str = ""
                lines.append(f"- [ID:{task['id']}] {task['content']}{age_str}")
            lines.append("")

        # Coming this week
        if due_this_week:
            lines.append("### 📆 Coming This Week")
            for task, days in due_this_week[:5]:
                day_name = (today + timedelta(days=days)).strftime('%A')
                lines.append(f"- {day_name}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append("**Quick Actions:**")
        lines.append("1. Reschedule slipped tasks to tomorrow")
        lines.append("2. Mark any secretly-completed tasks as done")
        lines.append("3. Add any new tasks that came up today")

        return "\\n".join(lines)

    except Exception as e:
        return f"Error running end-of-day review: {str(e)}"
'''

GTD_WEEKLY_REVIEW_SOURCE = '''
def run_weekly_review() -> str:
    """Run the weekly review workflow.

    This comprehensive GTD review covers:
    1. Project health - which projects are active, stalled, or incomplete?
    2. Waiting-for items - what needs follow-up?
    3. Overdue/upcoming deadlines
    4. Task volume by project

    Call this when the user asks for:
    - "Weekly review"
    - "How are my projects doing?"
    - "What's stalled?"
    - "Review everything"

    Returns:
        Comprehensive weekly review with project status and recommendations
    """
    import os
    import requests
    from datetime import datetime, date, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run weekly review."

    try:
        # Get projects
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()

        # Get all tasks
        task_resp = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        task_resp.raise_for_status()
        all_tasks = task_resp.json()

        today = date.today()

        # Organize tasks by project
        tasks_by_project = {}
        waiting_for = []
        overdue = []
        due_this_week = []

        for task in all_tasks:
            pid = task.get("project_id")
            if pid not in tasks_by_project:
                tasks_by_project[pid] = []
            tasks_by_project[pid].append(task)

            # Check for waiting-for
            labels = task.get("labels", [])
            if "waiting" in labels or "waiting-for" in labels:
                waiting_for.append(task)

            # Check due dates
            due = task.get("due")
            if due:
                due_date_str = due.get("date", "")[:10]
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                    days_until = (due_date - today).days
                    if days_until < 0:
                        overdue.append((task, days_until))
                    elif days_until <= 7:
                        due_this_week.append((task, days_until))
                except ValueError:
                    pass

        # Build project health report
        proj_by_id = {p["id"]: p for p in projects}

        lines = []
        lines.append(f"## Weekly Review - Week of {today.strftime('%B %d, %Y')}")
        lines.append("")

        # Urgent items first
        if overdue:
            lines.append("### 🚨 OVERDUE ITEMS")
            for task, days in sorted(overdue, key=lambda x: x[1])[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                lines.append(f"- [{proj_name}] [ID:{task['id']}] {task['content']} ({abs(days)}d overdue)")
            lines.append("")

        # This week's deadlines
        if due_this_week:
            lines.append("### 📅 DUE THIS WEEK")
            for task, days in sorted(due_this_week, key=lambda x: x[1])[:10]:
                day_name = (today + timedelta(days=days)).strftime('%A')
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                lines.append(f"- {day_name}: [{proj_name}] {task['content']}")
            lines.append("")

        # Project health
        lines.append("### 📊 PROJECT HEALTH")
        lines.append("")

        active = []
        stalled = []
        empty = []

        for proj in projects:
            pid = proj["id"]
            tasks = tasks_by_project.get(pid, [])
            count = len(tasks)

            if count == 0:
                empty.append(proj)
            elif count > 0:
                # Check if any have due dates (active) or all are floating (stalled)
                has_due = any(t.get("due") for t in tasks)
                if has_due:
                    active.append((proj, count))
                else:
                    stalled.append((proj, count))

        if active:
            lines.append("**Active Projects** (have scheduled work):")
            for proj, count in sorted(active, key=lambda x: -x[1])[:8]:
                lines.append(f"- {proj['name']}: {count} tasks")
            lines.append("")

        if stalled:
            lines.append("**⚠️ Stalled Projects** (no due dates set):")
            for proj, count in stalled[:5]:
                lines.append(f"- {proj['name']}: {count} tasks - needs next action with deadline")
            lines.append("")

        # Waiting-for items
        if waiting_for:
            lines.append("### ⏳ WAITING-FOR ITEMS")
            lines.append("*Review for follow-up:*")
            for task in waiting_for[:8]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                created = task.get("created_at", "")
                age_str = ""
                if created:
                    try:
                        created_date = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
                        age = (today - created_date).days
                        if age > 14:
                            age_str = f" ⚠️ {age}d - follow up!"
                        elif age > 7:
                            age_str = f" ({age}d - gentle check-in)"
                        else:
                            age_str = f" ({age}d)"
                    except:
                        pass
                lines.append(f"- [{proj_name}] {task['content']}{age_str}")
            lines.append("")

        # Summary stats
        lines.append("---")
        lines.append("**Summary:**")
        lines.append(f"- Total open tasks: {len(all_tasks)}")
        lines.append(f"- Overdue: {len(overdue)}")
        lines.append(f"- Due this week: {len(due_this_week)}")
        lines.append(f"- Waiting-for: {len(waiting_for)}")
        lines.append(f"- Active projects: {len(active)}")
        lines.append(f"- Stalled projects: {len(stalled)}")
        lines.append("")
        lines.append("**Recommended Actions:**")
        if overdue:
            lines.append("1. Address overdue items first")
        if stalled:
            lines.append("2. Add next actions with deadlines to stalled projects")
        if any(age > 14 for _, age in [(t, (today - datetime.fromisoformat(t.get("created_at", today.isoformat()).replace('Z', '+00:00')).date()).days) for t in waiting_for] if t.get("created_at")):
            lines.append("3. Follow up on waiting-for items older than 2 weeks")

        return "\\n".join(lines)

    except Exception as e:
        return f"Error running weekly review: {str(e)}"
'''

GTD_GET_COMPLETED_SOURCE = '''
def get_completed_tasks(since_days: int = 1) -> str:
    """Get recently completed tasks from Todoist.

    Use this to see what was accomplished recently. Useful for:
    - End-of-day reviews (what got done today)
    - Weekly reviews (what got done this week)
    - Celebrating wins and progress

    Args:
        since_days: How many days back to look (default: 1 for today)

    Returns:
        Formatted list of completed tasks
    """
    import os
    import requests
    from datetime import datetime, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        # Todoist Sync API for completed tasks
        # Note: REST API doesn't support completed tasks, need Sync API
        since = (datetime.now() - timedelta(days=since_days)).isoformat()

        response = requests.post(
            "https://api.todoist.com/sync/v9/completed/get_all",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"since": since, "limit": 50}
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            return f"No tasks completed in the last {since_days} day(s)."

        lines = [f"Completed in last {since_days} day(s): {len(items)} task(s)"]
        lines.append("")

        # Group by project
        by_project = {}
        for item in items:
            proj_id = item.get("project_id", "unknown")
            if proj_id not in by_project:
                by_project[proj_id] = []
            by_project[proj_id].append(item)

        projects = data.get("projects", {})
        for proj_id, tasks in by_project.items():
            proj_name = projects.get(str(proj_id), {}).get("name", "Unknown Project")
            lines.append(f"**{proj_name}:**")
            for task in tasks:
                completed_at = task.get("completed_at", "")
                if completed_at:
                    try:
                        dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        time_str = dt.strftime('%b %d %I:%M %p')
                    except:
                        time_str = completed_at
                else:
                    time_str = ""
                lines.append(f"  ✓ {task['content']} ({time_str})")
            lines.append("")

        return "\\n".join(lines)

    except Exception as e:
        return f"Error getting completed tasks: {str(e)}"
'''

# =============================================================================
# TASK CRUD TOOLS
# =============================================================================

TODOIST_CREATE_TOOL_SOURCE = '''
def create_todoist_task(content: str, due_string: str = None, labels: list = None) -> str:
    """Create a new task in Todoist.

    Use this tool when the user wants to add a task, reminder, or todo item.

    Args:
        content: The task title/description
        due_string: Optional due date in natural language (e.g., "tomorrow", "next monday")
        labels: Optional list of label names to apply

    Returns:
        Confirmation message with task details
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot create task."

    try:
        payload = {"content": content}
        if due_string:
            payload["due_string"] = due_string
        if labels:
            payload["labels"] = labels

        response = requests.post(
            "https://api.todoist.com/rest/v2/tasks",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        task = response.json()

        return f"Created task: {task['content']}\\nURL: {task['url']}"

    except Exception as e:
        return f"Error creating task: {str(e)}"
'''


def setup_tools(client: Letta) -> list[str]:
    """Create/update Letta tools and return their IDs.

    Args:
        client: Letta API client

    Returns:
        List of tool IDs that were created/updated
    """
    tool_ids = []

    # Create query tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_QUERY_TOOL_SOURCE,
            description="Query tasks from Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: query_todoist ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create query_todoist tool: {e}")

    # Create task creation tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_CREATE_TOOL_SOURCE,
            description="Create a task in Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: create_todoist_task ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create create_todoist_task tool: {e}")

    # Create task update tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_UPDATE_TOOL_SOURCE,
            description="Update/reschedule a task in Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: update_todoist_task ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create update_todoist_task tool: {e}")

    # Create task complete tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_COMPLETE_TOOL_SOURCE,
            description="Mark a task as complete in Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: complete_todoist_task ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create complete_todoist_task tool: {e}")

    # Create list projects tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_LIST_PROJECTS_SOURCE,
            description="List all Todoist projects with task counts",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: list_todoist_projects ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create list_todoist_projects tool: {e}")

    # Create project creation tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_CREATE_PROJECT_SOURCE,
            description="Create a new project in Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: create_todoist_project ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create create_todoist_project tool: {e}")

    # Create project archive tool
    try:
        tool = client.tools.upsert(
            source_code=TODOIST_ARCHIVE_PROJECT_SOURCE,
            description="Delete/archive a project in Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: archive_todoist_project ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create archive_todoist_project tool: {e}")

    # =========================================================================
    # GTD WORKFLOW TOOLS
    # =========================================================================

    # Morning planning tool
    try:
        tool = client.tools.upsert(
            source_code=GTD_MORNING_PLANNING_SOURCE,
            description="Run morning planning workflow - prioritizes today's tasks using GTD principles",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: run_morning_planning ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create run_morning_planning tool: {e}")

    # End-of-day review tool
    try:
        tool = client.tools.upsert(
            source_code=GTD_END_OF_DAY_SOURCE,
            description="Run end-of-day review - identifies slipped tasks and prepares tomorrow's priorities",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: run_end_of_day_review ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create run_end_of_day_review tool: {e}")

    # Weekly review tool
    try:
        tool = client.tools.upsert(
            source_code=GTD_WEEKLY_REVIEW_SOURCE,
            description="Run weekly review - checks project health, waiting-for items, and overdue tasks",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: run_weekly_review ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create run_weekly_review tool: {e}")

    # Get completed tasks tool
    try:
        tool = client.tools.upsert(
            source_code=GTD_GET_COMPLETED_SOURCE,
            description="Get recently completed tasks from Todoist",
            pip_requirements=[{"name": "requests"}],
        )
        tool_ids.append(tool.id)
        logger.info(f"Created/updated tool: get_completed_tasks ({tool.id})")
    except Exception as e:
        logger.exception(f"Failed to create get_completed_tasks tool: {e}")

    return tool_ids


def attach_tools_to_agent(client: Letta, agent_id: str, tool_ids: list[str]) -> None:
    """Attach tools to an agent.

    Args:
        client: Letta API client
        agent_id: The agent to attach tools to
        tool_ids: List of tool IDs to attach
    """
    for tool_id in tool_ids:
        try:
            client.agents.tools.attach(agent_id=agent_id, tool_id=tool_id)
            logger.info(f"Attached tool {tool_id} to agent {agent_id}")
        except Exception as e:
            # May already be attached
            if "already" in str(e).lower():
                logger.debug(f"Tool {tool_id} already attached to agent")
            else:
                logger.exception(f"Failed to attach tool {tool_id}: {e}")


def setup_agent_tools(client: Letta, agent_id: str) -> None:
    """Set up all custom tools for an agent.

    Args:
        client: Letta API client
        agent_id: The agent to set up tools for
    """
    # First, set the environment variable for the agent's sandbox
    try:
        todoist_key = os.environ.get("TODOIST_API_KEY", "")
        if todoist_key:
            # Set agent-scoped env var for tool execution
            client.agents.update(
                agent_id=agent_id,
                tool_exec_environment_variables={"TODOIST_API_KEY": todoist_key}
            )
            logger.info("Set TODOIST_API_KEY in agent's tool environment")
    except Exception as e:
        logger.warning(f"Could not set agent environment variables: {e}")

    # Create/update tools
    tool_ids = setup_tools(client)

    # Attach to agent
    if tool_ids:
        attach_tools_to_agent(client, agent_id, tool_ids)
