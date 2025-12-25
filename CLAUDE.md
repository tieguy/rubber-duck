# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rubber Duck is a Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

Key components:
- **Discord bot** for chat interface
- **Claude Agent SDK** for agentic behavior with MCP tools
- **Todoist** (via MCP) for task management
- **Letta Cloud** for persistent conversational memory
- **Fly.io** for deployment

See `docs/plans/2025-12-25-rubber-duck-design.md` for full architecture.

## Worktrees

Use `.worktrees/` for isolated development branches.

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

### Environment Variables

- `GITHUB_TOKEN` is set from `RUBBER_DUCK_GH_TOKEN` environment variable

## Commands

Once the project has a pyproject.toml, use uv for package management:
```bash
uv sync          # Install dependencies
uv run <cmd>     # Run commands in the virtual environment
uv add <pkg>     # Add a dependency
```
