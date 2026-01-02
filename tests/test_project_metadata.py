# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for project metadata utilities."""

from unittest.mock import patch

import pytest


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary state directory with metadata file path."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    metadata_file = state_dir / "projects-metadata.yaml"
    with patch(
        "rubber_duck.integrations.project_metadata.METADATA_PATH",
        metadata_file,
    ):
        yield metadata_file


def test_load_empty_returns_empty_dict(temp_state_dir):
    """Loading non-existent file returns empty dict."""
    from rubber_duck.integrations.project_metadata import load_project_metadata

    result = load_project_metadata()
    assert result == {}


def test_load_existing_file(temp_state_dir):
    """Loading existing file returns parsed content."""
    from rubber_duck.integrations.project_metadata import load_project_metadata

    temp_state_dir.write_text("""
projects:
  "Kitchen Renovation":
    type: project
    goal: "Complete remodel"
""")
    result = load_project_metadata()
    assert "Kitchen Renovation" in result
    assert result["Kitchen Renovation"]["type"] == "project"
    assert result["Kitchen Renovation"]["goal"] == "Complete remodel"


def test_get_project_meta_found(temp_state_dir):
    """Get metadata for existing project."""
    from rubber_duck.integrations.project_metadata import get_project_meta

    temp_state_dir.write_text("""
projects:
  "Kitchen Renovation":
    type: project
    goal: "Complete remodel"
""")
    result = get_project_meta("Kitchen Renovation")
    assert result is not None
    assert result["type"] == "project"


def test_get_project_meta_not_found(temp_state_dir):
    """Get metadata for non-existent project returns None."""
    from rubber_duck.integrations.project_metadata import get_project_meta

    result = get_project_meta("Nonexistent")
    assert result is None


def test_save_creates_file(temp_state_dir):
    """Saving creates file if it doesn't exist."""
    from rubber_duck.integrations.project_metadata import (
        load_project_metadata,
        save_project_metadata,
    )

    save_project_metadata({"Test Project": {"type": "project", "goal": "Test goal"}})

    result = load_project_metadata()
    assert "Test Project" in result


def test_load_malformed_yaml_returns_empty_dict(temp_state_dir):
    """Loading malformed YAML returns empty dict and logs warning."""
    from rubber_duck.integrations.project_metadata import load_project_metadata

    temp_state_dir.write_text("not: valid: yaml: content: {{{")
    result = load_project_metadata()
    assert result == {}


def test_set_project_metadata_creates_new(temp_state_dir):
    """Setting metadata for new project creates entry."""
    from rubber_duck.integrations.project_metadata import (
        get_project_meta,
        set_project_metadata,
    )

    result = set_project_metadata(
        project_name="New Project",
        project_type="project",
        goal="Build something",
    )

    assert "New Project" in result
    meta = get_project_meta("New Project")
    assert meta["type"] == "project"
    assert meta["goal"] == "Build something"


def test_set_project_metadata_updates_existing(temp_state_dir):
    """Setting metadata for existing project merges fields."""
    from rubber_duck.integrations.project_metadata import (
        get_project_meta,
        set_project_metadata,
    )

    # Create initial entry
    set_project_metadata(
        project_name="My Project",
        project_type="project",
        goal="Original goal",
        context="Some context",
    )

    # Update just the goal
    set_project_metadata(
        project_name="My Project",
        project_type="project",
        goal="Updated goal",
    )

    meta = get_project_meta("My Project")
    assert meta["goal"] == "Updated goal"
    assert meta["context"] == "Some context"  # Preserved


def test_set_project_metadata_category(temp_state_dir):
    """Setting category type works."""
    from rubber_duck.integrations.project_metadata import (
        get_project_meta,
        set_project_metadata,
    )

    set_project_metadata(
        project_name="Family",
        project_type="category",
        context="Ongoing family stuff",
    )

    meta = get_project_meta("Family")
    assert meta["type"] == "category"
    assert meta["context"] == "Ongoing family stuff"


def test_set_project_metadata_returns_created_for_new(temp_state_dir):
    """Creating new project returns 'Created' message."""
    from rubber_duck.integrations.project_metadata import set_project_metadata

    result = set_project_metadata(
        project_name="Brand New",
        project_type="project",
        goal="Test",
    )
    assert "Created" in result


def test_set_project_metadata_returns_updated_for_existing(temp_state_dir):
    """Updating existing project returns 'Updated' message."""
    from rubber_duck.integrations.project_metadata import set_project_metadata

    set_project_metadata(project_name="Existing", project_type="project", goal="First")
    result = set_project_metadata(project_name="Existing", project_type="project", goal="Second")
    assert "Updated" in result


def test_set_project_metadata_invalid_type(temp_state_dir):
    """Invalid project type returns error message."""
    from rubber_duck.integrations.project_metadata import set_project_metadata

    result = set_project_metadata(
        project_name="Test",
        project_type="invalid",
        goal="Test",
    )
    assert "Invalid type" in result
    assert "'invalid'" in result


def test_find_projects_without_metadata(temp_state_dir):
    """Find Todoist projects that lack metadata entries."""
    from rubber_duck.integrations.project_metadata import (
        find_projects_without_metadata,
        save_project_metadata,
    )

    # Metadata exists for one project
    save_project_metadata({
        "Known Project": {"type": "project", "goal": "Do stuff"}
    })

    # Simulate Todoist projects
    todoist_projects = [
        {"id": "1", "name": "Known Project"},
        {"id": "2", "name": "Unknown Project"},
        {"id": "3", "name": "Another Unknown"},
    ]

    result = find_projects_without_metadata(todoist_projects)
    assert len(result) == 2
    assert "Unknown Project" in [p["name"] for p in result]
    assert "Another Unknown" in [p["name"] for p in result]
