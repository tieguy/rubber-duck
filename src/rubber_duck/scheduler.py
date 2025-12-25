"""Scheduler for Rubber Duck nudges."""

import logging
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from rubber_duck.nudge import send_nudge

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "nudges.yaml"


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

        if not name or not schedule:
            logger.warning(f"Skipping invalid nudge config: {nudge}")
            continue

        hour, minute = schedule.split(":")
        trigger = CronTrigger(hour=int(hour), minute=int(minute))

        scheduler.add_job(
            send_nudge,
            trigger=trigger,
            args=[bot, nudge],
            id=f"nudge_{name}",
            name=f"Nudge: {name}",
            replace_existing=True,
        )
        logger.info(f"Scheduled nudge '{name}' at {schedule}")

    scheduler.start()
    logger.info(f"Scheduler started with {len(nudges)} nudges")

    return scheduler
