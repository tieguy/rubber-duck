# Project Metadata Design

Date: 2026-01-02

## Overview

Store per-project metadata (goals, context, due dates, links) that Todoist cannot hold natively. Distinguish between GTD projects (have end state) and categories (ongoing areas like "Family", "Health").

## Problem

Todoist treats projects and categories identically, but they need different handling:
- **Projects**: Have goals, due dates, end state. Weekly review tracks progress.
- **Categories**: Ongoing, no end state. Should not trigger "stalled" warnings.

The bot also needs project context when:
- Running weekly reviews (show goals alongside status)
- Creating tasks (suggest related actions based on project goal)
- Answering queries ("what's project X about?")

## File Structure

**File:** `state/projects-metadata.yaml`

```yaml
projects:
  "Kitchen Renovation":
    type: project
    goal: "Complete remodel with new cabinets and appliances"
    context: "Working with contractor Bob. Budget ~$30k."
    due: "2026-06-01"
    links:
      - "https://pinterest.com/kitchen-ideas"
      - "docs/contractor-quote.pdf"

  "Family":
    type: category
    context: "Ongoing family relationships, traditions, quality time"

  "Learn Rust":
    type: project
    goal: "Build one production tool in Rust"
    context: "For systems programming skills"
```

## Schema

| Field | Required | Applies To | Description |
|-------|----------|------------|-------------|
| `type` | Yes | All | `project` or `category` |
| `goal` | No | Projects | Definition of done |
| `context` | No | All | Background, constraints, stakeholders |
| `due` | No | Projects | ISO date or month (e.g., "2026-06-01") |
| `links` | No | All | List of URLs or file paths |

**Key for lookup:** Exact Todoist project name (case-sensitive).

No Todoist ID stored - name matching is sufficient. Can add ID later if needed.

## Implementation

### New File

**`src/rubber_duck/integrations/project_metadata.py`**

```python
def load_project_metadata() -> dict:
    """Load state/projects-metadata.yaml, return dict keyed by project name."""

def get_project_meta(project_name: str) -> dict | None:
    """Get metadata for a specific project, or None if not found."""

def save_project_metadata(metadata: dict) -> None:
    """Write metadata dict back to YAML file."""
```

### New Tool

**`set_project_metadata`**

```python
def set_project_metadata(
    project_name: str,
    type: str,  # "project" | "category"
    goal: str | None = None,
    context: str | None = None,
    due: str | None = None,
    links: list[str] | None = None,
) -> str:
    """Create or update metadata for a project/category."""
```

Behavior:
- If entry exists: merge updates (don't overwrite unspecified fields)
- If new: create entry
- Returns confirmation message

## Integration Points

### Reading Metadata

1. **Weekly review tools** (`project_review.py`, `category_health.py`)
   - Enrich output with goals/due dates
   - Exclude categories from STALLED/INCOMPLETE warnings

2. **Morning planning**
   - Show goal/due for projects with tasks due today
   - "Kitchen Renovation (due Jun 1): 3 tasks"

3. **Task creation**
   - Load project context when adding tasks
   - Suggest due dates based on project deadline

4. **On-demand queries**
   - "What's project X about?" → return goal/context/links

### Writing Metadata

1. **Prompted discovery**
   - When encountering project without metadata: "I don't have context for 'New Project' - any details you'd like to add?"
   - Assume project (not category) by default
   - User can say "no, I'll add later" or provide goal/context

2. **Conversational updates**
   - "The goal for Kitchen Renovation changed to..."
   - Bot calls `set_project_metadata()` to update

3. **New project creation**
   - When bot creates a Todoist project, prompt for metadata

## Output Changes

### Project Review (Before)

```
### STALLED (has next actions, no progress)
- **Kitchen Renovation**: 5 tasks -> Install cabinet hardware
```

### Project Review (After)

```
### STALLED (has next actions, no progress)
- **Kitchen Renovation** (due Jun 1): 5 tasks -> Install cabinet hardware
  Goal: Complete remodel with new cabinets and appliances
```

Categories filtered out of STALLED/INCOMPLETE sections entirely.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| File missing | Create empty `projects: {}` on first write |
| Malformed YAML | Log error, continue without metadata (degraded but functional) |
| Orphaned entry (Todoist project renamed) | Flag during weekly review (low priority) |

## Files Changed

- **New:** `src/rubber_duck/integrations/project_metadata.py`
- **New:** `state/projects-metadata.yaml` (created on first write)
- **Modify:** `src/rubber_duck/agent/tools.py` (add `set_project_metadata` tool)
- **Modify:** `src/rubber_duck/integrations/tools/project_review.py` (enrich output)
- **Modify:** `src/rubber_duck/integrations/tools/category_health.py` (use type field)
- **Modify:** `src/rubber_duck/integrations/tools/morning_planning.py` (show goals)

## Out of Scope

- Syncing Todoist project IDs (YAGNI - add if name matching breaks)
- Automatic category detection (user corrects during weekly review if needed)
- Migration tooling (start fresh, populate as projects come up)
