---
name: managing-gtd
description: GTD (Getting Things Done) workflow system. Routes to daily planning or weekly review based on user request. Use when user mentions GTD, daily planning, weekly review, or productivity workflows.
---

# GTD Workflow System

This skill system implements GTD (Getting Things Done) workflows.

## Available Workflows

**Daily Planning** - Morning routine to identify today's priorities
- Trigger: "morning planning", "daily planning", "what should I work on today"
- See: [daily.md](daily.md)

**Weekly Review** - Comprehensive review of all open loops
- Trigger: "weekly review", "review projects", "GTD review"
- See: [weekly.md](weekly.md)

## CLI Tools

All workflows use these JSON-returning CLI commands:

```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
uv run python -m rubber_duck.cli.gtd check-projects
uv run python -m rubber_duck.cli.gtd check-waiting
uv run python -m rubber_duck.cli.gtd check-someday
uv run python -m rubber_duck.cli.gtd calendar-today
uv run python -m rubber_duck.cli.gtd calendar-range --days-back 7 --days-forward 14
```

## Task Link Format

Format all task links as: `[🔗](https://todoist.com/app/task/{id})`
