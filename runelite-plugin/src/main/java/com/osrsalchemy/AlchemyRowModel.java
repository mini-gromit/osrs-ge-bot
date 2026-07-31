package com.osrsalchemy;

import lombok.Value;

import java.text.NumberFormat;
import java.util.Locale;

/**
 * Presentation model for alchemy opportunity rows.
 *
 * Handles all formatting and display string generation.
 * The panel simply renders these formatted values.
 *
 * Separation:
 * - AlchemyOpportunity = network/data model (raw values)
 * - AlchemyRowModel = presentation model (formatted strings)
 * - AlchemyPanel = view (rendering only)
 */
@Value
public class AlchemyRowModel
{
	private static final NumberFormat GP_FORMAT = NumberFormat.getNumberInstance(Locale.US);

	int itemId;
	String name;
	String profitDisplay;      // e.g., "+1,002 gp"
	String buyPriceDisplay;    // e.g., "Buy 160,998"
	int rawBuyPrice;           // Raw value for clipboard (no commas)

	/**
	 * Create presentation model from data model.
	 *
	 * All formatting happens here.
	 * Panel receives ready-to-display strings.
	 */
	public static AlchemyRowModel fromOpportunity(AlchemyOpportunity opportunity)
	{
		String profitDisplay = String.format("+%s gp", GP_FORMAT.format(opportunity.getProfit()));
		String buyPriceDisplay = String.format("Buy %s", GP_FORMAT.format(opportunity.getBuyPrice()));

		return new AlchemyRowModel(
			opportunity.getItemId(),
			opportunity.getName(),
			profitDisplay,
			buyPriceDisplay,
			opportunity.getBuyPrice()
		);
	}

	/**
	 * Format countdown timer.
	 *
	 * @param seconds Seconds remaining
	 * @return Formatted string (e.g., "Refresh 00:42")
	 */
	public static String formatRefreshTimer(int seconds)
	{
		int minutes = seconds / 60;
		int secs = seconds % 60;
		return String.format("Refresh %02d:%02d", minutes, secs);
	}
}
