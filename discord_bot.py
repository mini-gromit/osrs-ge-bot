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
from renderers import DiscordRenderer
from scheduler import DataScheduler
from notifications import AlertPolicy, JsonPreferenceStore, NotificationQueue
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
        self.scheduler = DataScheduler(self.calculator)
        self.config_manager = ConfigManager()
        self.notification_manager = UserNotificationManager()

        # Initialize alert policy layer for notification filtering
        self.preference_store = JsonPreferenceStore(
            filename='user_preferences.json',
            subscription_manager=self.notification_manager
        )
        self.alert_policy = AlertPolicy(self.preference_store)

        # Initialize notification batching queue (uses config defaults)
        self.notification_queue = NotificationQueue()

        self.channel_config = None
        self.last_update = None
        self.is_monitoring = False

        self.persistence_minutes = config.ALERT_PERSISTENCE_MINUTES

        self.hot_items_min_profit = config.DEFAULT_HOT_ITEMS_MIN_PROFIT
        self.super_hot_min_profit = config.DEFAULT_SUPER_HOT_MIN_PROFIT
        self.all_alchs_min_profit = config.DEFAULT_ALL_ALCHS_MIN_PROFIT
        self.f2p_alchs_min_profit = config.DEFAULT_F2P_ALCHS_MIN_PROFIT

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

        self.is_refreshing = False

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

        # Sync slash commands
        try:
            # Check for development guild ID for instant command sync
            dev_guild_id = os.getenv('DEV_GUILD_ID')

            if dev_guild_id:
                # Guild-specific sync for instant updates during development
                guild = discord.Object(id=int(dev_guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced)} slash command(s) to guild {dev_guild_id} (instant)")
            else:
                # Global sync for production (takes up to 1 hour to propagate)
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash command(s) globally (may take up to 1 hour to appear)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        await self.load_channel_config()

        # Start background market data refresh task
        if not self.is_refreshing:
            logger.info("Starting background market data refresh...")
            self.background_refresh_loop.start()
            self.is_refreshing = True
            logger.info(f"Background refresh started (every {config.REFRESH_INTERVAL_CURRENT_PRICES}s)")

        if self.channel_config:
            await self.start_monitoring()

    async def load_channel_config(self):
        """Load channel configuration using ConfigManager"""
        self.channel_config = self.config_manager.load_config()

        if self.channel_config:
            self.hot_items_min_profit = self.config_manager.profit_thresholds.hot_items_min_profit
            self.super_hot_min_profit = self.config_manager.profit_thresholds.super_hot_min_profit
            self.all_alchs_min_profit = self.config_manager.profit_thresholds.all_alchs_min_profit
            self.f2p_alchs_min_profit = self.config_manager.profit_thresholds.f2p_alchs_min_profit
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

        self.config_manager.save_config(self.channel_config)


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
        """
        Analyze market data and produce filtered results for channel updates.

        Returns:
            tuple: Always returns exactly 5 values:
                - super_hot: List of top profitable items (or None if data not ready)
                - hot_items: List of mid-tier profitable items (or None if data not ready)
                - all_alchs: List of all profitable alchemy items (or None if data not ready)
                - f2p_alchs: List of F2P profitable alchemy items (or None if data not ready)
                - alchemy_events: List of ProfitableAlchemyEvent objects (or None if data not ready)

            When market data is not ready, returns (None, None, None, None, None).
            Callers must check if super_hot is None before using results.
        """
        logger.info("Fetching data for analysis...")

        # Wait for initial data from background refresh task
        # Background task continuously refreshes market data independently
        has_prices = bool(self.calculator.current_prices)
        has_items = bool(self.calculator.item_mapping)

        if not has_prices or not has_items:
            logger.warning(
                f"[MONITOR] Market data not ready yet "
                f"(prices={has_prices}, items={has_items}) - skipping this cycle"
            )
            return None, None, None, None, None

        logger.info(
            f"Filtering: "
            f"super_hot >{self.super_hot_min_profit:,}gp | "
            f"hot >{self.hot_items_min_profit:,}gp | "
            f"all_alchs >{self.all_alchs_min_profit:,}gp | "
            f"limit ≥{self.super_hot_min_limit} | "
            f"vol ≥{self.super_hot_min_volume} | "
            f"ROI ≤{self.super_hot_max_roi}%"
        )

        # Read fully prepared market data from engine.
        # Background refresh task has already:
        #   - Refreshed current_prices, volume_data, five_min_data
        #   - Enriched five_min_data with historical minimums
        # This method performs zero network I/O - only reads prepared data.

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

        # Convert filtered items to events for personal notifications
        # Reuses same quality-filtered data for both channels and DMs
        alchemy_events = self._convert_items_to_events(all_profitable)

        return super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events

    def _convert_items_to_events(self, items):
        """
        Convert filtered alchemy item dicts to ProfitableAlchemyEvent objects.

        Reuses already-filtered market data to avoid duplicate computation.
        Ensures channel notifications and personal DMs use the same quality filters.

        Args:
            items: List of filtered alchemy item dicts

        Returns:
            List of ProfitableAlchemyEvent objects
        """
        from events import ProfitableAlchemyEvent

        events = []
        for item in items:
            profit = item['profit']

            # Calculate severity score based on profit tier
            if profit >= self.super_hot_min_profit:
                severity_score = config.SEVERITY_SUPER_HOT
            elif profit >= self.hot_items_min_profit:
                severity_score = config.SEVERITY_HOT_ITEMS
            elif profit >= 100:
                severity_score = config.SEVERITY_ALL_ALCHS_HIGH
            else:
                severity_score = config.SEVERITY_ALL_ALCHS_LOW

            event = ProfitableAlchemyEvent(
                name=item['name'],
                item_id=item['item_id'],
                profit=profit,
                buy_price=item['buy_price'],
                alch_value=item['high_alch_value'],
                roi_percent=item.get('roi_percent', 0),
                trade_limit=item.get('limit', 0),
                hourly_volume=item.get('recent_volume', 0),
                members=item.get('members', True),
                severity_score=severity_score,
                lowest_low=item.get('five_min_lowest_buy', 0) or 0
            )
            events.append(event)

        return events

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

    async def send_alchemy_event_notifications(self, alchemy_events):
        """
        Process profitable alchemy alerts through event-based notification pipeline.

        Flow:
        1. Receive filtered ProfitableAlchemyEvent objects (computed once by fetch_and_analyze)
        2. Filter through AlertPolicy for personal notification types
        3. Enqueue NotificationDecisions for batching
        4. Send ready notifications (respects batching window)

        Args:
            alchemy_events: List of ProfitableAlchemyEvent objects (already quality-filtered)
        """
        try:
            if not alchemy_events:
                return

            # Production log: event processing
            logger.info(f"[NOTIFY] Processing {len(alchemy_events)} filtered alchemy events")

            # Process personal notification types through AlertPolicy
            # Personal notifications: all_alchs, f2p_alchs only
            # Channel notifications (super_hot, hot_items) handled separately
            notification_types = ['all_alchs', 'f2p_alchs']

            for notif_type in notification_types:
                # Filter events through AlertPolicy
                # Policy handles: user thresholds, F2P filtering, cooldowns, duplicates
                notifications = self.alert_policy.filter_events(
                    alchemy_events,
                    notif_type
                )

                if notifications:
                    # Enqueue for batching (queue owns timing logic)
                    self.notification_queue.enqueue_batch(notifications)

            # Get ready notifications from queue
            # Queue determines readiness based on batching window, batch size, priority
            ready_notifications = self.notification_queue.get_ready_notifications()

            if ready_notifications:
                await self._send_ready_notifications_alchemy(ready_notifications)

        except Exception as e:
            logger.error(f"Error in alchemy event notifications: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _send_ready_notifications_alchemy(
        self,
        ready_notifications: dict
    ):
        """
        Send ready profitable alchemy notifications to users.

        Separate from _send_ready_notifications to allow different rendering
        during parallel operation phase.

        Args:
            ready_notifications: Dict mapping user_id to list of NotificationDecisions
        """
        from events import ProfitableAlchemyEvent
        from renderers import DiscordRenderer

        for user_id, notifications in ready_notifications.items():
            try:
                # Group notifications by type for better presentation
                by_type = {}
                for notification in notifications:
                    notif_type = notification.notification_type
                    if notif_type not in by_type:
                        by_type[notif_type] = []
                    by_type[notif_type].append(notification.event)

                # Send one message per notification type
                user = await self.fetch_user(user_id)
                if not user:
                    continue

                for notif_type, events in by_type.items():
                    # Determine title based on type
                    title_map = {
                        'all_alchs': '🧪 All Alchs Alert',
                        'f2p_alchs': '🆓 F2P Alchs Alert'
                    }
                    title = title_map.get(notif_type, '💰 Alchemy Alert')

                    # Create embed
                    embed = DiscordRenderer.create_profitable_alchemy_alert_embed(
                        events,
                        title
                    )

                    # Send DM
                    await user.send(embed=embed)

                # Production log: batch sent
                total_count = sum(len(events) for events in by_type.values())
                logger.info(
                    f"[NOTIFY] Sent batch: "
                    f"user={user_id}, "
                    f"count={total_count}"
                )

            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")

    async def send_market_event_notifications(self):
        """
        Process MarketEvent alerts through AlertPolicy and NotificationQueue.

        Flow:
        1. Fetch MarketEvents (crash risk, flipping trends)
        2. Filter through AlertPolicy (severity, cooldowns, duplicates)
        3. Enqueue NotificationDecisions for batching
        4. Get ready notifications from queue (batching window: 60s)
        5. Send batched or single notifications to users

        Uses NotificationQueue for batching - queue owns timing logic.
        """
        try:
            # Fetch crash risk alerts
            crash_events = self.calculator.get_alchemy_alerts(
                min_profit=100,
                min_volume_imbalance=2.0
            )

            if crash_events:
                # Filter through AlertPolicy
                notifications = self.alert_policy.filter_events(
                    crash_events,
                    'crash_risk'
                )

                # Enqueue for batching (queue owns timing)
                self.notification_queue.enqueue_batch(notifications)

        except Exception as e:
            logger.warning(f"Error processing crash risk notifications: {e}")

        try:
            # Fetch flipping trend alerts
            trend_events = self.calculator.get_flipping_alerts(
                min_margin=1000,
                min_volume=20
            )

            if trend_events:
                # Filter through AlertPolicy
                notifications = self.alert_policy.filter_events(
                    trend_events,
                    'flipping_trend'
                )

                # Enqueue for batching (queue owns timing)
                self.notification_queue.enqueue_batch(notifications)

        except Exception as e:
            logger.warning(f"Error processing flipping trend notifications: {e}")

        # Get notifications ready for delivery (queue decides based on batching window)
        ready_notifications = self.notification_queue.get_ready_notifications()

        # Send ready notifications (batched or single)
        await self._send_ready_notifications(ready_notifications)

    async def _send_ready_notifications(self, ready_notifications: dict):
        """
        Send ready notifications to users via DM.

        Handles both single and batched notifications.

        Args:
            ready_notifications: Dict mapping user_id to list of NotificationDecisions
        """
        for user_id, user_notifications in ready_notifications.items():
            try:
                user = await self.fetch_user(user_id)
                if not user:
                    continue

                # Single notification - send normally
                if len(user_notifications) == 1:
                    await self._send_single_notification(user, user_notifications[0])
                else:
                    # Multiple notifications - send as batch
                    await self._send_batched_notifications(user, user_notifications)

            except Exception as e:
                logger.error(f"Failed to send notifications to user {user_id}: {e}")

    async def _send_single_notification(self, user, notification):
        """
        Send a single notification to a user.

        Args:
            user: Discord user object
            notification: NotificationDecision object
        """
        try:
            # Determine emoji based on priority
            if notification.priority == 'critical':
                priority_emoji = '🚨'
            elif notification.priority == 'high':
                priority_emoji = '🔴'
            elif notification.priority == 'medium':
                priority_emoji = '🟡'
            else:
                priority_emoji = '🔵'

            if notification.notification_type == 'crash_risk':
                embed = DiscordRenderer.create_crash_risk_alert_embed(
                    [notification.event],
                    f"{priority_emoji} Alchemy Crash Risk Alert"
                )
            elif notification.notification_type == 'flipping_trend':
                embed = DiscordRenderer.create_flipping_trend_alert_embed(
                    [notification.event],
                    f"{priority_emoji} Market Trend Alert"
                )
            else:
                return

            await user.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to send single notification: {e}")

    async def _send_batched_notifications(self, user, notifications):
        """
        Send multiple notifications as a batched digest to a user.

        Args:
            user: Discord user object
            notifications: List of NotificationDecision objects
        """
        try:
            # Group by notification type
            crash_risk_events = [
                n.event for n in notifications
                if n.notification_type == 'crash_risk'
            ]
            trend_events = [
                n.event for n in notifications
                if n.notification_type == 'flipping_trend'
            ]

            # Send crash risk batch
            if crash_risk_events:
                embed = DiscordRenderer.create_crash_risk_alert_embed(
                    crash_risk_events,
                    f"🔔 Alchemy Alert Digest ({len(crash_risk_events)} items)"
                )
                await user.send(embed=embed)

            # Send trend batch
            if trend_events:
                embed = DiscordRenderer.create_flipping_trend_alert_embed(
                    trend_events,
                    f"🔔 Market Alert Digest ({len(trend_events)} items)"
                )
                await user.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to send batched notifications: {e}")

    async def send_market_event_alerts(self):
        """
        Fetch and send MarketEvent alerts to configured alert channels.

        Handles CrashRiskEvent and FlippingTrendEvent alerts.
        Separate from user DM notifications (handled by send_market_event_notifications).
        """
        if not self.channel_config:
            return

        # Fetch crash risk alerts if channel configured
        if self.channel_config.crash_risk_alerts:
            try:
                crash_alerts = self.calculator.get_alchemy_alerts(
                    min_profit=100,
                    min_volume_imbalance=2.0
                )

                if crash_alerts:
                    embed = DiscordRenderer.create_crash_risk_alert_embed(
                        crash_alerts,
                        "🚨 Alchemy Crash Risk Alerts"
                    )

                    await self.get_or_create_persistent_message(
                        self.channel_config.crash_risk_alerts,
                        self.channel_config.crash_risk_message_id,
                        embed,
                        "crash_risk"
                    )

            except Exception as e:
                logger.warning(f"Error sending crash risk alerts: {e}")

        # Fetch flipping trend alerts if channel configured
        if self.channel_config.flipping_trend_alerts:
            try:
                flipping_alerts = self.calculator.get_flipping_alerts(
                    min_margin=1000,
                    min_volume=20
                )

                if flipping_alerts:
                    embed = DiscordRenderer.create_flipping_trend_alert_embed(
                        flipping_alerts,
                        "📊 Flipping Market Trend Alerts"
                    )

                    await self.get_or_create_persistent_message(
                        self.channel_config.flipping_trend_alerts,
                        self.channel_config.flipping_trend_message_id,
                        embed,
                        "flipping_trend"
                    )

            except Exception as e:
                logger.warning(f"Error sending flipping trend alerts: {e}")

    async def send_updates_with_links(
        self,
        super_hot,
        hot_items,
        all_alchs,
        f2p_alchs,
        alchemy_events
    ):
        if not self.channel_config:
            return

        if super_hot:
            super_hot = self.merge_alchemy_items('super_hot', super_hot)
            embed = DiscordRenderer.create_alchemy_embed(
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
            embed = DiscordRenderer.create_alchemy_embed(
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
            embed = DiscordRenderer.create_alchemy_embed(
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
            embed = DiscordRenderer.create_alchemy_embed(
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

        # Send personal DM notifications through event-based pipeline
        # Reuses same filtered events as channel notifications
        await self.send_alchemy_event_notifications(alchemy_events)

        # Send MarketEvent alerts to dedicated alert channels
        await self.send_market_event_alerts()

        # Send MarketEvent notifications to users via DM using AlertPolicy
        await self.send_market_event_notifications()

        logger.info(
            f"Update complete at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    @tasks.loop(seconds=config.REFRESH_INTERVAL_CURRENT_PRICES)
    async def background_refresh_loop(self):
        """
        Background task that continuously refreshes market data.

        Runs independently from Discord event loop using asyncio.to_thread
        to avoid blocking. Scheduler handles staleness checks and triggers
        engine enrichment workflow.

        Blocking HTTP requests and time.sleep() occur in worker thread only,
        never in Discord event loop.
        """
        try:
            # Run synchronous scheduler.refresh_all() in thread pool
            # This includes blocking HTTP requests and historical enrichment
            await asyncio.to_thread(self.scheduler.refresh_all)

        except Exception as e:
            import traceback
            logger.error(f"Error in background refresh: {e}")
            logger.error(traceback.format_exc())

    @tasks.loop(seconds=config.MONITORING_INTERVAL_SECONDS)
    async def monitor_prices_with_links(self):
        try:
            result = await self.fetch_and_analyze()

            # Defensive validation: ensure we got 5-tuple
            if not isinstance(result, tuple) or len(result) != 5:
                logger.error(
                    f"[MONITOR] fetch_and_analyze() returned invalid result: "
                    f"expected 5-tuple, got {type(result).__name__} with length {len(result) if isinstance(result, tuple) else 'N/A'}"
                )
                return

            super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events = result

            if super_hot is not None:
                await self.send_updates_with_links(
                    super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events
                )
                self.last_update = datetime.now()

        except ValueError as e:
            logger.error(
                f"[MONITOR] Tuple unpacking failed - fetch_and_analyze() return value mismatch: {e}",
                exc_info=True
            )
        except Exception as e:
            import traceback
            logger.error(f"[MONITOR] Unexpected error in monitor loop: {e}")
            logger.error(traceback.format_exc())

    async def start_monitoring(self):
        if self.is_monitoring:
            return

        logger.info("Waiting for initial market data from background refresh...")

        # Wait briefly for background refresh to load initial data
        # Background task runs every 2 seconds, so wait up to 10 seconds
        max_wait_seconds = 10
        waited = 0
        while (not self.calculator.current_prices or not self.calculator.item_mapping) and waited < max_wait_seconds:
            await asyncio.sleep(1)
            waited += 1

        if not self.calculator.current_prices or not self.calculator.item_mapping:
            logger.warning("Initial data not available yet - monitoring will start when data is ready")
        else:
            logger.info("Initial data loaded - running first update...")

        try:
            super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events = (
                await self.fetch_and_analyze()
            )

            if super_hot is not None:
                await self.send_updates_with_links(
                    super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events
                )
                self.last_update = datetime.now()

        except Exception as e:
            import traceback
            logger.error(f"Initial update error: {e}")
            logger.error(traceback.format_exc())

        self.monitor_prices_with_links.start()
        self.is_monitoring = True

        logger.info(f"Started monitoring every {config.MONITORING_INTERVAL_SECONDS} seconds")


@commands.command(name='test')
async def test_cmd(ctx):
    bot = ctx.bot

    super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events = (
        await bot.fetch_and_analyze()
    )

    await bot.send_updates_with_links(
        super_hot, hot_items, all_alchs, f2p_alchs, alchemy_events
    )

    await ctx.send("✅ Test update complete.")


async def setup_bot():
    """Setup and configure the bot"""
    bot = OSRSAlchemyBot()

    await bot.load_extension('bot.cogs.setup')
    await bot.load_extension('bot.cogs.notifications')

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