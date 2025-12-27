# Bead: Calendar Integration for Nudges

**Date:** 2025-12-27
**Status:** Open

## Problem

Nudges should be able to draw context from calendar, not just Todoist tasks. Some relevant context (meetings, events, time blocks) lives in Google Calendar.

## Questions to Research

1. **Todoist + GCal sync**: Todoist can display GCal events, but does the Todoist API expose that synced calendar data? (Likely no - probably display-only in the app)

2. **Direct GCal integration**: May need to add Google Calendar API as a separate integration, similar to Todoist.

3. **What calendar data is useful for nudges?**
   - Upcoming events (next 2 hours?)
   - Free time blocks
   - Event context (who's the meeting with?)

## Python Libraries

| Library | Notes |
|---------|-------|
| [gcsa](https://pypi.org/project/gcsa/) | Pythonic wrapper, simplest API. `pip install gcsa` |
| [gcal-sync](https://pypi.org/project/gcal-sync/) | Async native, lightweight. Good fit for async bot |
| [google-api-python-client](https://developers.google.com/workspace/calendar/api/quickstart/python) | Official, more verbose but full control |

## Authentication Options

**OAuth 2.0 (user flow)**
- User clicks "Sign in with Google", grants permission in browser
- App gets a token that expires, need to handle refresh
- Good for: apps where many users log in

**Service Account (recommended for personal bot)**
- A "robot" Google account (not a person)
- Download JSON key file once, no browser needed
- No expiring tokens, no refresh logic
- Setup:
  1. Create service account in GCP console
  2. Download JSON credentials
  3. Share your calendar with the service account's email (e.g., `rubber-duck@your-project.iam.gserviceaccount.com`)
  4. Bot reads calendar using that key
- Downside: only works for calendars explicitly shared with it

## Options

| Approach | Pros | Cons |
|----------|------|------|
| Todoist API only | Simple, already done | No calendar data |
| Add GCal API (service account) | Simple auth, no OAuth popups | Must share calendar with service account |
| Add GCal API (OAuth) | Full access to user's calendars | Token refresh complexity |
| GCal MCP server | Reusable, standard | Need to find/build one |
| ICS feed polling | No auth needed if public | Stale data, limited info |

## Next Steps

- [ ] Decide: service account vs OAuth
- [ ] Create GCP project and enable Calendar API
- [ ] Add gcal-sync or gcsa to integrations

## References

- Todoist API: https://developer.todoist.com/rest/v2
- Google Calendar API: https://developers.google.com/calendar
- gcsa docs: https://google-calendar-simple-api.readthedocs.io/
- gcal-sync: https://pypi.org/project/gcal-sync/
