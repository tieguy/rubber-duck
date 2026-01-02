# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Project and category metadata storage."""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent.parent
METADATA_PATH = REPO_ROOT / "state" / "projects-metadata.yaml"


def load_project_metadata() -> dict:
    """Load project metadata from YAML file.

    Returns:
        Dict mapping project names to their metadata, or empty dict if file
        doesn't exist or is malformed.
    """
    if not METADATA_PATH.exists():
        return {}

    try:
        with open(METADATA_PATH) as f:
            data = yaml.safe_load(f)
        return data.get("projects", {}) if data else {}
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Could not load project metadata: {e}")
        return {}


def get_project_meta(project_name: str) -> dict | None:
    """Get metadata for a specific project.

    Args:
        project_name: Exact project name (case-sensitive)

    Returns:
        Metadata dict or None if not found.
    """
    metadata = load_project_metadata()
    return metadata.get(project_name)


def save_project_metadata(projects: dict) -> None:
    """Save project metadata to YAML file.

    Args:
        projects: Dict mapping project names to metadata
    """
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_PATH, "w") as f:
        yaml.safe_dump({"projects": projects}, f, default_flow_style=False, allow_unicode=True)


def set_project_metadata(
    project_name: str,
    project_type: str,
    goal: str | None = None,
    context: str | None = None,
    due: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Create or update metadata for a project/category.

    Args:
        project_name: Exact Todoist project name
        project_type: "project" or "category"
        goal: Definition of done (projects only)
        context: Background, constraints, stakeholders
        due: Deadline as ISO date (projects only)
        links: List of URLs or file paths

    Returns:
        Confirmation message
    """
    if project_type not in ("project", "category"):
        return f"Invalid type '{project_type}'. Must be 'project' or 'category'."

    metadata = load_project_metadata()

    # Get existing or create new entry
    existing = metadata.get(project_name, {})

    # Build updated entry, preserving existing fields not specified
    updated = {"type": project_type}

    # Merge fields - only update if explicitly provided (not None)
    for field, value in [
        ("goal", goal),
        ("context", context),
        ("due", due),
        ("links", links),
    ]:
        if value is not None:
            updated[field] = value
        elif field in existing:
            updated[field] = existing[field]

    metadata[project_name] = updated
    save_project_metadata(metadata)

    action = "Updated" if project_name in metadata else "Created"
    return f"{action} metadata for '{project_name}' ({project_type})."
