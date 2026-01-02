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
