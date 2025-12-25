# Rubber Duck

A Discord bot that nudges you at configurable times with context-aware prompts, accepts task capture anytime, and remembers everything via conversational memory.

## Setup

```bash
uv sync
uv run python -m rubber_duck
```

## Configuration

Set environment variables:
- `DISCORD_BOT_TOKEN`
- `ANTHROPIC_API_KEY`
- `TODOIST_API_KEY`
- `LETTA_API_KEY`

Edit `config/nudges.yaml` to configure scheduled nudges.
