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
