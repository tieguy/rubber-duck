---
name: todoist-tasks
description: Query, create, update, and complete Todoist tasks. Use when user mentions tasks, todos, to-dos, Todoist, or needs to manage work items.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Todoist Task Management

Query, create, and complete tasks in the user's Todoist.

## Query Tasks

```bash
uv run python -m rubber_duck.cli.tools todoist query "today | overdue"
```

Common filters:
- `today` - tasks due today
- `overdue` - overdue tasks
- `today | overdue` - both
- `#ProjectName` - tasks in a project
- `@label` - tasks with a label
- `all` - all tasks

## Create Task

```bash
uv run python -m rubber_duck.cli.tools todoist create "Task content" --due "tomorrow" --project-id "PROJECT_ID"
```

Options:
- `--due` - due date (e.g., "tomorrow", "next monday", "Jan 15")
- `--project-id` - project ID (get from `todoist projects`)
- `--labels` - comma-separated labels
- `--description` - task description

## Complete Task

```bash
uv run python -m rubber_duck.cli.tools todoist complete TASK_ID
```

## List Projects

```bash
uv run python -m rubber_duck.cli.tools todoist projects
```

## Output Format

All commands return JSON:
```json
{"success": true, "data": [...]}
{"success": false, "error": "Error message"}
```
