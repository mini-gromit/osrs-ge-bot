import re
import discord
from discord.ext import commands


class FlexibleChannelConverter(commands.Converter):
    """
    Flexible channel converter that handles multiple input formats.

    Resolution order (first match wins):
      1. Proper mention <#123456789> - Discord inserts this when you click
      2. Raw numeric ID 123456789
      3. Case-insensitive name match with or without a leading #
    """

    async def convert(self, ctx, argument: str) -> discord.TextChannel:
        if not ctx.guild:
            raise commands.ChannelNotFound(argument)

        mention_match = re.fullmatch(r'<#(\d+)>', argument.strip())
        if mention_match:
            channel = ctx.guild.get_channel(int(mention_match.group(1)))
            if isinstance(channel, discord.TextChannel):
                return channel

        if argument.strip().isdigit():
            channel = ctx.guild.get_channel(int(argument.strip()))
            if isinstance(channel, discord.TextChannel):
                return channel

        name = argument.lstrip('#').strip().lower()
        for channel in ctx.guild.text_channels:
            if channel.name.lower() == name:
                return channel

        raise commands.ChannelNotFound(argument)
