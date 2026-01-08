# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Perch ticks for proactive maintenance work."""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from anthropic import AsyncAnthropic

from rubber_duck.agent.tools import archive_to_memory
from rubber_duck.preemption import finish_work, should_yield, start_work

logger = logging.getLogger(__name__)

# Constants (future: move to config)
GAP_MINUTES = 30  # Min gap to consider conversation "ended"
NOTIFY_ON_ACTION = True  # Send debug DM only when action is taken
NOTIFY_ALL_TICKS = False  # Send debug DM on every tick (noisy, for debugging only)

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent
JOURNAL_PATH = REPO_ROOT / "state" / "journal.jsonl"
PERCH_STATE_PATH = REPO_ROOT / "state" / "perch_state.json"

# Model for summarization (use Haiku for cost efficiency)
MODEL_HAIKU = "claude-3-5-haiku-20241022"

SUMMARY_PROMPT = """Summarize this conversation. Focus on:
- Decisions made
- Preferences expressed
- Work completed
- Context that would be useful later

If the conversation was trivial (greetings, confirmations, no meaningful content), respond with just: SKIP

Conversation:
{entries}"""


def _load_perch_state() -> dict:
    """Load perch state from file."""
    if PERCH_STATE_PATH.exists():
        try:
            with open(PERCH_STATE_PATH) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_perch_state(state: dict) -> None:
    """Save perch state to file."""
    PERCH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PERCH_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _get_journal_entries_since(since_ts: str | None) -> list[dict]:
    """Get user/assistant message entries from journal since timestamp."""
    if not JOURNAL_PATH.exists():
        return []

    entries = []
    since_dt = datetime.fromisoformat(since_ts) if since_ts else None

    try:
        with open(JOURNAL_PATH) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_type = entry.get("type")

                    # Only include user/assistant messages
                    if entry_type not in ("user_message", "assistant_message"):
                        continue

                    # Filter by timestamp if provided
                    if since_dt:
                        entry_ts = datetime.fromisoformat(entry["ts"])
                        if entry_ts <= since_dt:
                            continue

                    entries.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError as e:
        logger.warning(f"Could not read journal: {e}")

    return entries


def _get_last_activity_ts() -> datetime | None:
    """Get timestamp of most recent journal entry."""
    if not JOURNAL_PATH.exists():
        return None

    last_ts = None
    try:
        with open(JOURNAL_PATH) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    last_ts = entry.get("ts")
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return datetime.fromisoformat(last_ts) if last_ts else None


def _format_entries_for_summary(entries: list[dict]) -> str:
    """Format journal entries for the summary prompt."""
    lines = []
    for entry in entries:
        role = "User" if entry["type"] == "user_message" else "Assistant"
        content = entry.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


async def _summarize_and_evaluate(entries: list[dict]) -> str | None:
    """Summarize entries and return summary, or None if trivial.

    Returns:
        Summary string to archive, or None if conversation was trivial.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping summarization")
        return None

    formatted = _format_entries_for_summary(entries)
    prompt = SUMMARY_PROMPT.format(entries=formatted)

    try:
        client = AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text.strip()

        if result.upper().startswith("SKIP"):
            return None

        return result

    except Exception as e:
        logger.exception(f"Error summarizing conversation: {e}")
        return None


async def _send_debug_dm(bot, message: str, *, is_action: bool = False) -> None:
    """Send debug DM to owner.

    Args:
        bot: Discord bot instance
        message: Message to send
        is_action: True if this tick performed an action (not just a status check)
    """
    # Only notify if: action taken and NOTIFY_ON_ACTION, or NOTIFY_ALL_TICKS
    if not (is_action and NOTIFY_ON_ACTION) and not NOTIFY_ALL_TICKS:
        return

    try:
        owner = await bot.fetch_user(bot.owner_id)
        await owner.send(message)
    except Exception as e:
        logger.warning(f"Could not send perch debug DM: {e}")


async def perch_tick(bot) -> None:
    """Run a perch tick - check for maintenance work.

    Currently only does conversation archiving.
    """
    now = datetime.now(UTC)
    state = _load_perch_state()

    # Check last activity
    last_activity = _get_last_activity_ts()

    if not last_activity:
        await _send_debug_dm(bot, "🪺 Perch tick\n• No journal activity found")
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Calculate gap
    gap = now - last_activity
    gap_minutes = gap.total_seconds() / 60

    if gap_minutes < GAP_MINUTES:
        await _send_debug_dm(
            bot,
            f"🪺 Perch tick\n"
            f"• Last activity: {int(gap_minutes)} min ago\n"
            f"• Action: Skipped - conversation may be active"
        )
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Get entries since last archive
    last_archive_ts = state.get("last_archive_ts")
    entries = _get_journal_entries_since(last_archive_ts)

    if not entries:
        await _send_debug_dm(
            bot,
            f"🪺 Perch tick\n"
            f"• Last activity: {int(gap_minutes)} min ago\n"
            f"• Action: Skipped - no new entries since last archive"
        )
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Start autonomous work
    start_work("archiving conversation")
    try:
        # Check for preemption before doing work
        if should_yield():
            await _send_debug_dm(bot, "🪺 Perch tick\n• Preempted before archiving")
            return

        # Summarize and evaluate
        summary = await _summarize_and_evaluate(entries)

        # Check again after async work
        if should_yield():
            await _send_debug_dm(bot, "🪺 Perch tick\n• Preempted after summarization")
            return

        if summary is None:
            # No action taken - only log, don't notify
            logger.debug(
                f"Perch tick: skipped trivial conversation "
                f"({len(entries)} entries, {int(gap_minutes)} min ago)"
            )
        else:
            # Archive the summary - this is an action
            result = archive_to_memory(summary)
            logger.info(f"Archived conversation summary: {result}")

            await _send_debug_dm(
                bot,
                f"🪺 Perch tick\n"
                f"• Last activity: {int(gap_minutes)} min ago\n"
                f"• Entries since last archive: {len(entries)}\n"
                f"• Action: Archived conversation summary",
                is_action=True,
            )

        # Update state
        state["last_archive_ts"] = now.isoformat()
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)

    finally:
        finish_work()
