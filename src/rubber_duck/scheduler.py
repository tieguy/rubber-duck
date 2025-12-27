"""Scheduler for Rubber Duck nudges."""

import logging
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from rubber_duck.nudge import send_nudge

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "nudges.yaml"

# Day name to cron day-of-week mapping (0=Mon, 6=Sun in APScheduler)
DAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def parse_days(days_config) -> str | None:
    """Parse days configuration into cron day_of_week string.

    Supports:
    - None or "daily" -> None (every day)
    - "weekdays" -> "mon-fri"
    - "weekends" -> "sat,sun"
    - ["mon", "wed", "fri"] -> "mon,wed,fri"
    - "mon,wed,fri" -> "mon,wed,fri"

    Returns:
        Cron day_of_week string, or None for daily
    """
    if days_config is None or days_config == "daily":
        return None

    if isinstance(days_config, str):
        days_config = days_config.lower().strip()
        if days_config == "weekdays":
            return "mon-fri"
        elif days_config == "weekends":
            return "sat,sun"
        elif days_config == "daily":
            return None
        else:
            # Assume it's a comma-separated list like "mon,wed,fri"
            return days_config

    if isinstance(days_config, list):
        # Convert list of day names to comma-separated string
        day_names = [d.lower().strip() for d in days_config]
        return ",".join(day_names)

    return None


def load_nudge_config(config_path: Path | None = None) -> dict:
    """Load nudge configuration from YAML file."""
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.warning(f"No nudge config found at {path}, using empty config")
        return {"nudges": []}

    with open(path) as f:
        config = yaml.safe_load(f)

    return config or {"nudges": []}


async def setup_scheduler(bot) -> AsyncIOScheduler:
    """Set up the APScheduler with nudges from config."""
    scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")

    config = load_nudge_config()
    nudges = config.get("nudges", [])

    for nudge in nudges:
        name = nudge.get("name")
        schedule = nudge.get("schedule")  # Format: "HH:MM"
        days = nudge.get("days")  # Optional: "weekdays", "weekends", ["mon", "wed", "fri"], etc.

        if not name or not schedule:
            logger.warning(f"Skipping invalid nudge config: {nudge}")
            continue

        hour, minute = schedule.split(":")
        day_of_week = parse_days(days)

        trigger = CronTrigger(
            hour=int(hour),
            minute=int(minute),
            day_of_week=day_of_week,
        )

        scheduler.add_job(
            send_nudge,
            trigger=trigger,
            args=[bot, nudge],
            id=f"nudge_{name}",
            name=f"Nudge: {name}",
            replace_existing=True,
        )
        days_str = day_of_week or "daily"
        logger.info(f"Scheduled nudge '{name}' at {schedule} ({days_str})")

    scheduler.start()
    logger.info(f"Scheduler started with {len(nudges)} nudges")

    return scheduler
