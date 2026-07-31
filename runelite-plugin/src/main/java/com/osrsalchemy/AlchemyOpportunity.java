package com.osrsalchemy;

import lombok.Data;

/**
 * Data model for alchemy opportunities.
 *
 * Received from Python backend API.
 * Contains only display information - no business logic.
 */
@Data
public class AlchemyOpportunity
{
	private int itemId;
	private String name;
	private int profit;
	private int buyPrice;
}
