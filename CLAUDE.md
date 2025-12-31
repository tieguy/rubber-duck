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

The bot uses Letta Cloud as the conversational brain. Letta provides:
- Persistent memory across conversations
- Claude LLM for responses
- Custom tool execution in a sandboxed environment

**Key files:**
- `src/rubber_duck/integrations/memory.py` - Letta agent management, system prompt
- `src/rubber_duck/integrations/letta_tools.py` - Tool registration and loading
- `src/rubber_duck/integrations/tools/` - Individual tool source files

### Letta Tools

Tools are Python functions that run in Letta's sandbox. They must be self-contained (no imports from our codebase).

**Tool structure:**
```
src/rubber_duck/integrations/
├── memory.py                   # Agent management, system prompt (defines available tools)
└── tools/
    ├── morning_planning.py     # GTD morning workflow
    └── weekly_review.py        # GTD weekly review
```

**Note:** Many tools described in the system prompt (Todoist CRUD, project operations) are provided by Letta Cloud's hosted tools, not local files. The `tools/` directory contains only custom workflow tools.

**To add a new custom tool:**
1. Create a `.py` file in `tools/` with a single function
2. Register it with Letta Cloud (see archive/letta-sandbox-tools/ for examples)
3. Update the system prompt in `memory.py` if the agent needs instructions

**Constraints:**
- Tools must be self-contained (imports inside the function)
- Only `requests` is available (declared in pip_requirements)
- Tool must return a string
- Docstring tells the agent when/how to use it

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
