# Project Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Store and surface per-project metadata (goals, context, due dates, links) to enrich weekly reviews and task creation.

**Architecture:** YAML file at `state/projects-metadata.yaml` with load/save utilities in `project_metadata.py`. New tool `set_project_metadata` for bot updates. Weekly review tools enriched to show metadata and filter categories.

**Tech Stack:** Python, PyYAML (already a dependency via other packages), pytest

---

### Task 1: Create project_metadata.py with load/save utilities

**Files:**
- Create: `src/rubber_duck/integrations/project_metadata.py`
- Test: `tests/test_project_metadata.py`

**Step 1: Write the failing tests**

```python
# tests/test_project_metadata.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for project metadata utilities."""

from pathlib import Path
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

    save_project_metadata({
        "Test Project": {"type": "project", "goal": "Test goal"}
    })

    result = load_project_metadata()
    assert "Test Project" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_project_metadata.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

```python
# src/rubber_duck/integrations/project_metadata.py
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
    except (yaml.YAMLError, IOError) as e:
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_project_metadata.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add src/rubber_duck/integrations/project_metadata.py tests/test_project_metadata.py
git commit -m "feat: add project metadata load/save utilities"
```

---

### Task 2: Add set_project_metadata tool

**Files:**
- Modify: `src/rubber_duck/integrations/project_metadata.py`
- Modify: `tests/test_project_metadata.py`

**Step 1: Add test for set_project_metadata**

Add to `tests/test_project_metadata.py`:

```python
def test_set_project_metadata_creates_new(temp_state_dir):
    """Setting metadata for new project creates entry."""
    from rubber_duck.integrations.project_metadata import (
        set_project_metadata,
        get_project_meta,
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
        set_project_metadata,
        get_project_meta,
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
        set_project_metadata,
        get_project_meta,
    )

    set_project_metadata(
        project_name="Family",
        project_type="category",
        context="Ongoing family stuff",
    )

    meta = get_project_meta("Family")
    assert meta["type"] == "category"
    assert meta["context"] == "Ongoing family stuff"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_project_metadata.py::test_set_project_metadata_creates_new -v`
Expected: FAIL with "ImportError" (function doesn't exist)

**Step 3: Add set_project_metadata function**

Add to `src/rubber_duck/integrations/project_metadata.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_project_metadata.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
git add src/rubber_duck/integrations/project_metadata.py tests/test_project_metadata.py
git commit -m "feat: add set_project_metadata function"
```

---

### Task 3: Register set_project_metadata as agent tool

**Files:**
- Modify: `src/rubber_duck/agent/tools.py`

**Step 1: Add import and tool function**

Add near other imports at top of `tools.py`:

```python
from rubber_duck.integrations.project_metadata import (
    get_project_meta,
    set_project_metadata as _set_project_metadata,
)
```

Add wrapper function (near other tool functions):

```python
def set_project_metadata(
    project_name: str,
    project_type: str,
    goal: str | None = None,
    context: str | None = None,
    due: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Set metadata for a Todoist project or category.

    Args:
        project_name: Exact Todoist project name
        project_type: "project" or "category"
        goal: Definition of done (projects only)
        context: Background info
        due: Deadline as ISO date
        links: Reference URLs or file paths

    Returns:
        Confirmation message
    """
    return _set_project_metadata(
        project_name=project_name,
        project_type=project_type,
        goal=goal,
        context=context,
        due=due,
        links=links,
    )
```

**Step 2: Add tool schema to TOOL_SCHEMAS**

Add to `TOOL_SCHEMAS` list:

```python
{
    "name": "set_project_metadata",
    "description": "Set metadata for a Todoist project or category. Use to store goals, context, due dates, and links that Todoist cannot hold.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Exact Todoist project name",
            },
            "project_type": {
                "type": "string",
                "enum": ["project", "category"],
                "description": "project (has goal/end state) or category (ongoing, no end state)",
            },
            "goal": {
                "type": "string",
                "description": "Definition of done (for projects)",
            },
            "context": {
                "type": "string",
                "description": "Background, constraints, stakeholders",
            },
            "due": {
                "type": "string",
                "description": "Deadline as ISO date, e.g. '2026-06-01'",
            },
            "links": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference URLs or file paths",
            },
        },
        "required": ["project_name", "project_type"],
    },
},
```

**Step 3: Add to TOOL_FUNCTIONS dict**

Add to `TOOL_FUNCTIONS`:

```python
"set_project_metadata": set_project_metadata,
```

**Step 4: Verify tool is registered**

Run: `uv run python -c "from rubber_duck.agent.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS; print('set_project_metadata' in TOOL_FUNCTIONS)"`
Expected: `True`

**Step 5: Commit**

```bash
git add src/rubber_duck/agent/tools.py
git commit -m "feat: register set_project_metadata as agent tool"
```

---

### Task 4: Add get_project_metadata tool for on-demand queries

**Files:**
- Modify: `src/rubber_duck/agent/tools.py`

**Step 1: Add tool function**

```python
def get_project_metadata(project_name: str) -> str:
    """Get metadata for a Todoist project or category.

    Args:
        project_name: Exact Todoist project name

    Returns:
        Formatted metadata or message if not found
    """
    meta = get_project_meta(project_name)
    if not meta:
        return f"No metadata found for '{project_name}'."

    lines = [f"**{project_name}** ({meta.get('type', 'unknown')})"]

    if goal := meta.get("goal"):
        lines.append(f"**Goal:** {goal}")
    if due := meta.get("due"):
        lines.append(f"**Due:** {due}")
    if context := meta.get("context"):
        lines.append(f"**Context:** {context}")
    if links := meta.get("links"):
        lines.append("**Links:**")
        for link in links:
            lines.append(f"  - {link}")

    return "\n".join(lines)
```

**Step 2: Add tool schema**

Add to `TOOL_SCHEMAS`:

```python
{
    "name": "get_project_metadata",
    "description": "Get stored metadata for a Todoist project or category. Returns goal, context, due date, and links.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Exact Todoist project name",
            },
        },
        "required": ["project_name"],
    },
},
```

**Step 3: Add to TOOL_FUNCTIONS**

```python
"get_project_metadata": get_project_metadata,
```

**Step 4: Verify**

Run: `uv run python -c "from rubber_duck.agent.tools import TOOL_FUNCTIONS; print('get_project_metadata' in TOOL_FUNCTIONS)"`
Expected: `True`

**Step 5: Commit**

```bash
git add src/rubber_duck/agent/tools.py
git commit -m "feat: add get_project_metadata tool for on-demand queries"
```

---

### Task 5: Enrich project_review.py with metadata

**Files:**
- Modify: `src/rubber_duck/integrations/tools/project_review.py`

**Step 1: Add import**

```python
from rubber_duck.integrations.project_metadata import load_project_metadata
```

**Step 2: Load metadata and add helper function**

Add helper function:

```python
def _format_project_line(proj: dict, meta: dict | None, task_count: int, extra: str = "") -> str:
    """Format a project line with optional metadata."""
    name = proj["name"]
    due_str = ""
    goal_line = ""

    if meta:
        if due := meta.get("due"):
            due_str = f" (due {due})"
        if goal := meta.get("goal"):
            goal_line = f"\n  Goal: {goal}"

    return f"- **{name}**{due_str}: {task_count} tasks{extra}{goal_line}"
```

**Step 3: Modify run_project_review to use metadata**

In `run_project_review()`, after fetching projects:

```python
# Load project metadata
project_metadata = load_project_metadata()
```

Then modify the loop to skip categories from STALLED/INCOMPLETE:

```python
for proj in projects:
    pid = proj["id"]
    proj_tasks = tasks_by_project.get(pid, [])
    proj_completions = completions_by_project.get(pid, [])

    if not proj_tasks and not proj_completions:
        continue

    if is_someday_maybe_project(pid, proj_by_id):
        someday_maybe.append((proj, len(proj_tasks)))
        continue

    # Get metadata for this project
    meta = project_metadata.get(proj["name"])

    # Skip categories from STALLED/INCOMPLETE tracking
    if meta and meta.get("type") == "category":
        continue

    status = compute_project_status(proj_tasks, proj_completions)
    next_action = _get_next_action(proj_tasks)
    by_status[status].append((proj, proj_tasks, proj_completions, next_action, meta))
```

Update the output sections to include metadata:

```python
if by_status["STALLED"]:
    lines.append("### STALLED (has next actions, no progress)")
    lines.append("*Decision needed: better next action? defer? abandon?*")
    lines.append("")
    for proj, proj_tasks, _, next_action, meta in by_status["STALLED"][:5]:
        next_str = f" -> {next_action['content'][:50]}" if next_action else ""
        lines.append(_format_project_line(proj, meta, len(proj_tasks), next_str))
    lines.append("")
```

**Step 4: Run existing tests**

Run: `uv run pytest tests/test_weekly_conductor.py -v`
Expected: All pass (no breaking changes)

**Step 5: Commit**

```bash
git add src/rubber_duck/integrations/tools/project_review.py
git commit -m "feat: enrich project review with metadata, filter categories"
```

---

### Task 6: Add helper to identify projects without metadata

**Files:**
- Modify: `src/rubber_duck/integrations/project_metadata.py`
- Modify: `tests/test_project_metadata.py`

**Step 1: Add test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_project_metadata.py::test_find_projects_without_metadata -v`
Expected: FAIL

**Step 3: Implement function**

Add to `project_metadata.py`:

```python
def find_projects_without_metadata(todoist_projects: list[dict]) -> list[dict]:
    """Find Todoist projects that have no metadata entry.

    Args:
        todoist_projects: List of Todoist project dicts with 'name' key

    Returns:
        List of projects without metadata entries
    """
    metadata = load_project_metadata()
    return [p for p in todoist_projects if p["name"] not in metadata]
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_project_metadata.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/rubber_duck/integrations/project_metadata.py tests/test_project_metadata.py
git commit -m "feat: add helper to find projects without metadata"
```

---

### Task 7: Update system prompt for metadata tools

**Files:**
- Modify: `src/rubber_duck/agent/loop.py`

**Step 1: Find system prompt section**

Locate the `_build_system_prompt()` function and add guidance about project metadata tools.

**Step 2: Add metadata guidance**

Add after the Weekly Review Sessions section:

```python
## Project Metadata

You can store and retrieve per-project context that Todoist cannot hold:

**Types:**
- **project**: Has a goal, due date, end state. Track progress in weekly reviews.
- **category**: Ongoing area (Family, Health, Work). No end state, excluded from stalled warnings.

**Tools:**
- `set_project_metadata`: Store goal, context, due date, links for a project
- `get_project_metadata`: Retrieve stored metadata

**When to prompt for metadata:**
When you encounter a project without stored metadata during reviews or task creation, ask:
"I don't have context for 'Project Name' - any details you'd like to add? (goal, due date, context)"

Assume new entries are projects (not categories) unless user says otherwise.
```

**Step 3: Verify prompt builds**

Run: `uv run python -c "from rubber_duck.agent.loop import _build_system_prompt; print('Project Metadata' in _build_system_prompt([]))"`
Expected: `True`

**Step 4: Commit**

```bash
git add src/rubber_duck/agent/loop.py
git commit -m "feat: add project metadata guidance to system prompt"
```

---

### Task 8: Integration test

**Files:**
- None (verification only)

**Step 1: Run all project metadata tests**

Run: `uv run pytest tests/test_project_metadata.py -v`
Expected: All pass

**Step 2: Verify all tools registered**

Run: `uv run python -c "from rubber_duck.agent.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS; tools = ['set_project_metadata', 'get_project_metadata']; print(all(t in TOOL_FUNCTIONS for t in tools))"`
Expected: `True`

**Step 3: Test round-trip**

Run:
```bash
uv run python -c "
from rubber_duck.integrations.project_metadata import set_project_metadata, get_project_meta
set_project_metadata('Test Project', 'project', goal='Test goal', context='Test context')
meta = get_project_meta('Test Project')
print(f'Goal: {meta[\"goal\"]}')
print(f'Type: {meta[\"type\"]}')
"
```
Expected:
```
Goal: Test goal
Type: project
```

**Step 4: Clean up test file**

Run: `rm -f state/projects-metadata.yaml`

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete project metadata implementation" --allow-empty
```

---

## Summary

8 tasks implementing:
1. Core load/save utilities
2. set_project_metadata function
3. Register set tool with agent
4. Add get_project_metadata tool
5. Enrich project_review.py output
6. Helper to find missing metadata
7. System prompt guidance
8. Integration verification
