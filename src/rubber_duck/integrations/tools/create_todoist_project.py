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

        return f"Created project: {project['name']}\nID: {project['id']}\nURL: {project['url']}"

    except Exception as e:
        return f"Error creating project: {str(e)}"
