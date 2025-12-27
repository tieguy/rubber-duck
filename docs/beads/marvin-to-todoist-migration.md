# Bead: Marvin to Todoist Migration

**Date:** 2025-12-27
**Status:** Open

## Context

Tasks currently live in Amazing Marvin, not Todoist. Need to either:
1. Migrate tasks to Todoist
2. Or integrate directly with Marvin API

## Existing Work

There's a `marvin-to-model` project at `/projects/self-serious/marvin-to-model` that exports Marvin tasks to JSONL for AI consumption. Could potentially adapt this.

## Options

| Approach | Pros | Cons |
|----------|------|------|
| Migrate to Todoist | Simpler integration (already done) | Manual migration effort |
| Add Marvin API integration | No migration needed | Another API to maintain |
| Use marvin-to-model export | Already exists | Read-only, no task creation |

## Tasks Needed in Todoist

- Projects: `#Asa`, `#Krissa` (at minimum)
- Labels: `@asa`, `@krissa`, `@family`

## Next Steps

- [ ] Decide: migrate to Todoist or add Marvin integration
- [ ] If migrating, set up projects/labels in Todoist
- [ ] Review marvin-to-model for reusable code
