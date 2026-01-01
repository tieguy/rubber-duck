#!/usr/bin/env python3
"""Migrate tasks from Amazing Marvin export to Todoist.

Usage:
    source .envrc
    uv run python scripts/migrate_marvin_to_todoist.py [--dry-run]
"""

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

from todoist_api_python.api import TodoistAPI

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Files
TASKS_FILE = Path("2025-12-26-marvin-tasks.jsonl")
HIERARCHY_FILE = Path("category_hierarchy.json")

# Top-level categories to import (skip "Work")
IMPORT_CATEGORIES = {"Self", "Volunteering"}

# Label mappings based on category names
# Add your own person/context labels here
PERSON_LABELS = {
    # "person_name": "@label",
}
FAMILY_KEYWORDS = ["february getaway", "family"]


def load_tasks(path: Path) -> list[dict]:
    """Load tasks from JSONL file."""
    tasks = []
    with open(path) as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    return tasks


def load_hierarchy(path: Path) -> list[dict]:
    """Load category hierarchy from JSON file."""
    with open(path) as f:
        return json.load(f)


def flatten_hierarchy(nodes: list[dict], parent_path: list[str] = None) -> dict[str, dict]:
    """Flatten hierarchy into a dict mapping ID to category info.

    Returns dict with:
        id -> {title, type, parent_id, path, top_level}
    """
    parent_path = parent_path or []
    result = {}

    for node in nodes:
        node_id = node["id"]
        title = node["title"]
        current_path = parent_path + [title]
        top_level = current_path[0] if current_path else None

        result[node_id] = {
            "title": title,
            "type": node.get("type", "category"),
            "parent_id": None,  # Will be set to Todoist project ID later
            "path": current_path,
            "top_level": top_level,
            "marvin_parent_id": parent_path[-1] if parent_path else None,
        }

        if "children" in node:
            child_results = flatten_hierarchy(node["children"], current_path)
            # Set parent references
            for child_id, child_info in child_results.items():
                if child_info["path"][:-1] == current_path:
                    child_info["marvin_parent_id"] = node_id
            result.update(child_results)

    return result


def detect_recurring_tasks(tasks: list[dict]) -> dict[str, dict]:
    """Detect recurring tasks by finding duplicates with date-prefixed IDs.

    Returns dict mapping base_id -> {title, pattern, instances}
    """
    # Pattern: YYYY-MM-DD_<uuid>
    date_prefix_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_(.+)$")

    recurring = {}
    seen_titles_by_parent = {}  # (parentId, title) -> [task_ids]

    for task in tasks:
        task_id = task["id"]
        title = task["title"]
        parent_id = task.get("parentId", "")

        match = date_prefix_pattern.match(task_id)
        if match:
            base_id = match.group(1)
            key = (parent_id, title)

            if key not in seen_titles_by_parent:
                seen_titles_by_parent[key] = []
            seen_titles_by_parent[key].append(task)

    # Find groups with multiple instances
    for (parent_id, title), instances in seen_titles_by_parent.items():
        if len(instances) > 1:
            # This is a recurring task
            base_id = date_prefix_pattern.match(instances[0]["id"]).group(1)
            recurring[base_id] = {
                "title": title,
                "parent_id": parent_id,
                "instances": instances,
                "pattern": guess_recurrence_pattern(instances),
            }

    return recurring


def guess_recurrence_pattern(instances: list[dict]) -> str:
    """Guess the recurrence pattern from task instances."""
    # Simple heuristic - if daily instances, return "every day"
    days = sorted([t.get("day", "") for t in instances if t.get("day") and t["day"] != "unassigned"])

    if len(days) >= 2:
        # Check if consecutive days
        # For simplicity, just return "every day" for daily patterns
        return "every day"

    return "every week"  # Default fallback


def get_labels_for_task(task: dict, category_info: dict) -> list[str]:
    """Determine which labels to apply to a task."""
    labels = []

    # Check for someday-maybe (from Marvin label OR backburner)
    if task.get("backburner") or "someday-maybe" in task.get("labelNames", []):
        labels.append("someday-maybe")

    # Check category path for person labels
    category_path = " ".join(category_info.get("path", [])).lower()

    for keyword, label in PERSON_LABELS.items():
        if keyword in category_path:
            labels.append(label.lstrip("@"))

    # Check for family keywords
    for keyword in FAMILY_KEYWORDS:
        if keyword in category_path:
            labels.append("family")
            break

    return list(set(labels))  # Dedupe


def create_labels(api: TodoistAPI, label_names: set[str], dry_run: bool) -> dict[str, str]:
    """Create labels in Todoist, return mapping of name -> id."""
    label_map = {}

    # Get existing labels
    try:
        existing = api.get_labels()
        # Paginator yields lists of labels
        for page in existing:
            for label in page:
                label_map[label.name] = label.id
    except Exception as e:
        logger.warning(f"Could not fetch existing labels: {e}")

    # Create missing labels
    for name in label_names:
        if name not in label_map:
            if dry_run:
                logger.info(f"[DRY RUN] Would create label: {name}")
                label_map[name] = f"dry-run-{name}"
            else:
                label = api.add_label(name=name)
                label_map[name] = label.id
                logger.info(f"Created label: {name}")
                time.sleep(0.1)  # Rate limiting

    return label_map


def create_projects(
    api: TodoistAPI,
    hierarchy: dict[str, dict],
    import_categories: set[str],
    dry_run: bool
) -> dict[str, str]:
    """Create Todoist projects from hierarchy, return mapping of marvin_id -> todoist_id."""
    project_map = {}

    # Sort by path length to create parents first
    sorted_items = sorted(hierarchy.items(), key=lambda x: len(x[1]["path"]))

    for marvin_id, info in sorted_items:
        # Skip if not in import categories
        if info["top_level"] not in import_categories:
            continue

        title = info["title"]
        parent_todoist_id = None

        # Find parent's Todoist ID
        if info["marvin_parent_id"] and info["marvin_parent_id"] in project_map:
            parent_todoist_id = project_map[info["marvin_parent_id"]]

        if dry_run:
            logger.info(f"[DRY RUN] Would create project: {' > '.join(info['path'])}")
            project_map[marvin_id] = f"dry-run-{marvin_id}"
        else:
            try:
                kwargs = {"name": title}
                if parent_todoist_id:
                    kwargs["parent_id"] = parent_todoist_id

                project = api.add_project(**kwargs)
                project_map[marvin_id] = project.id
                logger.info(f"Created project: {title}")
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to create project {title}: {e}")

    return project_map


def create_tasks(
    api: TodoistAPI,
    tasks: list[dict],
    hierarchy: dict[str, dict],
    project_map: dict[str, str],
    recurring: dict[str, dict],
    import_categories: set[str],
    dry_run: bool,
) -> int:
    """Create tasks in Todoist. Returns count of created tasks."""
    created = 0

    # Track which recurring tasks we've already created
    created_recurring = set()

    for task in tasks:
        parent_id = task.get("parentId", "")

        # Skip if category not in import list
        category_info = hierarchy.get(parent_id, {})
        if category_info.get("top_level") not in import_categories:
            continue

        # Skip if already done
        if task.get("done"):
            continue

        # Check if this is a recurring task instance
        task_id = task["id"]
        date_match = re.match(r"^\d{4}-\d{2}-\d{2}_(.+)$", task_id)
        if date_match:
            base_id = date_match.group(1)
            if base_id in recurring:
                if base_id in created_recurring:
                    continue  # Skip duplicate instances
                created_recurring.add(base_id)

                # Create as recurring task
                rec_info = recurring[base_id]
                due_string = rec_info["pattern"]
                title = rec_info["title"]
            else:
                # Date-prefixed but not detected as recurring, treat normally
                title = task["title"]
                due_string = task.get("day") if task.get("day") != "unassigned" else None
        else:
            title = task["title"]
            day = task.get("day")
            due_date = task.get("dueDate")
            due_string = due_date or (day if day != "unassigned" else None)

        # Get Todoist project ID
        todoist_project_id = project_map.get(parent_id)
        if not todoist_project_id:
            logger.warning(f"No project mapping for task: {title}")
            continue

        # Get labels
        labels = get_labels_for_task(task, category_info)

        # Build task kwargs
        kwargs = {
            "content": title,
            "project_id": todoist_project_id,
        }

        if task.get("note"):
            kwargs["description"] = task["note"]

        if due_string:
            kwargs["due_string"] = due_string

        if labels:
            kwargs["labels"] = labels

        if dry_run:
            logger.info(f"[DRY RUN] Would create task: {title[:50]}{'...' if len(title) > 50 else ''}")
            if labels:
                logger.info(f"          Labels: {labels}")
            if due_string:
                logger.info(f"          Due: {due_string}")
        else:
            try:
                api.add_task(**kwargs)
                created += 1
                logger.info(f"Created task: {title[:50]}{'...' if len(title) > 50 else ''}")
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to create task {title}: {e}")

    return created


def main():
    parser = argparse.ArgumentParser(description="Migrate Marvin tasks to Todoist")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually create anything")
    args = parser.parse_args()

    # Check for API key
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        logger.error("TODOIST_API_KEY environment variable not set")
        return 1

    # Check for input files
    if not TASKS_FILE.exists():
        logger.error(f"Tasks file not found: {TASKS_FILE}")
        return 1
    if not HIERARCHY_FILE.exists():
        logger.error(f"Hierarchy file not found: {HIERARCHY_FILE}")
        return 1

    logger.info(f"Loading tasks from {TASKS_FILE}")
    tasks = load_tasks(TASKS_FILE)
    logger.info(f"Loaded {len(tasks)} tasks")

    logger.info(f"Loading hierarchy from {HIERARCHY_FILE}")
    hierarchy_raw = load_hierarchy(HIERARCHY_FILE)
    hierarchy = flatten_hierarchy(hierarchy_raw)
    logger.info(f"Loaded {len(hierarchy)} categories/projects")

    # Detect recurring tasks
    recurring = detect_recurring_tasks(tasks)
    logger.info(f"Detected {len(recurring)} recurring task patterns")

    # Initialize API
    api = TodoistAPI(api_key)

    # Collect all needed labels
    all_labels = set()
    for task in tasks:
        parent_id = task.get("parentId", "")
        category_info = hierarchy.get(parent_id, {})
        if category_info.get("top_level") in IMPORT_CATEGORIES:
            all_labels.update(get_labels_for_task(task, category_info))

    logger.info(f"Labels to create: {all_labels}")

    # Create labels
    logger.info("Creating labels...")
    label_map = create_labels(api, all_labels, args.dry_run)

    # Create projects
    logger.info("Creating projects...")
    project_map = create_projects(api, hierarchy, IMPORT_CATEGORIES, args.dry_run)
    logger.info(f"Created {len(project_map)} projects")

    # Create tasks
    logger.info("Creating tasks...")
    created_count = create_tasks(
        api, tasks, hierarchy, project_map, recurring, IMPORT_CATEGORIES, args.dry_run
    )

    if args.dry_run:
        logger.info("[DRY RUN] No changes made")
    else:
        logger.info(f"Migration complete! Created {created_count} tasks")

    return 0


if __name__ == "__main__":
    exit(main())
