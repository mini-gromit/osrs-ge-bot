package com.osrsalchemy;

import lombok.extern.slf4j.Slf4j;
import net.runelite.client.game.ItemManager;
import net.runelite.client.ui.ColorScheme;
import net.runelite.client.ui.PluginPanel;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import java.awt.*;
import java.awt.datatransfer.StringSelection;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Sidebar panel for alchemy opportunities.
 *
 * Displays members/F2P tabs with top 5 items.
 * Click to copy buy price.
 *
 * Renders presentation models only - no formatting.
 */
@Slf4j
public class AlchemyPanel extends PluginPanel
{
	private final ItemManager itemManager;
	private final JTabbedPane tabbedPane;
	private final JPanel membersPanel;
	private final JPanel f2pPanel;
	private final JLabel refreshTimerLabel;

	private int backendRefreshSeconds = 0;

	public AlchemyPanel(ItemManager itemManager)
	{
		super(false);
		this.itemManager = itemManager;

		setLayout(new BorderLayout());
		setBackground(ColorScheme.DARK_GRAY_COLOR);

		// Header
		JPanel header = new JPanel(new BorderLayout());
		header.setBackground(ColorScheme.DARKER_GRAY_COLOR);
		header.setBorder(new EmptyBorder(10, 10, 10, 10));

		JLabel title = new JLabel("Alchemy");
		title.setForeground(Color.WHITE);
		title.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 16));
		header.add(title, BorderLayout.WEST);

		refreshTimerLabel = new JLabel("Refresh --:--");
		refreshTimerLabel.setForeground(Color.LIGHT_GRAY);
		refreshTimerLabel.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 12));
		header.add(refreshTimerLabel, BorderLayout.EAST);

		add(header, BorderLayout.NORTH);

		// Tabs
		tabbedPane = new JTabbedPane();
		tabbedPane.setBackground(ColorScheme.DARK_GRAY_COLOR);

		membersPanel = new JPanel();
		membersPanel.setLayout(new BoxLayout(membersPanel, BoxLayout.Y_AXIS));
		membersPanel.setBackground(ColorScheme.DARK_GRAY_COLOR);

		f2pPanel = new JPanel();
		f2pPanel.setLayout(new BoxLayout(f2pPanel, BoxLayout.Y_AXIS));
		f2pPanel.setBackground(ColorScheme.DARK_GRAY_COLOR);

		JScrollPane membersScroll = new JScrollPane(membersPanel);
		membersScroll.setBackground(ColorScheme.DARK_GRAY_COLOR);
		membersScroll.setBorder(null);

		JScrollPane f2pScroll = new JScrollPane(f2pPanel);
		f2pScroll.setBackground(ColorScheme.DARK_GRAY_COLOR);
		f2pScroll.setBorder(null);

		tabbedPane.addTab("Members", membersScroll);
		tabbedPane.addTab("F2P", f2pScroll);

		add(tabbedPane, BorderLayout.CENTER);
	}

	/**
	 * Update panel with new data.
	 *
	 * Converts network models to presentation models.
	 * Panel renders formatted strings from presentation models.
	 *
	 * @param members Members opportunities from API
	 * @param f2p F2P opportunities from API
	 * @param backendRefreshSeconds Seconds until backend refreshes data
	 */
	public void updateData(List<AlchemyOpportunity> members, List<AlchemyOpportunity> f2p, int backendRefreshSeconds)
	{
		// Convert to presentation models
		List<AlchemyRowModel> membersRows = members.stream()
			.map(AlchemyRowModel::fromOpportunity)
			.collect(Collectors.toList());

		List<AlchemyRowModel> f2pRows = f2p.stream()
			.map(AlchemyRowModel::fromOpportunity)
			.collect(Collectors.toList());

		// Update backend countdown
		this.backendRefreshSeconds = backendRefreshSeconds;
		updateRefreshTimer();

		// Update UI
		SwingUtilities.invokeLater(() ->
		{
			membersPanel.removeAll();
			f2pPanel.removeAll();

			populatePanel(membersPanel, membersRows);
			populatePanel(f2pPanel, f2pRows);

			membersPanel.revalidate();
			membersPanel.repaint();
			f2pPanel.revalidate();
			f2pPanel.repaint();
		});
	}

	/**
	 * Update refresh timer countdown.
	 *
	 * Uses formatted string from presentation model.
	 */
	public void updateRefreshTimer()
	{
		SwingUtilities.invokeLater(() ->
		{
			String timerText = AlchemyRowModel.formatRefreshTimer(backendRefreshSeconds);
			refreshTimerLabel.setText(timerText);
		});
	}

	/**
	 * Decrement backend refresh countdown.
	 *
	 * Called every second by plugin scheduler.
	 * Represents backend refresh time, not plugin poll time.
	 */
	public void decrementTimer()
	{
		if (backendRefreshSeconds > 0)
		{
			backendRefreshSeconds--;
			updateRefreshTimer();
		}
	}

	/**
	 * Populate panel with item rows.
	 *
	 * Renders presentation models only.
	 */
	private void populatePanel(JPanel panel, List<AlchemyRowModel> rows)
	{
		if (rows == null || rows.isEmpty())
		{
			JLabel noDataLabel = new JLabel("No data available");
			noDataLabel.setForeground(Color.LIGHT_GRAY);
			noDataLabel.setBorder(new EmptyBorder(10, 10, 10, 10));
			panel.add(noDataLabel);
			return;
		}

		for (AlchemyRowModel row : rows)
		{
			JPanel itemRow = createItemRow(row);
			panel.add(itemRow);
		}
	}

	/**
	 * Create a single item row.
	 *
	 * Renders formatted strings from presentation model.
	 * No formatting logic here - panel is render-only.
	 */
	private JPanel createItemRow(AlchemyRowModel model)
	{
		JPanel row = new JPanel(new BorderLayout(8, 0));
		row.setBackground(ColorScheme.DARKER_GRAY_COLOR);
		row.setBorder(BorderFactory.createCompoundBorder(
			BorderFactory.createMatteBorder(0, 0, 1, 0, ColorScheme.DARK_GRAY_COLOR),
			new EmptyBorder(8, 8, 8, 8)
		));
		row.setCursor(new Cursor(Cursor.HAND_CURSOR));

		// Item icon
		JLabel iconLabel = new JLabel();
		itemManager.getImage(model.getItemId()).addTo(iconLabel);
		row.add(iconLabel, BorderLayout.WEST);

		// Item details
		JPanel detailsPanel = new JPanel();
		detailsPanel.setLayout(new BoxLayout(detailsPanel, BoxLayout.Y_AXIS));
		detailsPanel.setBackground(ColorScheme.DARKER_GRAY_COLOR);

		// Name (from presentation model)
		JLabel nameLabel = new JLabel(model.getName());
		nameLabel.setForeground(Color.WHITE);
		nameLabel.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 12));
		detailsPanel.add(nameLabel);

		// Profit (already formatted)
		JLabel profitLabel = new JLabel(model.getProfitDisplay());
		profitLabel.setForeground(new Color(0, 200, 0));
		profitLabel.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 11));
		detailsPanel.add(profitLabel);

		// Buy price (already formatted)
		JLabel buyPriceLabel = new JLabel(model.getBuyPriceDisplay());
		buyPriceLabel.setForeground(Color.LIGHT_GRAY);
		buyPriceLabel.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 11));
		detailsPanel.add(buyPriceLabel);

		row.add(detailsPanel, BorderLayout.CENTER);

		// Click to copy (uses raw value for clipboard)
		row.addMouseListener(new MouseAdapter()
		{
			@Override
			public void mouseClicked(MouseEvent e)
			{
				copyBuyPrice(row, model.getRawBuyPrice());
			}

			@Override
			public void mouseEntered(MouseEvent e)
			{
				row.setBackground(ColorScheme.DARKER_GRAY_HOVER_COLOR);
				detailsPanel.setBackground(ColorScheme.DARKER_GRAY_HOVER_COLOR);
			}

			@Override
			public void mouseExited(MouseEvent e)
			{
				row.setBackground(ColorScheme.DARKER_GRAY_COLOR);
				detailsPanel.setBackground(ColorScheme.DARKER_GRAY_COLOR);
			}
		});

		return row;
	}

	/**
	 * Copy buy price to clipboard and show confirmation.
	 */
	private void copyBuyPrice(JPanel row, int buyPrice)
	{
		// Copy to clipboard (no commas)
		String priceStr = String.valueOf(buyPrice);
		Toolkit.getDefaultToolkit()
			.getSystemClipboard()
			.setContents(new StringSelection(priceStr), null);

		// Show checkmark briefly
		Color originalColor = row.getBackground();
		row.setBackground(new Color(0, 100, 0));

		Timer timer = new Timer(1000, e ->
		{
			row.setBackground(originalColor);
		});
		timer.setRepeats(false);
		timer.start();

		log.debug("Copied buy price to clipboard: {}", buyPrice);
	}

	/**
	 * Set default tab.
	 */
	public void setDefaultTab(AlchemyPluginConfig.AlchemyTab tab)
	{
		SwingUtilities.invokeLater(() ->
		{
			if (tab == AlchemyPluginConfig.AlchemyTab.MEMBERS)
			{
				tabbedPane.setSelectedIndex(0);
			}
			else
			{
				tabbedPane.setSelectedIndex(1);
			}
		});
	}
}
