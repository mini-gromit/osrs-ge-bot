import discord
from discord.ext import commands, tasks
import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
import aiohttp
from dotenv import load_dotenv
import os

from engine import OSRSAlchemyFlippingCalculator
from bot.config import ChannelConfig, ConfigManager
from bot.notifications import UserNotificationManager
from bot.converters import FlexibleChannelConverter
import config

logger = logging.getLogger(__name__)


class OSRSAlchemyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True

        super().__init__(
            command_prefix='!',
            intents=intents
        )

        self.calculator = OSRSAlchemyFlippingCalculator()
        self.config_manager = ConfigManager()
        self.notification_manager = UserNotificationManager()

        self.channel_config = None
        self.last_update = None
        self.is_monitoring = False
        self.opt_in_message_id = None

        self.persistence_minutes = config.ALERT_PERSISTENCE_MINUTES

        self.hot_items_min_profit = config.DEFAULT_HOT_ITEMS_MIN_PROFIT
        self.super_hot_min_profit = config.DEFAULT_SUPER_HOT_MIN_PROFIT
        self.all_alchs_min_profit = config.DEFAULT_ALL_ALCHS_MIN_PROFIT
        self.f2p_alchs_min_profit = config.DEFAULT_F2P_ALCHS_MIN_PROFIT

        self.last_notification_items = {
            'super_hot': [],
            'hot_items': [],
            'all_alchs': [],
            'f2p_alchs': [],
        }

        self.alchemy_message_cache = {
            'super_hot': {
                'items': [],
                'last_update': 0,
                'highest_profit': 0,
                'rolling_max_profit': 0
            },
            'hot_items': {
                'items': [],
                'last_update': 0,
                'highest_profit': 0,
                'rolling_max_profit': 0
            },
            'all_alchs': {
                'items': [],
                'last_update': 0,
                'highest_profit': 0,
                'rolling_max_profit': 0
            },
            'f2p_alchs': {
                'items': [],
                'last_update': 0,
                'highest_profit': 0,
                'rolling_max_profit': 0
            },
        }

        self.super_hot_max_items = config.SUPER_HOT_MAX_ITEMS
        self.super_hot_min_limit = config.SUPER_HOT_MIN_LIMIT
        self.super_hot_min_volume = config.SUPER_HOT_MIN_VOLUME
        self.super_hot_max_roi = config.SUPER_HOT_MAX_ROI

    # Emoji → (notification_type, display_label) mapping.
    # Drives the opt-in embed, reaction list, handler, and DM confirmations.
    REACTION_MAP = {
        '🔥': ('super_hot', 'Super Hot Items'),
        '🌟': ('hot_items', 'Hot Items'),
        '🧪': ('all_alchs', 'All Alchs'),
        '🆓': ('f2p_alchs', 'F2P Alchs'),
        '🔕': (None,        'Unsubscribe'),
    }

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

        await self.load_channel_config()

        if self.channel_config:
            await self.start_monitoring()

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent
    ):
        if payload.message_id != self.opt_in_message_id:
            return

        if payload.user_id == self.user.id:
            return

        emoji = str(payload.emoji)
        user_id = payload.user_id

        if emoji not in self.REACTION_MAP:
            return

        notif_type, label = self.REACTION_MAP[emoji]

        try:
            user = await self.fetch_user(user_id)
        except Exception as e:
            logger.warning(f"Could not fetch user {user_id}: {e}")
            return

        if not user:
            return

        if notif_type is None:
            removed = self.notification_manager.unsubscribe_user(user_id)
            if removed:
                try:
                    await user.send(
                        "🔕 You've been unsubscribed from all alchemy alerts."
                    )
                except Exception as e:
                    logger.warning(f"Could not DM user {user_id}: {e}")
            return

        subscribed = self.notification_manager.subscribe_user(
            user_id, notif_type
        )

        if subscribed:
            try:
                await user.send(
                    f"✅ You're now subscribed to **{label}** alchemy alerts!"
                )
            except Exception as e:
                logger.warning(f"Could not DM user {user_id}: {e}")

    async def load_channel_config(self):
        """Load channel configuration using ConfigManager"""
        self.channel_config = self.config_manager.load_config()

        if self.channel_config:
            self.hot_items_min_profit = self.config_manager.profit_thresholds.hot_items_min_profit
            self.super_hot_min_profit = self.config_manager.profit_thresholds.super_hot_min_profit
            self.all_alchs_min_profit = self.config_manager.profit_thresholds.all_alchs_min_profit
            self.f2p_alchs_min_profit = self.config_manager.profit_thresholds.f2p_alchs_min_profit
            self.opt_in_message_id = self.channel_config.opt_in_message_id
            logger.info("Channel config loaded successfully.")
        else:
            logger.info("No channel config found.")

    async def save_channel_config(self):
        """Save channel configuration using ConfigManager"""
        if not self.channel_config:
            return

        self.config_manager.profit_thresholds.hot_items_min_profit = self.hot_items_min_profit
        self.config_manager.profit_thresholds.super_hot_min_profit = self.super_hot_min_profit
        self.config_manager.profit_thresholds.all_alchs_min_profit = self.all_alchs_min_profit
        self.config_manager.profit_thresholds.f2p_alchs_min_profit = self.f2p_alchs_min_profit
        self.channel_config.opt_in_message_id = self.opt_in_message_id

        self.config_manager.save_config(self.channel_config)

    def get_item_ge_tracker_url(self, item_id=None, item_name=None):
        if item_id:
            return f"https://www.ge-tracker.com/item/{item_id}"

        if item_name:
            slug = (
                item_name.lower()
                .replace("'", "-")
                .replace(" ", "-")
                .replace("&", "and")
            )
            slug = re.sub(r'[^a-z0-9\-]', '', slug)
            return f"https://www.ge-tracker.com/item/{slug}"

        return None

    def merge_alchemy_items(self, message_type, new_items):
        current_time = time.time()
        cache = self.alchemy_message_cache[message_type]

        new_highest = max(
            (item['profit'] for item in new_items),
            default=0
        )

        time_expired = (
            current_time - cache['last_update']
        ) >= (self.persistence_minutes * 60)

        higher_profit = new_highest > (cache['highest_profit'] + 50)

        if time_expired or higher_profit:
            cache['items'] = new_items
            cache['last_update'] = current_time
            cache['highest_profit'] = new_highest
            cache['rolling_max_profit'] = max(
                cache['rolling_max_profit'],
                new_highest
            )

            for item in cache['items']:
                item['rolling_max_profit'] = cache['rolling_max_profit']

            return cache['items']

        return cache['items']

    async def fetch_and_analyze(self):
        logger.info("Fetching data for analysis...")

        current_time = time.time()

        if (
            not hasattr(self, '_last_mapping_fetch')
            or current_time - self._last_mapping_fetch > 3600
        ):
            if not self.calculator.fetch_item_mapping():
                return None, None, None, None

            self._last_mapping_fetch = current_time

        if not self.calculator.fetch_current_prices():
            return None, None, None, None

        try:
            self.calculator.fetch_volume_data()
        except Exception as e:
            logger.warning(f"Volume error: {e}")

        try:
            self.calculator.fetch_five_minute_data()
        except Exception as e:
            logger.warning(f"5m error: {e}")

        logger.info(
            f"Filtering: "
            f"super_hot >{self.super_hot_min_profit:,}gp | "
            f"hot >{self.hot_items_min_profit:,}gp | "
            f"all_alchs >{self.all_alchs_min_profit:,}gp | "
            f"limit ≥{self.super_hot_min_limit} | "
            f"vol ≥{self.super_hot_min_volume} | "
            f"ROI ≤{self.super_hot_max_roi}%"
        )

        # Super hot — top profitable items, members and F2P
        super_hot = self.calculator.get_profitable_items(
            min_profit=self.super_hot_min_profit,
            max_items=self.super_hot_max_items,
            min_limit=self.super_hot_min_limit,
            min_volume=self.super_hot_min_volume,
            max_roi=self.super_hot_max_roi
        )

        # Hot items — 450–999gp tier. max_items=200 ensures we reach this
        # range even when 50+ items exist above the super_hot threshold.
        hot_items = [
            item for item in self.calculator.get_profitable_items(
                min_profit=self.hot_items_min_profit,
                max_items=200,
                min_limit=self.super_hot_min_limit,
                min_volume=self.super_hot_min_volume,
                max_roi=self.super_hot_max_roi
            )
            if item['profit'] < self.super_hot_min_profit
        ][:15]

        # All alchs — every item with any positive alchemy profit.
        # One large query; f2p_alchs is derived from it to avoid a
        # redundant API call.
        all_profitable = self.calculator.get_profitable_items(
            min_profit=self.all_alchs_min_profit,
            max_items=500,
            min_limit=self.super_hot_min_limit,
            min_volume=self.super_hot_min_volume,
            max_roi=self.super_hot_max_roi
        )
        all_alchs = all_profitable[:20]

        # F2P alchs — same pool filtered to non-members items only
        f2p_alchs = [
            item for item in all_profitable
            if not item.get('members', True)
        ][:20]

        return super_hot, hot_items, all_alchs, f2p_alchs

    def create_embed(self, items, title, color):
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not items:
            embed.description = "No items found."
            return embed

        for i, item in enumerate(items[:10], 1):
            ge_url = self.get_item_ge_tracker_url(
                item_id=item.get('item_id'),
                item_name=item.get('name')
            )

            member_tag = "[M]" if item.get('members') else "[F2P]"

            embed.add_field(
                name=f"{i}. {member_tag} {item['name']}",
                value=(
                    f"[GE-Tracker]({ge_url})\n"
                    f"Profit: {item['profit']:,} gp\n"
                    f"Buy: {item['buy_price']:,} gp\n"
                    f"Alch: {item['high_alch_value']:,} gp\n"
                    f"ROI: {item['roi_percent']:.1f}%\n"
                    f"Current Profit: {item['profit']:,} gp\n"
                    f"5m Max Seen: "
                    f"{item.get('rolling_max_profit', item['profit']):,} gp"
                ),
                inline=True
            )

        return embed

    async def get_or_create_persistent_message(
        self,
        channel_id,
        message_id,
        embed,
        title_key
    ):
        channel = self.get_channel(channel_id)

        if not channel:
            return None

        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed)
                return msg
            except discord.NotFound:
                pass

        msg = await channel.send(embed=embed)

        id_attr = f"{title_key}_message_id"
        if hasattr(self.channel_config, id_attr):
            setattr(self.channel_config, id_attr, msg.id)

        await self.save_channel_config()

        return msg

    async def send_personal_notifications(
        self,
        super_hot,
        hot_items,
        all_alchs,
        f2p_alchs
    ):
        notifications = {
            'super_hot': (super_hot, "🔥 Super Hot Alchemy Alert!"),
            'hot_items': (hot_items, "🌟 Hot Alchemy Alert!"),
            'all_alchs': (all_alchs, "🧪 All Alchs Alert!"),
            'f2p_alchs': (f2p_alchs, "🆓 F2P Alchs Alert!"),
        }

        for notif_type, (items, title) in notifications.items():
            if not items:
                continue

            current_ids = {item['item_id'] for item in items}
            old_ids = {
                item['item_id']
                for item in self.last_notification_items[notif_type]
            }

            if current_ids == old_ids:
                continue

            self.last_notification_items[notif_type] = items

            subscribers = (
                self.notification_manager.get_subscribers_for_type(notif_type)
            )

            if not subscribers:
                continue

            embed = discord.Embed(
                title=title,
                color=discord.Color.red(),
                timestamp=datetime.now()
            )

            for item in items[:5]:
                embed.add_field(
                    name=item['name'],
                    value=(
                        f"Profit: {item['profit']:,} gp\n"
                        f"ROI: {item['roi_percent']:.1f}%"
                    ),
                    inline=False
                )

            for uid in subscribers:
                try:
                    user = await self.fetch_user(uid)
                    if user:
                        await user.send(embed=embed)
                except Exception:
                    pass

    async def send_updates_with_links(
        self,
        super_hot,
        hot_items,
        all_alchs,
        f2p_alchs
    ):
        if not self.channel_config:
            return

        if super_hot:
            super_hot = self.merge_alchemy_items('super_hot', super_hot)
            embed = self.create_embed(
                super_hot,
                f"🔥 SUPER HOT ALCHEMY (>{self.super_hot_min_profit:,}gp)",
                discord.Color.red()
            )
            await self.get_or_create_persistent_message(
                self.channel_config.super_hot_items,
                self.channel_config.super_hot_message_id,
                embed,
                "super_hot"
            )

        if hot_items:
            hot_items = self.merge_alchemy_items('hot_items', hot_items)
            embed = self.create_embed(
                hot_items,
                f"🌟 HOT ITEMS "
                f"({self.hot_items_min_profit:,}-"
                f"{self.super_hot_min_profit - 1:,}gp)",
                discord.Color.orange()
            )
            await self.get_or_create_persistent_message(
                self.channel_config.hot_items,
                self.channel_config.hot_items_message_id,
                embed,
                "hot_items"
            )

        if all_alchs and self.channel_config.all_alchs:
            all_alchs = self.merge_alchemy_items('all_alchs', all_alchs)
            embed = self.create_embed(
                all_alchs,
                f"🧪 ALL ALCHS (profit >{self.all_alchs_min_profit:,}gp)",
                discord.Color.purple()
            )
            await self.get_or_create_persistent_message(
                self.channel_config.all_alchs,
                self.channel_config.all_alchs_message_id,
                embed,
                "all_alchs"
            )

        if f2p_alchs and self.channel_config.f2p_alchs:
            f2p_alchs = self.merge_alchemy_items('f2p_alchs', f2p_alchs)
            embed = self.create_embed(
                f2p_alchs,
                f"🆓 F2P ALCHS (profit >{self.f2p_alchs_min_profit:,}gp)",
                discord.Color.green()
            )
            await self.get_or_create_persistent_message(
                self.channel_config.f2p_alchs,
                self.channel_config.f2p_alchs_message_id,
                embed,
                "f2p_alchs"
            )

        await self.send_personal_notifications(
            super_hot, hot_items, all_alchs, f2p_alchs
        )

        logger.info(
            f"Update complete at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    @tasks.loop(minutes=config.MONITORING_INTERVAL_MINUTES)
    async def monitor_prices_with_links(self):
        try:
            super_hot, hot_items, all_alchs, f2p_alchs = (
                await self.fetch_and_analyze()
            )

            if super_hot is not None:
                await self.send_updates_with_links(
                    super_hot, hot_items, all_alchs, f2p_alchs
                )
                self.last_update = datetime.now()

        except Exception as e:
            import traceback
            logger.error(f"Error in monitor loop: {e}")
            logger.error(traceback.format_exc())

    async def start_monitoring(self):
        if self.is_monitoring:
            return

        logger.info("Running initial update...")

        try:
            super_hot, hot_items, all_alchs, f2p_alchs = (
                await self.fetch_and_analyze()
            )

            if super_hot is not None:
                await self.send_updates_with_links(
                    super_hot, hot_items, all_alchs, f2p_alchs
                )
                self.last_update = datetime.now()

        except Exception as e:
            import traceback
            logger.error(f"Initial update error: {e}")
            logger.error(traceback.format_exc())

        self.monitor_prices_with_links.start()
        self.is_monitoring = True

        logger.info(f"Started monitoring every {config.MONITORING_INTERVAL_MINUTES} minutes")


# ------------------------------------------------------------------ #
# !setup
#
# Uses FlexibleChannelConverter so all of these work identically:
#   !setup #super-hot #hot-items
#   !setup #super-hot #hot-items #welcome
#   !setup #super-hot #hot-items #welcome #all-alchs #f2p-alchs
#   !setup super-hot hot-items          (no # prefix)
#   !setup 123456789 987654321          (raw channel IDs)
# ------------------------------------------------------------------ #
@commands.command(name='setup')
async def setup_channels(
    ctx,
    super_hot_channel: FlexibleChannelConverter,
    hot_channel: FlexibleChannelConverter,
    welcome_channel: Optional[FlexibleChannelConverter] = None,
    all_alchs_channel: Optional[FlexibleChannelConverter] = None,
    f2p_alchs_channel: Optional[FlexibleChannelConverter] = None,
):
    bot = ctx.bot

    bot.channel_config = ChannelConfig(
        super_hot_items=super_hot_channel.id,
        hot_items=hot_channel.id,
        welcome_channel=welcome_channel.id if welcome_channel else None,
        all_alchs=all_alchs_channel.id if all_alchs_channel else None,
        f2p_alchs=f2p_alchs_channel.id if f2p_alchs_channel else None,
    )

    await bot.save_channel_config()

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
    await bot.start_monitoring()


@commands.command(name='setup_help')
async def setup_help(ctx):
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
async def create_optin(ctx):
    bot = ctx.bot

    if not bot.channel_config:
        await ctx.send("❌ Run !setup first.")
        return

    channel = bot.get_channel(bot.channel_config.welcome_channel)

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

    for emoji in bot.REACTION_MAP.keys():
        await msg.add_reaction(emoji)

    bot.opt_in_message_id = msg.id
    await bot.save_channel_config()

    await ctx.send("✅ Opt-in message created.")


@commands.command(name='status')
async def status_cmd(ctx):
    bot = ctx.bot

    embed = discord.Embed(title="Bot Status", color=discord.Color.blue())

    embed.add_field(
        name="Monitoring",
        value="✅ Active" if bot.is_monitoring else "❌ Stopped"
    )

    if bot.last_update:
        embed.add_field(
            name="Last Update",
            value=bot.last_update.strftime('%Y-%m-%d %H:%M:%S')
        )

    if bot.channel_config:
        lines = [
            f"🔥 Super Hot: <#{bot.channel_config.super_hot_items}>",
            f"🌟 Hot Items:  <#{bot.channel_config.hot_items}>",
        ]
        if bot.channel_config.all_alchs:
            lines.append(f"🧪 All Alchs: <#{bot.channel_config.all_alchs}>")
        if bot.channel_config.f2p_alchs:
            lines.append(f"🆓 F2P Alchs: <#{bot.channel_config.f2p_alchs}>")
        embed.add_field(
            name="Channels",
            value="\n".join(lines),
            inline=False
        )

    await ctx.send(embed=embed)


@commands.command(name='test')
async def test_cmd(ctx):
    bot = ctx.bot

    super_hot, hot_items, all_alchs, f2p_alchs = (
        await bot.fetch_and_analyze()
    )

    await bot.send_updates_with_links(
        super_hot, hot_items, all_alchs, f2p_alchs
    )

    await ctx.send("✅ Test update complete.")


async def setup_bot():
    """Setup and configure the bot"""
    bot = OSRSAlchemyBot()

    await bot.load_extension('bot.cogs.setup')

    bot.add_command(test_cmd)

    return bot


async def main():
    """Main entry point"""
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        level=getattr(logging, config.LOG_LEVEL)
    )

    TOKEN = os.getenv('DISCORD_APP_TOKEN')

    if not TOKEN:
        logger.error("DISCORD_APP_TOKEN missing")
        exit(1)

    bot = await setup_bot()
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())