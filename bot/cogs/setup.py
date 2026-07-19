import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List, Tuple

from bot.converters import FlexibleChannelConverter
from bot.config import ChannelConfig


class SetupCog(commands.Cog, name="Setup"):
    """Commands for configuring the bot"""

    def __init__(self, bot):
        self.bot = bot

    async def start_setup_flow(self, source):
        """Shared setup flow for both slash and prefix commands."""

        # Check if already configured
        if self.bot.channel_config:
            config = self.bot.channel_config
            embed = discord.Embed(
                title="⚙️ Bot Already Configured",
                description="Your bot is already set up. Current configuration:",
                color=discord.Color.blue()
            )

            config_lines = []
            for key, name, emoji, required, desc in self.CHANNEL_TYPES:
                channel_id = getattr(config, key, None)
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        config_lines.append(f"{emoji} **{name}** → {channel.mention}")
                    else:
                        config_lines.append(f"{emoji} **{name}** → ⚠️ Channel not found")

            if config_lines:
                embed.add_field(
                    name="Configured Channels",
                    value="\n".join(config_lines),
                    inline=False
                )

            view = ReconfigureView(self.bot, self.CHANNEL_TYPES)

        else:
            embed = discord.Embed(
                title="🛠️ Bot Setup Wizard",
                description=(
                    "Welcome! Let's configure your OSRS Alchemy Bot.\n\n"
                    "**What you'll do:**\n"
                    "• Select channels for alerts\n"
                    "• Review permissions\n"
                    "• Test your configuration\n\n"
                    "**Time:** ~2 minutes\n"
                    "Click **Begin Setup** to start."
                ),
                color=discord.Color.green()
            )

            view = StartSetupView(self.bot, self.CHANNEL_TYPES)

        if isinstance(source, discord.Interaction):
            await source.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True,
            )
        else:
            await source.send(embed=embed, view=view)

    @commands.command(name="setup")
    async def setup(self, ctx):
        await self.start_setup_flow(ctx)

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

    # =============================================================================
    # Interactive Setup System (Slash Commands)
    # =============================================================================

    # Channel configuration types: (key, display_name, emoji, required, description)
    CHANNEL_TYPES: List[Tuple[str, str, str, bool, str]] = [
        ('super_hot_items', 'Super Hot Items', '🔥', True, 'High-profit alchemy opportunities (>1,000 gp)'),
        ('hot_items', 'Hot Items', '🌟', True, 'Good alchemy opportunities (450-999 gp)'),
        ('welcome_channel', 'Welcome/Opt-in', '👋', False, 'Channel for user notification opt-ins'),
        ('all_alchs', 'All Alchemy Items', '🧪', False, 'All profitable alchemy items'),
        ('f2p_alchs', 'F2P Alchemy Items', '🆓', False, 'F2P-only profitable alchemy items'),
        ('crash_risk_alerts', 'Crash Risk Alerts', '📉', False, 'Market crash alerts for alchemy items'),
        ('flipping_trend_alerts', 'Flipping Trend Alerts', '📈', False, 'Flipping trend alerts'),
    ]

    @app_commands.command(
        name="setup",
        description="Configure bot channels (interactive)"
    )
    async def slash_setup(self, interaction: discord.Interaction):
        await self.start_setup_flow(interaction)

    @app_commands.command(name="status", description="Show bot status and configuration")
    async def slash_status(self, interaction: discord.Interaction):
        """Show bot status and configuration"""
        if not self.bot.channel_config:
            embed = discord.Embed(
                title="❌ Bot Not Configured",
                description="The bot hasn't been set up yet. Use `/setup` to configure it.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        config = self.bot.channel_config
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green() if self.bot.is_monitoring else discord.Color.orange()
        )

        embed.add_field(
            name="Monitoring",
            value="🟢 Active" if self.bot.is_monitoring else "🔴 Inactive",
            inline=False
        )

        # Show configured channels
        channels_text = []
        for key, name, emoji, required, desc in self.CHANNEL_TYPES:
            channel_id = getattr(config, key, None)
            if channel_id:
                ch = self.bot.get_channel(channel_id)
                if ch:
                    channels_text.append(f"{emoji} **{name}** → {ch.mention}")
                else:
                    channels_text.append(f"{emoji} **{name}** → ⚠️ Not found")

        if channels_text:
            embed.add_field(
                name="Configured Channels",
                value="\n".join(channels_text),
                inline=False
            )

        # Show subscriber count
        sub_count = len(self.bot.notification_manager.user_subscriptions)
        embed.add_field(
            name="Subscribers",
            value=f"{sub_count} user(s) receiving DM notifications",
            inline=False
        )

        # Show last update time
        if self.bot.last_update:
            embed.add_field(
                name="Last Update",
                value=self.bot.last_update.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class StartSetupView(discord.ui.View):
    """Initial setup view with Begin Setup button"""

    def __init__(self, bot, channel_types):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_types = channel_types

    @discord.ui.button(label="Begin Setup", style=discord.ButtonStyle.green, emoji="▶️")
    async def begin_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Start channel selection flow
        setup_state = {key: None for key, _, _, _, _ in self.channel_types}
        view = ChannelSelectionView(self.bot, self.channel_types, setup_state, 0)
        await view.show_current_step(interaction)


class ReconfigureView(discord.ui.View):
    """View for already-configured users to reconfigure or cancel"""

    def __init__(self, bot, channel_types):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_types = channel_types

    @discord.ui.button(label="Reconfigure", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def reconfigure(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Load existing config into setup state
        config = self.bot.channel_config
        setup_state = {}
        for key, _, _, _, _ in self.channel_types:
            channel_id = getattr(config, key, None)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                setup_state[key] = channel
            else:
                setup_state[key] = None

        # Start at first step
        view = ChannelSelectionView(self.bot, self.channel_types, setup_state, 0)
        await view.show_current_step(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ Setup Cancelled",
            description="Your existing configuration is unchanged.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ChannelSelectionView(discord.ui.View):
    """Sequential channel selection view"""

    def __init__(self, bot, channel_types, setup_state: Dict, current_index: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_types = channel_types
        self.setup_state = setup_state
        self.current_index = current_index

        # Add channel select
        key, name, emoji, required, desc = channel_types[current_index]
        select = discord.ui.ChannelSelect(
            placeholder=f"Select {name} channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        select.callback = self.channel_selected
        self.add_item(select)

        # Add Skip button for optional channels
        if not required:
            skip_button = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
            skip_button.callback = self.skip_channel
            self.add_item(skip_button)

    async def show_current_step(self, interaction: discord.Interaction):
        """Display the current channel selection step"""
        key, name, emoji, required, desc = self.channel_types[self.current_index]

        # Build progress indicator
        progress = f"Step {self.current_index + 1} of {len(self.channel_types)}"

        # Show what's been configured so far
        configured_lines = []
        for i in range(self.current_index):
            prev_key, prev_name, prev_emoji, _, _ = self.channel_types[i]
            channel = self.setup_state.get(prev_key)
            if channel:
                configured_lines.append(f"{prev_emoji} {prev_name}: {channel.mention}")
            else:
                configured_lines.append(f"{prev_emoji} {prev_name}: *(skipped)*")

        embed = discord.Embed(
            title=f"{emoji} Select {name}",
            description=(
                f"{desc}\n\n"
                f"**{'Required' if required else 'Optional'}** • {progress}"
            ),
            color=discord.Color.blue()
        )

        if configured_lines:
            embed.add_field(
                name="✅ Configured So Far",
                value="\n".join(configured_lines),
                inline=False
            )

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def channel_selected(self, interaction: discord.Interaction):
        """Handle channel selection"""
        selected_channel = interaction.data['values'][0]
        channel = self.bot.get_channel(int(selected_channel))

        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found. Please try again.",
                ephemeral=True
            )
            return

        # Store selection
        key, name, emoji, required, desc = self.channel_types[self.current_index]
        self.setup_state[key] = channel

        # Move to next step or finish
        await self.advance_to_next(interaction)

    async def skip_channel(self, interaction: discord.Interaction):
        """Handle skipping optional channel"""
        key, name, emoji, required, desc = self.channel_types[self.current_index]
        self.setup_state[key] = None
        await self.advance_to_next(interaction)

    async def advance_to_next(self, interaction: discord.Interaction):
        """Move to next step or show confirmation"""
        self.current_index += 1

        if self.current_index >= len(self.channel_types):
            # All channels selected, show confirmation
            view = ConfirmationView(self.bot, self.channel_types, self.setup_state)
            await view.show_confirmation(interaction)
        else:
            # Show next channel selection
            view = ChannelSelectionView(self.bot, self.channel_types, self.setup_state, self.current_index)
            await view.show_current_step(interaction)


class ConfirmationView(discord.ui.View):
    """Final confirmation before saving configuration"""

    def __init__(self, bot, channel_types, setup_state: Dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_types = channel_types
        self.setup_state = setup_state

    async def show_confirmation(self, interaction: discord.Interaction):
        """Display configuration summary and validation results"""
        embed = discord.Embed(
            title="📋 Configuration Summary",
            description="Review your setup before saving:",
            color=discord.Color.blue()
        )

        # Show all selections
        config_lines = []
        warnings = []

        for key, name, emoji, required, desc in self.channel_types:
            channel = self.setup_state.get(key)
            if channel:
                # Validate permissions
                perms = channel.permissions_for(interaction.guild.me)
                if not perms.view_channel or not perms.send_messages or not perms.embed_links:
                    warnings.append(
                        f"⚠️ **{name}**: Missing permissions in {channel.mention}\n"
                        f"   Need: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS"
                    )
                config_lines.append(f"{emoji} **{name}** → {channel.mention}")
            elif required:
                config_lines.append(f"{emoji} **{name}** → ❌ **REQUIRED - NOT SET**")
            else:
                config_lines.append(f"{emoji} **{name}** → *(not configured)*")

        embed.add_field(name="Selected Channels", value="\n".join(config_lines), inline=False)

        if warnings:
            embed.add_field(
                name="⚠️ Permission Warnings",
                value="\n\n".join(warnings),
                inline=False
            )
            embed.color = discord.Color.orange()

        # Check if required channels are set
        required_missing = []
        for key, name, emoji, required, desc in self.channel_types:
            if required and not self.setup_state.get(key):
                required_missing.append(name)

        if required_missing:
            embed.add_field(
                name="❌ Cannot Save",
                value=f"Missing required channels: {', '.join(required_missing)}",
                inline=False
            )
            embed.color = discord.Color.red()

            # Only show Back button
            back_button = discord.ui.Button(label="Go Back", style=discord.ButtonStyle.secondary)
            back_button.callback = self.go_back
            view = discord.ui.View(timeout=300)
            view.add_item(back_button)

            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=view)
            else:
                await interaction.response.edit_message(embed=embed, view=view)
            return

        # Show confirm/cancel buttons
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Confirm & Save", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save configuration and start monitoring"""

        # Create ChannelConfig
        config = ChannelConfig(
            super_hot_items=self.setup_state['super_hot_items'].id if self.setup_state.get('super_hot_items') else None,
            hot_items=self.setup_state['hot_items'].id if self.setup_state.get('hot_items') else None,
            welcome_channel=self.setup_state['welcome_channel'].id if self.setup_state.get('welcome_channel') else None,
            all_alchs=self.setup_state['all_alchs'].id if self.setup_state.get('all_alchs') else None,
            f2p_alchs=self.setup_state['f2p_alchs'].id if self.setup_state.get('f2p_alchs') else None,
            crash_risk_alerts=self.setup_state['crash_risk_alerts'].id if self.setup_state.get('crash_risk_alerts') else None,
            flipping_trend_alerts=self.setup_state['flipping_trend_alerts'].id if self.setup_state.get('flipping_trend_alerts') else None,
        )

        # Save to bot and file
        self.bot.channel_config = config
        success = self.bot.config_manager.save_config(config)

        if not success:
            embed = discord.Embed(
                title="❌ Save Failed",
                description="Could not save configuration. Please try again or contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        # Start monitoring
        await self.bot.start_monitoring()

        # Show success message
        embed = discord.Embed(
            title="✅ Setup Complete!",
            description=(
                "Your bot is now configured and monitoring has started.\n\n"
                "Users can manage notification preferences using `/notifications`"
            ),
            color=discord.Color.green()
        )

        # Add test button
        view = TestConfigView(self.bot, self.setup_state)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="No changes were saved.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def go_back(self, interaction: discord.Interaction):
        """Go back to channel selection"""
        # Start from first step
        view = ChannelSelectionView(self.bot, self.channel_types, self.setup_state, 0)
        await view.show_current_step(interaction)


class TestConfigView(discord.ui.View):
    """View for testing configuration after setup"""

    def __init__(self, bot, setup_state: Dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.setup_state = setup_state

    @discord.ui.button(label="Send Test Messages", style=discord.ButtonStyle.primary, emoji="🧪")
    async def test_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send test messages to all configured channels"""

        await interaction.response.defer(ephemeral=True, thinking=True)

        results = []

        # Test each configured channel
        for key, value in self.setup_state.items():
            if value:  # Channel is configured
                channel = value
                try:
                    # Send simple test message
                    test_embed = discord.Embed(
                        title="🧪 Test Message",
                        description=f"This is a test message from the OSRS Alchemy Bot.\nChannel type: **{key.replace('_', ' ').title()}**",
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=test_embed)
                    results.append(f"✅ {channel.mention} - Success")
                except discord.Forbidden:
                    results.append(f"❌ {channel.mention} - No permissions")
                except Exception as e:
                    results.append(f"❌ {channel.mention} - Error: {str(e)[:50]}")

        # Show results
        embed = discord.Embed(
            title="🧪 Test Results",
            description="\n".join(results),
            color=discord.Color.green() if all("✅" in r for r in results) else discord.Color.orange()
        )

        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            embed=embed,
            view=None
        )

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ All Set!",
            description="Your bot is ready. Use `/status` to check configuration anytime.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    """Load the SetupCog"""
    await bot.add_cog(SetupCog(bot))
