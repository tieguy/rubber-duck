# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Nudge generation and delivery for Rubber Duck."""

import logging
import os

import discord

from rubber_duck.agent import generate_nudge_content

logger = logging.getLogger(__name__)


async def send_nudge(bot, nudge_config: dict) -> None:
    """Send a scheduled nudge to the owner.

    Args:
        bot: The Discord bot instance
        nudge_config: Configuration for this nudge containing:
            - name: Nudge identifier
            - context_query: Query for Todoist tasks
            - prompt_hint: Hint for the LLM about this nudge's focus
    """
    owner_id = bot.owner_id
    name = nudge_config.get("name", "unknown")

    logger.info(f"Sending nudge: {name}")

    try:
        # Get the owner's DM channel
        owner = await bot.fetch_user(owner_id)
        dm_channel = await owner.create_dm()

        # Generate nudge content using the agent
        content = await generate_nudge_content(nudge_config)

        # Send the nudge
        await dm_channel.send(content)
        logger.info(f"Nudge '{name}' sent successfully")

    except discord.errors.Forbidden:
        logger.error(f"Cannot send DM to owner {owner_id} - check permissions")
    except Exception as e:
        logger.exception(f"Error sending nudge '{name}': {e}")
