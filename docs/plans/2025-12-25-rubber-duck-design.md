# Rubber Duck Design

Date: 2025-12-25

## Overview

Rubber Duck is a Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

## Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Bot runtime | Fly.io (SFO) | Always-on Python process |
| Chat interface | Discord | DM-based conversation |
| Agent brain | Claude Agent SDK | Tool use, synthesis, reasoning |
| Task backend | Todoist (MCP) | Query/create tasks |
| Memory | Letta Cloud | Persistent conversational memory |
| Scheduling | APScheduler | Config-driven nudge times |

## Architecture

```
┌─────────────────────────────────────────────┐
│              Fly.io (SFO)                   │
│  ┌────────────────────────────────────┐     │
│  │  rubber-duck (Python)              │     │
│  │  - Discord bot (always listening)  │     │
│  │  - Scheduler (config-driven)       │     │
│  │  - Claude Agent SDK                │     │
│  │    └─ MCP: Todoist                 │     │
│  │    └─ MCP: Letta (or direct API)   │     │
│  └────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────┐
│ Letta Cloud  │    │   Todoist    │
│ (memory)     │    │   (tasks)    │
└──────────────┘    └──────────────┘
```

## Interaction Modes

### Mode 1: Scheduled Nudges

Configurable nudges defined in YAML, not code:

```yaml
# config/nudges.yaml
nudges:
  - name: exercise
    schedule: "15:00"
    context_query: "@exercise OR #health"
    prompt_hint: "Focus on movement, energy, breaking from work"

  - name: asa
    schedule: "17:00"
    context_query: "@asa"
    prompt_hint: "Father-son connection, his current interests, school"

  - name: krissa
    schedule: "20:00"
    context_query: "@krissa"
    prompt_hint: "Partnership, shared planning, appreciation"
```

Example nudges:
- 3pm: "You haven't moved today. 30-min window before Asa's home - walk or bike?"
- 5pm: "You wanted to ask Asa about his Wolf badge. He mentioned struggling with the knots requirement."
- 8pm: "You've been meaning to discuss summer vacation plans. Also: she handled bedtime solo twice this week."

Each nudge:
1. Pulls relevant tasks from Todoist (by label/project)
2. Pulls conversation history from Letta
3. Synthesizes a context-aware prompt
4. Waits for reply, stores it in memory

### Mode 2: Task Capture (anytime)

User messages the bot: "I need to schedule Asa's dentist appointment soon"

Bot:
1. Parses intent (new task)
2. Infers context: Asa-related, probably `@asa` label, no hard due date
3. Confirms: "Got it - 'Schedule Asa dentist appointment' under Asa, no due date. Sound right?"
4. On confirmation, creates task in Todoist via MCP

Over time, learns filing patterns from conversation history.

## Memory Model

### Letta Memory Blocks (always in context)

```
Core Identity:
  owner: Luis
  bot_name: Rubber Duck
  focus_areas: [exercise, Asa, Krissa]

Patterns Observed:
  - "Often skips exercise when work runs late"
  - "Asa conversations go better after dinner"
  - "Krissa appreciates advance notice on plans"

Recent Context:
  - Last exercise: Tuesday (2 days ago)
  - Last Asa task completed: "Helped with math homework" (yesterday)
  - Open thread with Krissa: vacation planning
```

### Archival Memory (searchable, retrieved on demand)

- Full conversation history
- Task completions and context
- Patterns that aren't daily-relevant but might resurface

### Memory Flow

When generating a nudge:
1. Memory blocks provide patterns + recent context
2. Archival search retrieves relevant history
3. Todoist query gets matching tasks
4. LLM synthesizes with all context

When user replies:
1. Bot updates archival memory
2. If pattern emerges, may update memory blocks

## Code Structure

```
rubber-duck/
├── src/
│   ├── bot.py              # Discord client, message handlers
│   ├── scheduler.py        # Loads nudges from config, schedules generically
│   ├── agent.py            # Claude Agent SDK wrapper
│   ├── nudge.py            # Generic nudge generator (config-driven)
│   └── handlers/
│       ├── task_capture.py # "I need to do X" parsing
│       └── conversation.py # General replies, memory updates
├── config/
│   └── nudges.yaml         # Nudge definitions
├── pyproject.toml          # uv-managed dependencies
├── Dockerfile
└── fly.toml
```

### Key Dependencies

- `discord.py` - Discord bot framework
- `claude-agent-sdk` - Agent with MCP support
- `apscheduler` - Cron-like scheduling
- `letta-client` - Letta Cloud API

## MCP Integration

```yaml
mcp_servers:
  todoist:
    # Task queries: get tasks by filter (@asa, due:today, etc.)
    # Task creation: create task with project/labels/due date
    # Task completion: mark tasks done

  letta:
    # Memory read: get memory blocks, search archival
    # Memory write: update blocks, add to archival
    # (If Letta exposes MCP; otherwise direct API)
```

For scheduled nudges, the agent receives:
```
It's 5pm. Generate an Asa-focused nudge.
Context query: @asa
Hint: Father-son connection, his current interests, school

Use your tools to:
1. Check Letta memory for recent Asa-related context
2. Query Todoist for tasks matching @asa
3. Synthesize a nudge based on what you find
```

## Deployment

### Fly.io Configuration

```toml
# fly.toml
app = "rubber-duck"
primary_region = "sfo"

[env]
  TZ = "America/Los_Angeles"

[build]
  dockerfile = "Dockerfile"

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

### Secrets

Set via `fly secrets set`:
- `DISCORD_BOT_TOKEN`
- `ANTHROPIC_API_KEY`
- `TODOIST_API_KEY`
- `LETTA_API_KEY`

### Cost Estimate

- Fly.io: Free tier (one small VM)
- Letta Cloud: Free tier
- Claude API: ~$5-10/month with regular use

## MVP Scope

### What to build first

1. Discord bot that responds to DMs
2. Single nudge type working end-to-end
3. Letta memory: store/retrieve conversation context
4. Todoist integration: query tasks, create tasks
5. Config-driven nudge definitions
6. Deploy to Fly.io

### Explicitly deferred

- Claude.ai conversation integration (manual exports/cross-links for now)
- Self-modification (Strix-style)
- Morning brief / task synthesis
- Pattern learning (beyond Letta's automatic behavior)

## Setup Requirements

### API Keys Needed

| Service | Status | How to get |
|---------|--------|------------|
| Anthropic | Have | - |
| Todoist | Have | - |
| Discord | Need | discord.com/developers → New App → Bot → Token |
| Letta | Need | letta.com → Sign up → Dashboard → API key |

### Discord Bot Setup

1. Create application at discord.com/developers
2. Add Bot to the application
3. Copy bot token (secret)
4. Enable "Message Content Intent" in bot settings
5. Generate invite URL with permissions: Send Messages, Read Message History
6. Create private server, invite bot
