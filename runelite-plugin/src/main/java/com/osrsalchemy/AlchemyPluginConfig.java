package com.osrsalchemy;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

/**
 * Configuration for the Alchemy plugin.
 */
@ConfigGroup("alchemy")
public interface AlchemyPluginConfig extends Config
{
	@ConfigItem(
		keyName = "backendUrl",
		name = "Backend URL",
		description = "URL of the Python backend API",
		position = 1
	)
	default String backendUrl()
	{
		return "http://localhost:5000";
	}

	@ConfigItem(
		keyName = "autoRefresh",
		name = "Auto Refresh",
		description = "Automatically refresh data from backend",
		position = 2
	)
	default boolean autoRefresh()
	{
		return true;
	}

	@ConfigItem(
		keyName = "refreshInterval",
		name = "Refresh Interval",
		description = "How often to refresh (seconds)",
		position = 3
	)
	default int refreshInterval()
	{
		return 60;
	}

	@ConfigItem(
		keyName = "defaultTab",
		name = "Default Tab",
		description = "Which tab to show by default",
		position = 4
	)
	default AlchemyTab defaultTab()
	{
		return AlchemyTab.MEMBERS;
	}

	enum AlchemyTab
	{
		MEMBERS,
		F2P
	}
}
