# Claude Code Refactor Design

**Date:** 2026-01-03
**Status:** Approved
**Bead:** rubber-duck-etf

## Motivation

Current API costs are $7-8/day (~$210-240/month) using direct Anthropic SDK calls. The owner already pays for Claude Max subscription, which includes Claude Code usage. Refactoring to use Claude Code eliminates these costs.

Secondary benefits:
- Access to Claude Code's native tools (file editing, bash, web search) without maintaining custom implementations
- Per-task session model with Letta providing persistent memory

## Architecture Overview

```
Discord Message
    ↓
bot.py (on_message)
    ↓
Load memory blocks from Letta
    ↓
claude -p "message" --output-format stream-json [--resume <session_id>]
    --append-system-prompt "memory blocks + tool instructions"
    --allowedTools "Bash,Read,Edit,Glob,Grep,Write,WebFetch,WebSearch"
    ↓
Parse NDJSON stream (tool calls → Discord status updates)
    ↓
Extract final result, session_id
    ↓
Store session_id for potential follow-up
    ↓
Return response to Discord
```

## Session Model

| Scenario | Approach |
|----------|----------|
| New topic / explicit task | Fresh session |
| Follow-up within ~5 min | `--resume <session_id>` |
| "What did you just do?" | `--resume <session_id>` |
| Scheduled nudge/check-in | Fresh session |

**Persistence:** Letta remains the long-term memory layer. Claude Code sessions are ephemeral executors. After each session, relevant learnings can be archived to Letta.

## Tool Architecture

### Native Claude Code Tools
Claude Code handles these directly:
- File operations (Read, Write, Edit, Glob, Grep)
- Git operations (via Bash)
- Shell commands (Bash)
- Web access (WebFetch, WebSearch)

### Custom Tools via Skills
Python tools exposed as Claude Code skills with CLI wrappers:

```
.claude/skills/
├── todoist/
│   ├── SKILL.md
│   └── scripts/
│       └── todoist.py      # CLI wrapper
├── gcal/
│   ├── SKILL.md
│   └── scripts/
│       └── gcal.py
└── memory/
    ├── SKILL.md
    └── scripts/
        └── memory.py       # Letta operations
```

Skills are loaded dynamically when Claude Code detects relevance, keeping context efficient.

## Headless Authentication

Claude Code stores OAuth tokens in `~/.claude/.credentials.json`:
```json
{"claudeAiOauth": {"accessToken": "...", "refreshToken": "..."}}
```

For headless deployment (Fly.io):
1. Authenticate on local machine with browser
2. Copy `.credentials.json` to persistent volume or Fly secrets
3. Mount to `~/.claude/.credentials.json` in container

Tokens auto-refresh, so this is a one-time setup.

## Implementation Components

### 1. Claude Code Executor (`src/rubber_duck/agent/claude_code.py`)
- Spawn `claude -p` subprocess with appropriate flags
- Stream and parse NDJSON output
- Extract tool calls for Discord status updates
- Return final result and session metadata

### 2. Session Manager (`src/rubber_duck/agent/sessions.py`)
- Track active session IDs per user/channel
- Decide fresh vs resume based on timing and context
- Store in `state/sessions.json`

### 3. Tool Skills (`.claude/skills/`)
- `todoist/` - Task management
- `gcal/` - Calendar queries
- `memory/` - Letta memory operations (get/set blocks, search, archive)

### 4. CLI Wrappers (`src/rubber_duck/cli/`)
- Thin CLI entrypoints for each tool
- Reuse existing integration code
- Output structured JSON for Claude Code to parse

### 5. Updated Message Handler
- Replace `run_agent_loop()` with Claude Code executor
- Maintain Discord status message updates from streamed tool calls
- Handle preemption/cancellation via process signals

## Context Injection

Each Claude Code session receives:

1. **System prompt addition** (`--append-system-prompt`):
   - Memory blocks from Letta (persona, patterns, guidelines, etc.)
   - Current date/time
   - Skill usage hints

2. **Conversation context** (via prompt or `--input-format stream-json`):
   - Recent journal entries (last 3-5 substantive turns)
   - Filtered to exclude perch ping noise

## Migration Path

1. **Phase 1:** Create skill infrastructure and CLI wrappers
2. **Phase 2:** Build Claude Code executor with NDJSON parsing
3. **Phase 3:** Update message handler to use executor
4. **Phase 4:** Remove old agent loop and direct SDK dependencies
5. **Phase 5:** Deploy and validate on Fly.io

## Open Issues

- **rubber-duck-0a1:** Journal search for Claude Code sessions (how to expose long-term journal to Claude Code)
- **rubber-duck-bs1:** Perch pings polluting journal (log less, add source field for future filtering)

## Deployment

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_CLAUDE_CODE` | Enable Claude Code mode (uses Max subscription) | `false` |
| `ANTHROPIC_API_KEY` | Required when `USE_CLAUDE_CODE=false` | - |

When `USE_CLAUDE_CODE=true`:
- Requires `claude` CLI to be installed and authenticated
- Uses `~/.claude/.credentials.json` for OAuth tokens
- API costs are covered by Max subscription

### Fly.io Deployment

To deploy with Claude Code mode on Fly.io:

1. **Create persistent volume for Claude credentials:**
   ```bash
   fly volumes create claude_data --size 1
   ```

2. **Add volume mount to `fly.toml`:**
   ```toml
   [mounts]
     source = "claude_data"
     destination = "/root/.claude"
   ```

3. **Copy credentials from local machine:**
   ```bash
   # First authenticate locally (requires browser)
   claude auth login

   # Then copy credentials to Fly volume
   fly ssh console -C "mkdir -p /root/.claude"
   fly sftp shell
   put ~/.claude/.credentials.json /root/.claude/.credentials.json
   ```

4. **Set environment variable:**
   ```bash
   fly secrets set USE_CLAUDE_CODE=true
   ```

5. **Install Claude CLI in container:**
   Add to Dockerfile:
   ```dockerfile
   RUN npm install -g @anthropic-ai/claude-code
   ```

### Token Refresh

OAuth tokens auto-refresh, so credential setup is one-time. If tokens expire (after extended downtime), re-authenticate locally and copy fresh credentials.

## Cost Impact

- **Before:** $7-8/day API costs (~$240/month)
- **After:** $0 additional (covered by Max subscription)
- **Savings:** ~$240/month
