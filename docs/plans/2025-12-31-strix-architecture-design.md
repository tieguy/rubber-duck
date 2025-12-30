# Strix-Style Architecture Redesign

Date: 2025-12-31

## Overview

Refactor Rubber Duck to follow Strix's memory architecture: Letta for persistent memory blocks, Anthropic/Opus for LLM reasoning, full self-modification capability via file and git tools.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Fly.io (LAX)                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  rubber-duck (Python)                                 │  │
│  │                                                       │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌───────────┐ │  │
│  │  │  Discord    │───▶│   Agent     │───▶│ Anthropic │ │  │
│  │  │  Gateway    │    │   Loop      │    │  (Opus)   │ │  │
│  │  └─────────────┘    └──────┬──────┘    └───────────┘ │  │
│  │                            │                          │  │
│  │         ┌──────────────────┼──────────────────┐       │  │
│  │         ▼                  ▼                  ▼       │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌───────────┐ │  │
│  │  │ File Tools  │    │ Letta Tools │    │ External  │ │  │
│  │  │ (git repo)  │    │ (memory)    │    │ (Todoist, │ │  │
│  │  │             │    │             │    │  GCal)    │ │  │
│  │  └─────────────┘    └─────────────┘    └───────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key changes from current architecture:**
- Agent loop calls Anthropic directly (not through Letta)
- Letta becomes a tool for memory operations only
- File tools enable self-modification
- Context assembled from Letta blocks + on-demand file loading

## Memory Tier Structure

### Tier 1: Core Blocks (Letta - always in context)

| Block | Purpose |
|-------|---------|
| persona | Owner info, relationship, preferences |
| bot_values | Identity, name, behavioral principles |
| patterns | Observed behavioral patterns |
| guidelines | Operating rules, integrity requirements |
| communication | Tone, style, constraints |

### Tier 2: Index Blocks (Letta - always in context)

| Block | Purpose |
|-------|---------|
| current_focus | What we're working on, pointers to files |
| schedule | Upcoming nudges, events affecting behavior |
| file_index | Map of state/ directory contents |

### Tier 3: State Files (Git - loaded on demand)

```
state/
├── inbox.md           # Unprocessed thoughts, quick captures
├── today.md           # Current priorities (max 3)
├── insights/          # Dated insight files
│   └── YYYY-MM-DD.md
└── journal.jsonl      # Unified conversation + tool log
config/
└── nudges.yaml        # Self-modifiable nudge config
```

### Context Assembly Flow

1. Load all Letta memory blocks (core + index)
2. Index blocks tell the LLM what files exist
3. LLM uses `read_file` tool to load what it needs
4. After conversation, LLM updates blocks/files as needed

## Tool Definitions

### File Operations

```python
read_file(path: str) -> str
write_file(path: str, content: str) -> str
list_directory(path: str) -> list[str]
```

### Git Operations

```python
git_commit(message: str, paths: list[str] | None = None) -> str
git_status() -> str
```

### Letta Memory

```python
get_memory_blocks() -> dict[str, str]
set_memory_block(name: str, value: str) -> str
search_memory(query: str) -> list[str]
```

### External Services

```python
# Todoist
query_todoist(filter: str) -> str
create_todoist_task(...) -> str
update_todoist_task(...) -> str
complete_todoist_task(task_id: str) -> str

# Calendar
query_gcal(days: int = 7) -> str
```

All tools run locally in the Python process, not in Letta's sandbox.

## Agent Loop

```
Discord Message (or scheduled nudge)
       │
       ▼
┌──────────────────┐
│ 1. Load Context  │
│   - Get all Letta memory blocks
│   - Build system prompt with blocks embedded
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Call Opus     │◀─────────────────┐
│   - System prompt + user message    │
│   - Available tools                 │
└────────┬─────────┘                  │
         │                            │
         ▼                            │
    ┌────────────┐                    │
    │ Tool call? │───yes──▶ Execute ──┘
    └─────┬──────┘           tool
          │ no               (log to journal.jsonl)
          ▼
┌──────────────────┐
│ 3. Send Response │
│   - Reply to Discord
│   - Log to journal.jsonl
└──────────────────┘
```

### Unified Logging

All events logged to `state/journal.jsonl`:

```jsonl
{"ts": "...", "type": "user_message", "content": "..."}
{"ts": "...", "type": "tool_call", "tool": "read_file", "args": {...}}
{"ts": "...", "type": "tool_result", "tool": "read_file", "result": "..."}
{"ts": "...", "type": "assistant_message", "content": "..."}
```

## System Prompt Structure

Assembled at each turn from Letta blocks:

```
You are Rubber Duck, a helpful assistant for {owner_name}.

## Core Identity
{bot_values block}

## Communication Style
{communication block}

## Guidelines
{guidelines block}

## About Your Owner
{persona block}

## Observed Patterns
{patterns block}

## Current Focus
{current_focus block}

## Schedule Awareness
{schedule block}

## Available State Files
{file_index block}

## Tools
[tool descriptions]

## Key Principles
- If you didn't write it down, you won't remember it next message
- Commit important changes to git for provenance
- Update memory blocks when you learn something persistent
- Use state files for working memory and tasks
```

## Migration Strategy

### What stays the same
- Discord bot framework (`discord.py`)
- Scheduler (`APScheduler`)
- Fly.io deployment
- Todoist/GCal integration logic (ported to local execution)

### What changes

| Current | New |
|---------|-----|
| Letta agent handles LLM + tools | Anthropic SDK for LLM, local tools |
| Tools in Letta sandbox | Tools in Python process |
| System prompt in memory.py | Assembled from Letta blocks |
| No self-modification | Full file/git access |

### Migration Steps

1. Add `anthropic` SDK, create agent loop module
2. Implement local tools (file ops, git ops, Letta memory ops)
3. Port Todoist/GCal tools from Letta sandbox to local
4. Initialize Letta memory blocks (core + index tiers)
5. Create `state/` directory structure
6. Wire Discord handler to new agent loop
7. Update scheduler to use new agent
8. Test, then deploy

## Error Handling & Safety

### Tool Execution
- Errors returned to LLM as tool results (let it handle)
- Critical failures (API down) logged and surfaced

### Self-Modification Safety
- All changes via git - full rollback capability
- Bot cannot modify `.git/` directory
- If bot breaks itself, redeploy from good commit

### Resource Limits
- Max 20 tool calls per conversation turn
- Max 100KB file size for read/write
- 60s timeout on Anthropic API calls

### Philosophy
Trust the bot, use git as safety net, iterate.

## Follow-up Work

- `rubber-duck-462`: Prime memory with owner context (life, family, routine, GTD, ADHD)
- Future: bash execution (when trust is established)
- Future: web_fetch, proactive Discord messaging

## Reference

Architecture inspired by Strix:
- https://timkellogg.me/blog/2025/12/30/strix-memory
- https://timkellogg.me/blog/2025/12/15/strix
