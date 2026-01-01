# Rubber Duck

A Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

Inspired by [Strix](https://timkellogg.me/blog/2025/12/15/strix), Tim Kellogg's AI executive assistant architecture. Primarily developed with [Claude Code](https://claude.ai/code).

## How It Works

Rubber Duck is a personal assistant bot that runs in Discord DMs. It:

- **Captures tasks** from natural language ("remind me to call mom tomorrow")
- **Sends scheduled nudges** at configurable times (exercise reminders, family check-ins, etc.)
- **Remembers context** across conversations using a three-tier memory system
- **Applies GTD principles** to help you stay organized

### Integrations

| Service | Purpose | Status |
|---------|---------|--------|
| **Todoist** | Task management backend | ✅ Implemented |
| **Letta Cloud** | Persistent memory (blocks + archival) | ✅ Implemented |
| **Anthropic Claude** | LLM reasoning (Opus 4.5) | ✅ Implemented |
| **Google Calendar** | Calendar awareness | 🚧 Planned |

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Discord bot token
- API keys for Anthropic, Todoist, and Letta

### Installation

```bash
# Clone the repository
git clone https://github.com/tieguy/rubber-duck.git
cd rubber-duck

# Install dependencies
uv sync

# Copy and configure environment variables
cp .env.example .envrc
# Edit .envrc with your API keys

# Run the bot
uv run python -m rubber_duck
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Your Discord bot token |
| `DISCORD_OWNER_ID` | Yes | Your Discord user ID (bot only responds to you) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `TODOIST_API_KEY` | Yes | Todoist API token |
| `LETTA_API_KEY` | Yes | Letta Cloud API key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | Base64-encoded Google service account JSON (for future GCal support) |

### Nudge Configuration

Copy `config/nudges.yaml.example` to `state/nudges.yaml` and customize:

```yaml
nudges:
  - name: exercise
    schedule: "15:00"
    days: weekdays
    context_query: "@exercise | #health"
    prompt_hint: "Remind about physical activity."
```

## Architecture

Rubber Duck follows the Strix three-tier memory pattern:

1. **Core Identity (Tier 1)** - Letta memory blocks always loaded into context
2. **Long-Term Memory (Tier 2)** - Searchable archival memory in Letta
3. **Working Memory (Tier 3)** - Session journal and state files

The agent loop calls Anthropic directly while using Letta purely for memory storage (no LLM calls through Letta).

## Deployment

Designed for deployment on [Fly.io](https://fly.io) with persistent storage for state.

```bash
fly launch
fly secrets set DISCORD_BOT_TOKEN=... ANTHROPIC_API_KEY=... # etc
fly deploy
```

## License

[MPL-2.0](LICENSES/MPL-2.0.txt)
