import discord
from discord.ext import commands
from typing import Optional

from bot.converters import FlexibleChannelConverter
from bot.config import ChannelConfig


class SetupCog(commands.Cog, name="Setup"):
    """Commands for configuring the bot"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setup')
    async def setup_channels(
        self,
        ctx,
        super_hot_channel: FlexibleChannelConverter,
        hot_channel: FlexibleChannelConverter,
        welcome_channel: Optional[FlexibleChannelConverter] = None,
        all_alchs_channel: Optional[FlexibleChannelConverter] = None,
        f2p_alchs_channel: Optional[FlexibleChannelConverter] = None,
    ):
        """
        Configure which channels the bot posts to.

        Usage: !setup <super_hot> <hot_items> [welcome] [all_alchs] [f2p_alchs]
        """
        self.bot.channel_config = ChannelConfig(
            super_hot_items=super_hot_channel.id,
            hot_items=hot_channel.id,
            welcome_channel=welcome_channel.id if welcome_channel else None,
            all_alchs=all_alchs_channel.id if all_alchs_channel else None,
            f2p_alchs=f2p_alchs_channel.id if f2p_alchs_channel else None,
        )

        await self.bot.config_manager.save_config(self.bot.channel_config)

        lines = [
            "✅ Channels configured.",
            f"🔥 Super Hot → {super_hot_channel.mention}",
            f"🌟 Hot Items  → {hot_channel.mention}",
        ]
        if welcome_channel:
            lines.append(f"👋 Welcome    → {welcome_channel.mention}")
        if all_alchs_channel:
            lines.append(f"🧪 All Alchs  → {all_alchs_channel.mention}")
        if f2p_alchs_channel:
            lines.append(f"🆓 F2P Alchs  → {f2p_alchs_channel.mention}")

        await ctx.send("\n".join(lines))
        await self.bot.start_monitoring()

    @commands.command(name='setup_help')
    async def setup_help(self, ctx):
        """Show detailed setup instructions"""
        embed = discord.Embed(
            title="!setup usage",
            color=discord.Color.blue(),
            description=(
                "Configure which channels the bot posts to.\n"
                "All channels after the first two are optional.\n\n"
                "**Accepted formats for each channel:**\n"
                "• Click the channel name so Discord auto-inserts a mention\n"
                "• Type the name with or without `#`  e.g. `super-hot`\n"
                "• Paste the raw channel ID  e.g. `1234567890`\n\n"
                "**Examples:**\n"
                "`!setup #super-hot #hot-items`\n"
                "`!setup #super-hot #hot-items #welcome`\n"
                "`!setup #super-hot #hot-items #welcome #all-alchs #f2p-alchs`"
            )
        )
        await ctx.send(embed=embed)

    @commands.command(name='create_optin')
    async def create_optin(self, ctx):
        """Create the opt-in message for notifications"""
        if not self.bot.channel_config:
            await ctx.send("❌ Run !setup first.")
            return

        channel = self.bot.get_channel(self.bot.channel_config.welcome_channel)

        if not channel:
            await ctx.send("❌ Welcome channel not set or not found.")
            return

        embed = discord.Embed(
            title="🔔 Notification Subscriptions",
            description=(
                "React below to subscribe to DM alerts.\n\n"
                "🔥 **Super Hot** — profit >1,000gp\n"
                "🌟 **Hot Items** — profit 450–999gp\n"
                "🧪 **All Alchs** — any profitable alch\n"
                "🆓 **F2P Alchs** — F2P profitable alchs only\n"
                "🔕 **Unsubscribe** — remove all alerts"
            ),
            color=discord.Color.gold()
        )

        msg = await channel.send(embed=embed)

        for emoji in self.bot.REACTION_MAP.keys():
            await msg.add_reaction(emoji)

        self.bot.opt_in_message_id = msg.id
        await self.bot.save_channel_config()

        await ctx.send("✅ Opt-in message created.")

    @commands.command(name='status')
    async def status_cmd(self, ctx):
        """Show bot status and configuration"""
        if not self.bot.channel_config:
            await ctx.send("❌ Bot not configured yet. Run !setup first.")
            return

        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green() if self.bot.is_monitoring else discord.Color.orange()
        )

        config = self.bot.channel_config
        embed.add_field(
            name="Monitoring",
            value="🟢 Active" if self.bot.is_monitoring else "🔴 Inactive",
            inline=False
        )

        channels_text = []
        if config.super_hot_items:
            ch = self.bot.get_channel(config.super_hot_items)
            channels_text.append(f"🔥 Super Hot → {ch.mention if ch else 'Not found'}")
        if config.hot_items:
            ch = self.bot.get_channel(config.hot_items)
            channels_text.append(f"🌟 Hot Items → {ch.mention if ch else 'Not found'}")
        if config.all_alchs:
            ch = self.bot.get_channel(config.all_alchs)
            channels_text.append(f"🧪 All Alchs → {ch.mention if ch else 'Not found'}")
        if config.f2p_alchs:
            ch = self.bot.get_channel(config.f2p_alchs)
            channels_text.append(f"🆓 F2P Alchs → {ch.mention if ch else 'Not found'}")

        embed.add_field(
            name="Configured Channels",
            value="\n".join(channels_text) if channels_text else "None",
            inline=False
        )

        sub_count = len(self.bot.notification_manager.user_subscriptions)
        embed.add_field(
            name="Subscribers",
            value=f"{sub_count} user(s)",
            inline=False
        )

        if self.bot.last_update:
            embed.add_field(
                name="Last Update",
                value=self.bot.last_update.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    """Load the SetupCog"""
    await bot.add_cog(SetupCog(bot))
