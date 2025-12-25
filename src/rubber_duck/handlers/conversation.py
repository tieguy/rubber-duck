"""Conversation handler for Rubber Duck."""

import logging

import discord

from rubber_duck.agent import process_user_message

logger = logging.getLogger(__name__)


async def handle_message(bot, message: discord.Message) -> None:
    """Handle an incoming message from the owner.

    Args:
        bot: The Discord bot instance
        message: The Discord message to handle
    """
    content = message.content.strip()

    if not content:
        return

    logger.info(f"Handling message from owner: {content[:50]}...")

    try:
        # Show typing indicator while processing
        async with message.channel.typing():
            response = await process_user_message(content)

        await message.reply(response)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await message.reply("Sorry, something went wrong processing your message.")
