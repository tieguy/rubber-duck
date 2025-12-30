def update_todoist_project(project_id: str, name: str = None, parent_id: str = None, is_favorite: bool = None) -> str:
    """Update, rename, or move a project in Todoist.

    Use this when the user wants to:
    - Rename a project
    - Move a project under another parent (or to top level)
    - Change favorite status

    Args:
        project_id: The project ID to update
        name: New name for the project (optional)
        parent_id: New parent project ID to move under, or "none" for top level (optional)
        is_favorite: Whether to mark as favorite (optional)

    Returns:
        Confirmation with updated project details
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    if not name and parent_id is None and is_favorite is None:
        return "Please provide a new name, parent_id, or favorite status to update."

    try:
        payload = {}
        if name:
            payload["name"] = name
        if parent_id is not None:
            # "none" or empty string means move to top level (no parent)
            if parent_id.lower() in ("none", "null", ""):
                payload["parent_id"] = None
            else:
                payload["parent_id"] = parent_id
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

        parent_info = f"\nParent: {project.get('parent_id', 'none')}" if 'parent_id' in project else ""
        return f"Updated project: {project['name']}\nID: {project['id']}{parent_info}\nFavorite: {project.get('is_favorite', False)}"

    except Exception as e:
        return f"Error updating project: {str(e)}"
