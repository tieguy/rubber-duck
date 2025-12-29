# Google Calendar Setup (Service Account)

This guide explains how to set up Google Calendar integration for Rubber Duck using a service account.

## Overview

Service account auth allows the bot to read your calendar without interactive login. You share your calendar with the service account's email, and it can then query events.

## Setup Steps

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Note your project ID

### 2. Enable the Calendar API

1. Go to **APIs & Services > Library**
2. Search for "Google Calendar API"
3. Click **Enable**

### 3. Create a Service Account

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > Service Account**
3. Name it something like `rubber-duck-calendar`
4. Click **Create and Continue**
5. Skip the optional steps, click **Done**

### 4. Download the JSON Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key > Create new key**
4. Choose **JSON** format
5. Save the downloaded file securely

### 5. Share Your Calendar with the Service Account

1. Open [Google Calendar](https://calendar.google.com/)
2. Find your calendar in the left sidebar
3. Click the three dots > **Settings and sharing**
4. Under "Share with specific people", click **Add people**
5. Enter the service account email (looks like `name@project-id.iam.gserviceaccount.com`)
6. Set permission to **See all event details**
7. Click **Send**

### 6. Configure Rubber Duck

Base64-encode your JSON key file:

```bash
base64 -w0 path/to/your-service-account-key.json
```

Set the environment variable:

**Local development (.envrc):**
```bash
export GOOGLE_SERVICE_ACCOUNT_JSON="<paste-base64-encoded-key>"
```

**Fly.io deployment:**
```bash
fly secrets set GOOGLE_SERVICE_ACCOUNT_JSON="$(base64 -w0 path/to/key.json)"
```

### 7. Restart the Bot

The bot will automatically detect the credentials on next startup and enable calendar features in:
- Morning planning (shows today's calendar)
- End-of-day review (shows tonight + tomorrow)
- Direct queries via `query_gcal` tool

## Troubleshooting

### "Google Calendar is not configured"
- Verify `GOOGLE_SERVICE_ACCOUNT_JSON` is set
- Check that the value is properly base64-encoded

### No events showing up
- Confirm you shared your calendar with the service account email
- Check that the service account has "See all event details" permission
- Verify the calendar ID (defaults to "primary")

### Authentication errors
- Ensure the Calendar API is enabled in your GCP project
- Verify the JSON key hasn't been revoked

## Security Notes

- The JSON key grants read-only access to shared calendars
- Never commit the key file or base64 value to git
- Rotate keys periodically via the GCP console
- The service account can only see calendars explicitly shared with it
