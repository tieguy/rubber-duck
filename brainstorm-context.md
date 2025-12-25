# Rubber Duck Project - Brainstorming Context

Saved: 2025-12-25

## Goal

Build a cron-triggered bot that maintains ambient awareness of ongoing projects and suggests next steps on a regular basis. Over time, it should grow interfaces to other systems (personal CRM, content archives). Interface must be mobile-accessible - NOT Discord. Options: Signal bot or web interface (e.g., Netlify PWA).

---

## Inspiration: Strix (from timkellogg.me/blog/2025/12/15/strix)

Strix is a Discord-based AI assistant built on Claude Code with persistent identity and memory. Key concepts:

**Three Trigger Types:**
1. Direct messages from user
2. Ambient "perch ticks" (2-hour intervals) for self-directed tasks
3. Cron-scheduled jobs for reminders and recurring chores

**Memory Stack:**
- Memory blocks (persistent identity: persona, patterns, focus, values)
- Journal logs (temporal awareness, commitments, agent intent)
- State files (working memory: inbox, today's tasks, commitments)
- Event logs (debugging and decision reasoning)

**Core Principle:** "If you didn't write it down, you won't remember it next message." Context rebuilds completely each invocation.

**Self-Modification:** Can modify its own code via git-based workflow (dev branch → pytest/pyright → PR for approval).

---

## Existing Projects to Integrate

### marvin-to-model (/projects/self-serious/marvin-to-model)

Python tool that exports tasks from Amazing Marvin to JSONL for AI consumption.

**Key features:**
- Dual-mode: personal and work contexts with different excluded categories
- Morning/end-of-day/weekly/monthly review cadences
- Uses Claude API for AI-powered GTD planning
- Exports: tasks_enhanced_for_daily.json, tasks_enhanced_for_weekly.json
- Project health tracking (WAITING/ACTIVE/INCOMPLETE/STALLED)

**Useful commands:**
```bash
./morning          # Morning planning
./end-of-day       # EOD review
./weekly           # Weekly GTD review
./monthly          # Monthly strategic review
```

**Data files:**
- data/{mode}/tasks_enhanced_for_daily.json - Tasks grouped by urgency
- data/{mode}/tasks_enhanced_for_weekly.json - Tasks grouped by category
- data/{mode}/projects_with_health.json - Project health status

### content-archive (/projects/self-serious/content-archive)

Python tooling to create searchable archive of ~20 years of personal writings.

**Current focus:** Importing talks (PDF/PPTX slides) to markdown with YAML frontmatter.

**Output format:**
```yaml
---
type: talk
title: "Talk Title"
date: 2019
event: "Conference Name"
event_type: conference
audience: engineers
format: slides
favorite: false  # for style analysis curation
---
```

**End goal:** Feed curated talks to LLM for style analysis to generate better first drafts.

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      RUBBER DUCK CORE                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  State Files (YAML/JSON)                            │    │
│  │  - identity.yaml (persona, patterns, focus)         │    │
│  │  - journal/ (daily logs, commitments, discoveries)  │    │
│  │  - state/ (inbox, active context, pending actions)  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Tick Handler (cron-triggered)                      │    │
│  │  - Load full state                                  │    │
│  │  - Query integrations for updates                   │    │
│  │  - LLM: "What's worth surfacing?"                   │    │
│  │  - Update state, emit notifications                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Integrations                                       │    │
│  │  - Marvin (via marvin-to-model export)              │    │
│  │  - Content Archive (reading YAML frontmatter)       │    │
│  │  - CRM (TBD)                                        │    │
│  │  - GitHub (activity, PR reviews, issues)            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
    ┌─────────────┐              ┌─────────────────┐
    │  Notifier   │              │  PWA Dashboard  │
    │  (ntfy.sh)  │              │  (Netlify)      │
    └─────────────┘              └─────────────────┘
```

---

## Interface Options

### Option A: Signal Bot
- Pros: True mobile push, E2E encrypted, conversational
- Cons: signal-cli is finicky, no rich formatting, unofficial

### Option B: PWA via Netlify
- Pros: Full UI control, rich formatting, push notifications
- Cons: Need to build UI, push less reliable than native

### Option C: Hybrid (Recommended)
- PWA for rich display
- ntfy.sh or Pushover for reliable mobile push notifications
- Links in notifications open to PWA for details

---

## Tick Cadences

| Cadence | Trigger | Purpose |
|---------|---------|---------|
| Morning (7am) | Cron | Context for today - tasks, calendar, overnight updates |
| Perch tick (2-3 hours) | Cron | Ambient scan - urgent items, stalled work |
| Evening (6pm) | Cron | Wrap-up - what got done, what slipped, journal prompt |
| Weekly (Sunday) | Cron | GTD review synthesis, pattern observations |
| On-demand | Webhook/PWA | User-triggered queries |

---

## State Schema (Draft)

```yaml
# state/identity.yaml
name: "Rubber Duck"
owner: "Luis"
focus_areas:
  - "Ship content-archive MVP"
  - "Maintain open source health"
  - "Relationship maintenance (CRM)"
patterns_observed:
  - "Often defer 'organize' tasks"
  - "Energy higher in morning for writing"
values:
  - "Proactive but not nagging"
  - "Surface connections across domains"

# state/current.yaml
last_tick: "2025-12-25T09:00:00Z"
active_context:
  - project: "content-archive"
    status: "MVP extraction working"
    next_action: "Run extraction on remaining 15 talks"
pending_nudges:
  - type: "stalled_project"
    project: "rubber-duck"
    days_stalled: 3
    suggested_action: "Define MVP scope"
```

---

## MVP Phases

**Phase 1: Proof of Concept**
1. Cron job (GitHub Actions or local) runs daily
2. Reads marvin-to-model export (tasks_enhanced_for_daily.json)
3. LLM generates "morning brief"
4. Sends to ntfy.sh (mobile notification)
5. State stored in git repo (simple YAML files)

**Phase 2: Add Depth**
- PWA dashboard showing history and context
- Content-archive integration
- Perch ticks (ambient 2-hour scans)
- Journal/log storage

**Phase 3: Interactivity**
- Reply to notifications triggers actions
- CRM integration
- Self-modification (agent can update its own patterns)

---

## Open Questions

1. **Notification mechanism**: Signal, ntfy.sh, Pushover, or something else?
2. **Hosting for cron**: GitHub Actions (free, 6-hour max), fly.io, or home server?
3. **State storage**: Git repo (simple, versioned) vs. SQLite/Postgres (queryable)?
4. **CRM format**: What system/format is personal CRM currently?
5. **First integration priority**: Marvin tasks, content-archive, or both?

---

## Immediate Next Steps

1. Set up basic Python project structure with uv
2. Create first cron tick that reads marvin-to-model data
3. Wire up ntfy.sh for mobile notifications
4. Define state schema in YAML
5. Build first "morning brief" LLM prompt
