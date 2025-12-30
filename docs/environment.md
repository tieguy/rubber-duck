# Environment Variables

Required and optional environment variables for Rubber Duck.

## Required

### ANTHROPIC_API_KEY
API key for Claude. Get one from https://console.anthropic.com/

### LETTA_API_KEY
API key for Letta Cloud (persistent memory). Get one from https://www.letta.com/

### DISCORD_BOT_TOKEN
Discord bot token. Create a bot at https://discord.com/developers/applications

### DISCORD_OWNER_ID
Your Discord user ID. Enable Developer Mode in Discord settings, then right-click your name and "Copy ID".

## Optional

### TODOIST_API_KEY
API key for Todoist integration. Get from https://todoist.com/prefs/integrations

### GOOGLE_SERVICE_ACCOUNT_JSON
Base64-encoded Google service account JSON for Calendar access.

To create:
1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Base64 encode it: `base64 -w0 service-account.json`
4. Set the result as this environment variable

## Fly.io Deployment

Set secrets with:
```bash
fly secrets set ANTHROPIC_API_KEY=sk-ant-... --app rubber-duck
fly secrets set LETTA_API_KEY=... --app rubber-duck
fly secrets set DISCORD_BOT_TOKEN=... --app rubber-duck
fly secrets set DISCORD_OWNER_ID=... --app rubber-duck
fly secrets set TODOIST_API_KEY=... --app rubber-duck
fly secrets set GOOGLE_SERVICE_ACCOUNT_JSON=... --app rubber-duck
```
