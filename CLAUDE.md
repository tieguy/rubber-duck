# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rubber Duck is a Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

Key components:
- **Discord bot** for chat interface
- **Anthropic SDK** for LLM reasoning (Claude Opus 4.5)
- **Letta Cloud** for persistent memory blocks only (no LLM calls)
- **Todoist** for task management (via local tools)
- **APScheduler** for scheduled nudges
- **Fly.io** for deployment (planned)

Architecture follows Strix's three-tier memory pattern - see `docs/plans/2025-12-31-strix-architecture-design.md`.

## Architecture

### Three-Tier Memory (Strix Pattern)

**Tier 1 - Core Identity (Letta Memory Blocks):** Always loaded into system prompt.
- `persona`: Facts about owner
- `bot_values`: Bot identity and principles
- `patterns`: Observed behavioral patterns
- `guidelines`, `communication`: Operating rules, tone
- `current_focus`, `schedule`, `file_index`: Index pointers

**Tier 2 - Long-Term Memory (Letta Archival):** Searchable via `search_memory` tool.
- Past conversations, insights, preferences, project context

**Tier 3 - Working Memory (Journal + Files):** Session context.
- `state/journal.jsonl`: Unified conversation/tool log
- `state/inbox.md`, `state/today.md`: Working files
- Recent context auto-injected from journal

### Agent Loop

The agent loop (`agent/loop.py`) calls Anthropic directly:
1. Load memory blocks from Letta
2. Build system prompt with blocks embedded
3. Call Claude Opus 4.5 with tools
4. Execute tool calls locally
5. Log everything to journal.jsonl

**Key file:** `src/rubber_duck/integrations/memory.py` - Letta agent/memory management

### Agent Tools

All tools execute locally in the Python process (not in Letta's sandbox). Defined in `src/rubber_duck/agent/tools.py`.

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
├── loop.py                     # Agent loop: Anthropic calls + tool execution
├── tools.py                    # Tool definitions, schemas, execute_tool()
└── utils.py                    # Async helpers

src/rubber_duck/integrations/
├── memory.py                   # Letta client, memory block management
├── todoist.py                  # Todoist API client
├── gcal.py                     # Google Calendar integration
└── tools/
    ├── morning_planning.py     # GTD morning workflow
    └── weekly_review.py        # GTD weekly review
```

**To add a new tool:**
1. Add function to `agent/tools.py`
2. Add schema to `TOOL_SCHEMAS` list
3. Add to `TOOL_FUNCTIONS` dict
4. Update system prompt in `loop.py:_build_system_prompt()` if needed

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

## Private Configuration

This repo is designed to be public. Private data lives in `state/` (gitignored, persistent on Fly.io).

**Nudge config:** `state/nudges.yaml` (see `config/nudges.yaml.example` for template)

**Private docs** (gitignored):
- `docs/brainstorm-context.md`
- `docs/plans/2025-12-25-rubber-duck-design.md`
