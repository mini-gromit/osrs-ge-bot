package com.osrsalchemy;

import com.google.inject.Provides;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.game.ItemManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.task.Schedule;
import net.runelite.client.ui.ClientToolbar;
import net.runelite.client.ui.NavigationButton;
import net.runelite.client.ui.overlay.OverlayManager;
import net.runelite.client.util.ImageUtil;
import okhttp3.OkHttpClient;

import javax.inject.Inject;
import java.awt.image.BufferedImage;
import java.time.temporal.ChronoUnit;

/**
 * OSRS Alchemy Plugin for RuneLite.
 *
 * Displays profitable high alchemy opportunities from Python backend.
 * All calculations done server-side - plugin only displays results.
 *
 * Phase 1: Alchemy only (no flipping, no charts, no overlays)
 */
@Slf4j
@PluginDescriptor(
	name = "OSRS Alchemy",
	description = "Displays profitable high alchemy opportunities",
	tags = {"alchemy", "high alch", "profit", "money making"}
)
public class AlchemyPlugin extends Plugin
{
	@Inject
	private Client client;

	@Inject
	private ClientToolbar clientToolbar;

	@Inject
	private ItemManager itemManager;

	@Inject
	private OkHttpClient okHttpClient;

	@Inject
	private AlchemyPluginConfig config;

	@Inject
	private OverlayManager overlayManager;

	@Inject
	private AlchemyOverlay overlay;

	private AlchemyPanel panel;
	private NavigationButton navButton;
	private AlchemyHttpClient httpClient;

	@Override
	protected void startUp() throws Exception
	{
		log.info("OSRS Alchemy plugin started");

		overlayManager.add(overlay);

		httpClient = new AlchemyHttpClient(okHttpClient);

		// Create panel and navigation button (optional if icon resource exists)
		try
		{
			panel = new AlchemyPanel(itemManager);
			panel.setDefaultTab(config.defaultTab());

			final BufferedImage icon = ImageUtil.loadImageResource(getClass(), "/alchemy_icon.png");
			navButton = NavigationButton.builder()
				.tooltip("Alchemy")
				.icon(icon)
				.priority(5)
				.panel(panel)
				.build();

			clientToolbar.addNavigation(navButton);

			// Initial poll for cached data
			if (config.autoRefresh())
			{
				fetchCachedData();
			}
		}
		catch (Exception e)
		{
			log.warn("Could not load sidebar icon, panel will not be available: {}", e.getMessage());
		}
	}

	@Override
	protected void shutDown() throws Exception
	{
		log.info("OSRS Alchemy plugin stopped");
		overlayManager.remove(overlay);
		if (navButton != null)
		{
			clientToolbar.removeNavigation(navButton);
		}
	}

	@Provides
	AlchemyPluginConfig provideConfig(ConfigManager configManager)
	{
		return configManager.getConfig(AlchemyPluginConfig.class);
	}

	/**
	 * Periodic task runs every second.
	 *
	 * Responsibilities:
	 * - Update countdown timer (every 1s)
	 * - Poll backend for cached data (every 10s)
	 *
	 * The countdown shows backend refresh time, not plugin poll time.
	 * Polling does not trigger backend refresh - backend refreshes on its own schedule.
	 */
	private int pollCounter = 0;
	private static final int POLL_INTERVAL_SECONDS = 10;

	@Schedule(
		period = 1,
		unit = ChronoUnit.SECONDS,
		asynchronous = true
	)
	public void scheduledTask()
	{
		// Update countdown timer every second
		if (panel != null)
		{
			panel.decrementTimer();
		}

		// Poll backend every 10 seconds if auto-refresh enabled
		if (config.autoRefresh())
		{
			pollCounter++;
			if (pollCounter >= POLL_INTERVAL_SECONDS)
			{
				pollCounter = 0;
				fetchCachedData();
			}
		}
	}

	/**
	 * Fetch cached data from backend.
	 *
	 * Polls backend for latest cached opportunities.
	 * Does not trigger backend refresh - backend refreshes on its own schedule.
	 */
	private void fetchCachedData()
	{
		String backendUrl = config.backendUrl();

		httpClient.fetchAlchemyOpportunities(backendUrl).thenAccept(response ->
		{
			if (response == null)
			{
				log.error("Failed to fetch cached alchemy data");
				return;
			}

			log.debug("Polled cached data: {} members, {} F2P items, next refresh in {}s",
				response.getMembers().size(),
				response.getF2p().size(),
				response.getNextRefresh());

			if (panel != null)
			{
				panel.updateData(
					response.getMembers(),
					response.getF2p(),
					response.getNextRefresh()
				);
			}
		}).exceptionally(ex ->
		{
			log.error("Error polling cached data", ex);
			return null;
		});
	}
}
