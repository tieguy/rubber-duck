def update_todoist_project(project_id: str, name: str = None, is_favorite: bool = None) -> str:
    """Update/rename a project in Todoist.

    Use this when the user wants to rename a project or change its favorite status.

    Args:
        project_id: The project ID to update
        name: New name for the project (optional)
        is_favorite: Whether to mark as favorite (optional)

    Returns:
        Confirmation with updated project details
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    if not name and is_favorite is None:
        return "Please provide a new name or favorite status to update."

    try:
        payload = {}
        if name:
            payload["name"] = name
        if is_favorite is not None:
            payload["is_favorite"] = is_favorite

        response = requests.post(
            f"https://api.todoist.com/rest/v2/projects/{project_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        project = response.json()

        return f"Updated project: {project['name']}\nID: {project['id']}\nFavorite: {project.get('is_favorite', False)}"

    except Exception as e:
        return f"Error updating project: {str(e)}"
