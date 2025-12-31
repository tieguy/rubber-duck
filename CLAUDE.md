# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rubber Duck is a Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

Key components:
- **Discord bot** for chat interface
- **Letta Cloud** for persistent conversational memory + Claude LLM
- **Todoist** for task management (via Letta custom tools)
- **APScheduler** for scheduled nudges
- **Fly.io** for deployment (planned)

See `docs/plans/2025-12-25-rubber-duck-design.md` for full architecture.

## Architecture

### Letta Integration

The bot uses Letta Cloud for persistent memory across conversations. Letta stores:
- Memory blocks (persona, patterns, current_focus, etc.)
- Archival memory (searchable long-term storage)

**Key file:** `src/rubber_duck/integrations/memory.py` - Agent management, system prompt

### Agent Tools

The bot uses a local agent loop with Claude that has access to tools defined in `src/rubber_duck/agent/tools.py`.

**Available tools:**
- **File ops**: `read_file`, `write_file`, `list_directory`
- **Git**: `git_status`, `git_commit`
- **Memory**: `get_memory_blocks`, `set_memory_block`, `search_memory`, `archive_to_memory`, `read_journal`
- **Todoist**: `query_todoist`, `create_todoist_task`, `complete_todoist_task`, `update_todoist_task`, `move_todoist_task`, `list_todoist_projects`
- **Calendar**: `query_gcal`
- **GTD workflows**: `run_morning_planning`, `run_weekly_review`

**Key files:**
```
src/rubber_duck/agent/
├── tools.py                    # All tool definitions + schemas
├── loop.py                     # Agent execution loop
└── utils.py                    # Async helpers

src/rubber_duck/integrations/
├── memory.py                   # Letta memory/agent management
├── todoist.py                  # Todoist API client
├── gcal.py                     # Google Calendar integration
└── tools/
    ├── morning_planning.py     # GTD morning workflow implementation
    └── weekly_review.py        # GTD weekly review implementation
```

**To add a new tool:**
1. Add function to `agent/tools.py`
2. Add schema to `TOOL_SCHEMAS` list
3. Add to `TOOL_FUNCTIONS` dict
4. Update system prompt in `memory.py` if agent needs usage instructions

### GTD Workflows

The bot implements GTD (Getting Things Done) principles via workflow tools:
- **Morning planning**: TOP 3 priorities, overdue alerts, today's schedule
- **End-of-day review**: Slipped tasks, tomorrow's priorities, waiting-for items
- **Weekly review**: Project health, deadline scan, follow-up timing

Priority algorithm: urgency → feasibility → strategic value

## Issue Tracking

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Development Environment

This project uses a devcontainer with:
- **uv** for Python package management
- **Node.js** for tooling
- **GitHub CLI** for repository operations
- **Homebrew** for additional packages (including `bd` CLI)

### Container Setup

The devcontainer mounts:
- `~/.claude` and `~/.claude.json` for Claude Code configuration
- `~/Projects` as read-only at `/projects`

### Commands

```bash
uv sync          # Install dependencies
uv run <cmd>     # Run commands in the virtual environment
uv add <pkg>     # Add a dependency
```

## Worktrees

Use `.worktrees/` for isolated development branches.
