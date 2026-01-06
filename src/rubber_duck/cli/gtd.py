# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""GTD CLI commands for skill consumption.

All commands output JSON for Claude Code skills to interpret.
"""

import json
import sys

import click


@click.group()
def gtd():
    """GTD workflow commands."""
    pass


@gtd.command("scan-deadlines")
def scan_deadlines_cmd():
    """Scan tasks for deadline urgency."""
    from rubber_duck.gtd.deadlines import scan_deadlines

    try:
        result = scan_deadlines()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-projects")
def check_projects_cmd():
    """Check project health status."""
    from rubber_duck.gtd.projects import check_projects

    try:
        result = check_projects()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-waiting")
def check_waiting_cmd():
    """Check waiting-for items and staleness."""
    from rubber_duck.gtd.waiting import check_waiting

    try:
        result = check_waiting()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-someday")
def check_someday_cmd():
    """Triage someday-maybe items by age."""
    from rubber_duck.gtd.someday import check_someday

    try:
        result = check_someday()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("calendar-today")
def calendar_today_cmd():
    """Get today's calendar events."""
    from rubber_duck.gtd.calendar import calendar_today

    try:
        result = calendar_today()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("calendar-range")
@click.option("--days-back", default=0, help="Days in the past to include")
@click.option("--days-forward", default=7, help="Days in the future to include")
def calendar_range_cmd(days_back: int, days_forward: int):
    """Get calendar events in a date range."""
    from rubber_duck.gtd.calendar import calendar_range

    try:
        result = calendar_range(days_back=days_back, days_forward=days_forward)
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


if __name__ == "__main__":
    gtd()
