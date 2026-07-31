package com.osrsalchemy;

import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayPosition;

import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Color;

/**
 * Minimal overlay to verify plugin is loading and rendering.
 */
public class AlchemyOverlay extends Overlay
{
	public AlchemyOverlay()
	{
		setPosition(OverlayPosition.TOP_LEFT);
	}

	@Override
	public Dimension render(Graphics2D graphics)
	{
		graphics.setColor(Color.YELLOW);
		graphics.drawString("GE Bot Active", 0, graphics.getFontMetrics().getHeight());
		return null;
	}
}
