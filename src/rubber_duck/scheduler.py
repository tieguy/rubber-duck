# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Scheduler for Rubber Duck nudges."""

import logging
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from rubber_duck.nudge import send_nudge
from rubber_duck.perch import perch_tick

logger = logging.getLogger(__name__)

# Config paths in priority order:
# 1. NUDGE_CONFIG_PATH env var (override)
# 2. state/nudges.yaml (private, gitignored, persistent on Fly.io)
# 3. config/nudges.yaml (fallback/example)
REPO_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATHS = [
    REPO_ROOT / "state" / "nudges.yaml",
    REPO_ROOT / "config" / "nudges.yaml",
]

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
    """Load nudge configuration from YAML file.

    Checks paths in priority order:
    1. Explicit config_path argument
    2. NUDGE_CONFIG_PATH environment variable
    3. state/nudges.yaml (private, gitignored)
    4. config/nudges.yaml (public template/fallback)
    """
    import os

    # Priority 1: explicit argument
    if config_path and config_path.exists():
        path = config_path
    # Priority 2: environment variable
    elif env_path := os.environ.get("NUDGE_CONFIG_PATH"):
        path = Path(env_path)
        if not path.exists():
            logger.warning(f"NUDGE_CONFIG_PATH set but file not found: {path}")
            return {"nudges": []}
    # Priority 3-4: check config paths in order
    else:
        path = None
        for candidate in CONFIG_PATHS:
            if candidate.exists():
                path = candidate
                break

        if not path:
            logger.warning("No nudge config found, using empty config")
            return {"nudges": []}

    logger.info(f"Loading nudge config from: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)

    return config or {"nudges": []}


def setup_scheduler(bot) -> AsyncIOScheduler:
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

    # Add perch tick for background maintenance (every hour)
    scheduler.add_job(
        perch_tick,
        trigger=IntervalTrigger(hours=1),
        args=[bot],
        id="perch_tick",
        name="Perch tick",
        replace_existing=True,
    )
    logger.info("Scheduled perch tick (hourly)")

    scheduler.start()
    logger.info(f"Scheduler started with {len(nudges)} nudges + perch tick")

    return scheduler
