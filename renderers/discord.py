import re
import discord
from datetime import datetime
from typing import List, Dict, Optional
from events import CrashRiskEvent, FlippingTrendEvent


class DiscordRenderer:
    """
    Discord-specific presentation logic.

    Handles embed creation, formatting, colors, and Discord-specific rules.
    Consumes business/domain data and produces Discord embeds.
    """

    @staticmethod
    def format_volume_compact(volume: int) -> str:
        """
        Format volume with k/m suffix for compact display.

        Args:
            volume: Volume count (hourly)

        Returns:
            Formatted string like "850", "2.4k", "18k"
        """
        if volume >= 10000:
            return f"{volume/1000:.0f}k"
        elif volume >= 1000:
            return f"{volume/1000:.1f}k"
        else:
            return str(volume)

    @staticmethod
    def format_5m_price_range(avg_low: Optional[int], lowest_buy: Optional[int]) -> str:
        """
        Format 5-minute price range with arrow notation.

        Shows average and lowest as range, or just what's available.
        Uses ─ for missing data instead of "N/A".

        Args:
            avg_low: 5-minute average low price
            lowest_buy: Lowest observed buy price in recent 5m windows

        Returns:
            Formatted string like "2,450→2,350", "2,450", or "─"
        """
        if avg_low is None and lowest_buy is None:
            return "─"

        if avg_low is None:
            return f"→{lowest_buy:,}" if lowest_buy else "─"

        if lowest_buy is None:
            return f"{avg_low:,}"

        # Both available - show range if different
        if avg_low == lowest_buy:
            return f"{avg_low:,}"

        return f"{avg_low:,}→{lowest_buy:,}"

    @staticmethod
    def get_item_ge_tracker_url(item_id: Optional[int] = None, item_name: Optional[str] = None) -> Optional[str]:
        """
        Generate GE-Tracker URL for an item.

        Args:
            item_id: Item ID (preferred)
            item_name: Item name (fallback)

        Returns:
            GE-Tracker URL or None
        """
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

    @staticmethod
    def create_alchemy_embed(
        items: List[Dict],
        title: str,
        color: discord.Color
    ) -> discord.Embed:
        """
        Compact trading-terminal style embed.

        One item = two lines.

        ⭐ = Current buy is at the best 5m buy opportunity.
        🏆 = Members
        💎 = F2P
        """

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not items:
            embed.description = "No items found."
            return embed

        lines = []

        for i, item in enumerate(items[:3], 1):

            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=item.get("item_id"),
                item_name=item.get("name"),
            )

            member = "🏆" if item.get("members") else "💎"

            star = " ⭐" if item.get("is_at_five_min_low") else ""

            price_range = DiscordRenderer.format_5m_price_range(
                item.get("five_min_avg_low"),
                item.get("five_min_lowest_buy"),
            )

            volume = DiscordRenderer.format_volume_compact(
                item.get("recent_volume", 0)
            )

            lines.append(
                f"**{i}. {member} [{item['name']}]({ge_url}){star}**"
                f"`{item['profit']:,} gp` • "
                f"Buy `{item['buy_price']:,}` • "
                f"5m `{price_range}` • "
                f"Vol `{volume}/hr`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="⭐ Current buy matches lowest 5m buy opportunity"
        )

        return embed


    @staticmethod
    def create_notification_embed(items: List[Dict], title: str) -> discord.Embed:
        """
        Create a simpler Discord embed for personal notifications.

        Args:
            items: List of alchemy item dicts
            title: Notification title

        Returns:
            Discord embed
        """
        embed = discord.Embed(
            title=title,
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        for item in items[:3]:
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=item.get("item_id"),
                item_name=item.get("name"),
            )

            member = "🏆" if item.get("members") else "💎"

            embed.add_field(
                name="​",  # No field name for personal notifications
                value=(
                    f"{member} [{item['name']}]({ge_url})\n"
                    f"`+{item['profit']:,} gp` • "
                    f"Buy `{item['buy_price']:,}`"
                ),
                inline=False
            )

        return embed

    @staticmethod
    def create_crash_risk_alert_embed(
        alerts: List[CrashRiskEvent],
        title: str = "🚨 Crash Risk Alerts"
    ) -> discord.Embed:

        color = (
            discord.Color.red()
            if any(a.status == "crashing" for a in alerts)
            else discord.Color.orange()
        )

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "No crash risks detected."
            return embed

        lines = []

        for i, alert in enumerate(alerts[:8], 1):

            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name,
            )

            member = "🏆" if alert.members else "💎"

            # Confidence: emoji from volume quality, number from confidence score
            confidence_emoji = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🟠",
                "very_low": "🔴",
            }.get(alert.volume_confidence, "⚪")

            # Price movement: show direction with symbols
            if alert.price_decline_percent is None:
                trend = "—"
            elif alert.price_decline_percent < -0.1:
                trend = f"▼{abs(alert.price_decline_percent):.1f}%"
            elif alert.price_decline_percent > 0.1:
                trend = f"▲{alert.price_decline_percent:.1f}%"
            else:
                trend = "—"

            # Format buy price compactly
            # buy_fmt = DiscordRenderer.format_volume_compact(alert.buy_price)
            vol_fmt = DiscordRenderer.format_volume_compact(alert.hourly_volume)

            lines.append(
                f"**{i}. {member} [{alert.name}]({ge_url})** "
                f"`{alert.profit:,} gp` • "
                f"Buy `{alert.buy_price}` • "
                f"Press `{alert.volume_ratio:.1f}x` • "
                f"{trend} • "
                f"Vol `{vol_fmt}/hr` • "
                f"{confidence_emoji}{alert.confidence_score}"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Press = sell/buy ratio • Trend = 5min price change • Confidence color = volume quality"
        )

        return embed
    
    @staticmethod
    def create_flipping_trend_alert_embed(
        alerts: List[FlippingTrendEvent],
        title: str = "💰 Flipping Opportunities"
    ) -> discord.Embed:
        """
        Compact trading-terminal style flipping embed.

        Shows actionable flipping opportunities with:
        - Buy/sell prices
        - Net profit after 2% GE tax
        - Price trend direction
        - Volume and liquidity
        """

        statuses = {a.status for a in alerts}

        if "surging" in statuses:
            color = discord.Color.green()
        elif "crashing" in statuses:
            color = discord.Color.red()
        else:
            color = discord.Color.gold()

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "No actionable flipping opportunities at this time."
            return embed

        lines = []

        # Limit to 8 items to fit Discord embed limits
        for i, alert in enumerate(alerts[:8], 1):

            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name,
            )

            member = "🏆" if alert.members else "💎"

            # Price trend: show direction with symbols
            if alert.price_change_percent > 0.1:
                trend = f"▲{alert.price_change_percent:.1f}%"
            elif alert.price_change_percent < -0.1:
                trend = f"▼{abs(alert.price_change_percent):.1f}%"
            else:
                trend = "—"

            # Confidence: emoji based on confidence score
            if alert.confidence_score >= 80:
                confidence_emoji = "🟢"
            elif alert.confidence_score >= 60:
                confidence_emoji = "🟡"
            elif alert.confidence_score >= 40:
                confidence_emoji = "🟠"
            else:
                confidence_emoji = "🔴"

            # # Format prices compactly
            # buy_fmt = DiscordRenderer.format_volume_compact(alert.buy_price)
            # sell_fmt = DiscordRenderer.format_volume_compact(alert.sell_price)
            vol_fmt = DiscordRenderer.format_volume_compact(alert.hourly_volume)

            # Compact terminal format
            lines.append(
                f"**{i}. {member} [{alert.name}]({ge_url})** "
                f"`{alert.buy_price} → {alert.sell_price}` • "
                f"`+{alert.net_profit:,} gp` • "
                f"ROI `{alert.margin_percent:.1f}%` • "
                f"{trend} • "
                f"Vol `{vol_fmt}/hr` • "
                f"{confidence_emoji}{alert.confidence_score}"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Net profit after 2% GE tax • Sorted by opportunity score • Confidence color = signal quality"
        )

        return embed
    
    @staticmethod
    def create_profitable_alchemy_alert_embed(
        alerts: List['ProfitableAlchemyEvent'],
        title: str = "💰 Profitable Alchemy Alert"
    ) -> discord.Embed:
        """
        Create Discord embed for profitable alchemy alerts.

        Reuses layout from create_alchemy_embed but accepts MarketEvent objects.

        Args:
            alerts: List of ProfitableAlchemyEvent objects
            title: Embed title

        Returns:
            Discord Embed object
        """
        from events import ProfitableAlchemyEvent

        embed = discord.Embed(
            title=title,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "No profitable items at this time."
            return embed

        # Limit to 10 items to fit embed limits
        alerts = alerts[:10]

        # Build compact item list
        lines = []

        for alert in alerts:
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name,
            )

            star = " ⭐" if getattr(alert, "is_at_five_min_low", False) else ""

            price_range = DiscordRenderer.format_5m_price_range(
                getattr(alert, "five_min_avg_low", None),
                getattr(alert, "lowest_low", None),
            )

            lines.append(
                f"**[{alert.name}]({ge_url}){star}**\n"
                f"`+{alert.profit:,} gp` • "
                f"Buy `{alert.buy_price:,}` • "
                f"5m `{price_range}`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="⭐ Current buy matches lowest 5m buy opportunity"
        )

        return embed
