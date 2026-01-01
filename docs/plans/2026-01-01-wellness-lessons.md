# Wellness-Focused Agent Lessons

Date: 2026-01-01
Source: https://gist.github.com/tkellogg/55a66bb237fd01c82f6ff2891e199595

## Overview

Lessons from the Strix wellness game plan that apply to Rubber Duck's design and operation.

## Core Principles

### 1. Autonomy-Supportive Language

**Problem:** Directive language ("you should", "you must") triggers resistance and shame.

**Solution:** Use autonomy-supportive framing:
- "You could..." instead of "You should..."
- "Would you like to..." instead of "It's time to..."
- "One option is..." instead of "You need to..."

**Where to apply:**
- `prompt_hint` in nudges.yaml
- System prompt `communication` block
- Generated nudge messages

### 2. ADHD-Aware Design

**Key accommodations:**
- **Time blindness:** Surface deadlines proactively; don't assume awareness
- **Emotional overload signals:** Recognize when user is overwhelmed and reduce demands
- **Working memory limits:** Keep messages short, one key point at a time
- **Task initiation difficulty:** Lower the activation energy for starting tasks

**Where to apply:**
- Morning planning tool: show deadlines with "days until" not just dates
- Nudge generation: detect overload (many overdue tasks) and adjust tone
- System prompt: add pattern recognition for overwhelm signals

### 3. Human Connection Priority

**Problem:** AI assistants can become substitutes for human relationships.

**Solution:** The bot should actively facilitate human connection:
- Nudge about family/partner time (already in nudges.yaml.example)
- Track relationship cadence (last time you called mom, etc.)
- Never position itself as emotional support substitute
- When user vents, suggest talking to a human

**Where to apply:**
- Add `relationship_cadence` memory block pattern
- Scheduled nudges for connection (exercise, family, partner nudges exist)
- System prompt guideline: facilitate human support, don't replace it

### 4. Shame Reduction

**Problem:** Missed tasks accumulate shame, creating avoidance loops.

**Solution:**
- Neutral framing for slipped tasks: "This moved to today" not "You missed..."
- No guilt-inducing language in nudges
- Celebrate completions without implying prior failure
- Avoid counting streaks (breaks become failures)

**Where to apply:**
- Morning planning output format
- Overdue task messaging in nudges
- System prompt `communication` block

### 5. Crisis Protocol

**Problem:** In emotional crisis, AI advice can be harmful.

**Solution:**
- Recognize crisis signals (suicidal ideation, severe distress, relationship crisis)
- DO NOT offer AI solutions to crisis
- Redirect to human support: friends, family, professionals
- Have resources ready (therapist contact, crisis lines if configured)

**Where to apply:**
- Add crisis detection to system prompt
- Create `support_resources` memory block for owner's support network
- Train to redirect, not counsel

## Implementation Plan

### Phase 1: Prompt Changes (Quick Wins)

1. **Update `communication` memory block:**
   ```
   Use autonomy-supportive language: "you could" not "you should".
   Be neutral about slipped tasks—no shame, no guilt.
   Keep messages brief—one actionable point.
   Recognize overwhelm: fewer demands, simpler options.
   ```

2. **Update nudge `prompt_hint` examples:**
   - Change "Remind about" → "Gently surface"
   - Add "No shame if skipped"

3. **Add crisis protocol to `guidelines` block:**
   ```
   If user expresses crisis (severe distress, suicidal thoughts, relationship crisis):
   - Do NOT offer advice or solutions
   - Acknowledge their feelings briefly
   - Suggest reaching out to a human (friend, family, therapist)
   - Offer to look up support_resources if configured
   ```

### Phase 2: Memory Block Additions

1. **`support_resources` block:**
   - Therapist contact
   - Close friends list
   - Family members for support
   - Crisis lines (optional)

2. **Extend `patterns` block to track:**
   - Overwhelm signals (many overdue, short responses, late night activity)
   - Relationship cadence (last contact with key people)

### Phase 3: Behavioral Changes

1. **Overdue handling in morning planning:**
   - Show count without judgment
   - Offer "quick triage" not "you're behind"
   - Suggest realistic daily max (3 priorities)

2. **Nudge tone adaptation:**
   - Detect high-stress periods
   - Reduce nudge frequency or make optional
   - "Would you like a nudge break?"

### Phase 4: Relationship Facilitation

1. **Track relationship cadence:**
   - Optional logging of human connection moments
   - Gentle nudges if someone important hasn't been contacted

2. **Connection > productivity nudges:**
   - End-of-day nudge should prioritize partner/family over task review
   - Weekly review: relationships before projects

## Anti-Patterns to Avoid

- ❌ Constant AI-nature disclaimers ("As an AI, I can't...")
- ❌ Counting streaks or building gamification
- ❌ "Catching up" language implying user is behind
- ❌ Offering to be emotional support
- ❌ Giving advice in crisis situations
- ❌ Productivity guilt ("You only completed 2 of 5 tasks")

## Alignment with Existing Architecture

Rubber Duck already has:
- ✅ Memory blocks for `persona`, `patterns`, `communication` (extensible)
- ✅ Nudge system with `prompt_hint` (updatable)
- ✅ Family/partner nudges in example config
- ✅ Morning planning with TOP 3 priorities (not overwhelming)
- ✅ GTD principles that align (capture, not shame)

Needs:
- [ ] Autonomy-supportive language in memory blocks
- [ ] Crisis protocol in guidelines
- [ ] Support resources block
- [ ] Shame-free overdue handling
- [ ] Overwhelm detection pattern

## References

- Original Strix wellness game plan: https://gist.github.com/tkellogg/55a66bb237fd01c82f6ff2891e199595
- Strix architecture: https://timkellogg.me/blog/2025/12/30/strix-memory
- Self-Determination Theory (autonomy, competence, relatedness)
