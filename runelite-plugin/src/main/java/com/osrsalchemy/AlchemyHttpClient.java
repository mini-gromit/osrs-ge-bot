package com.osrsalchemy;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import lombok.extern.slf4j.Slf4j;
import okhttp3.HttpUrl;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * HTTP client for communicating with Python backend.
 *
 * Fetches alchemy opportunities from the API.
 * No business logic - just data retrieval.
 */
@Slf4j
public class AlchemyHttpClient
{
	private final OkHttpClient httpClient;
	private final Gson gson;

	public AlchemyHttpClient(OkHttpClient httpClient)
	{
		this.httpClient = httpClient;
		this.gson = new Gson();
	}

	/**
	 * Fetch alchemy opportunities from backend.
	 *
	 * @param backendUrl Base URL of the backend API
	 * @return CompletableFuture with AlchemyResponse
	 */
	public CompletableFuture<AlchemyResponse> fetchAlchemyOpportunities(String backendUrl)
	{
		return CompletableFuture.supplyAsync(() ->
		{
			try
			{
				HttpUrl url = HttpUrl.parse(backendUrl + "/alchemy");
				if (url == null)
				{
					log.error("Invalid backend URL: {}", backendUrl);
					return null;
				}

				Request request = new Request.Builder()
					.url(url)
					.build();

				try (Response response = httpClient.newCall(request).execute())
				{
					if (!response.isSuccessful())
					{
						log.error("Backend returned error: {}", response.code());
						return null;
					}

					String body = response.body().string();
					Type responseType = new TypeToken<Map<String, Object>>() {}.getType();
					Map<String, Object> data = gson.fromJson(body, responseType);

					AlchemyResponse alchemyResponse = new AlchemyResponse();
					alchemyResponse.setMembers(parseOpportunities(data.get("members")));
					alchemyResponse.setF2p(parseOpportunities(data.get("f2p")));

					Object nextRefreshObj = data.get("next_refresh");
					if (nextRefreshObj instanceof Number)
					{
						alchemyResponse.setNextRefresh(((Number) nextRefreshObj).intValue());
					}

					Object timestampObj = data.get("timestamp");
					if (timestampObj instanceof Number)
					{
						alchemyResponse.setTimestamp(((Number) timestampObj).longValue());
					}

					return alchemyResponse;
				}
			}
			catch (IOException e)
			{
				log.error("Failed to fetch alchemy opportunities", e);
				return null;
			}
		});
	}

	private List<AlchemyOpportunity> parseOpportunities(Object data)
	{
		List<AlchemyOpportunity> opportunities = new ArrayList<>();

		if (data instanceof List)
		{
			List<?> list = (List<?>) data;
			for (Object item : list)
			{
				if (item instanceof Map)
				{
					@SuppressWarnings("unchecked")
					Map<String, Object> map = (Map<String, Object>) item;

					AlchemyOpportunity opp = new AlchemyOpportunity();

					Object itemIdObj = map.get("item_id");
					if (itemIdObj instanceof Number)
					{
						opp.setItemId(((Number) itemIdObj).intValue());
					}

					Object nameObj = map.get("name");
					if (nameObj instanceof String)
					{
						opp.setName((String) nameObj);
					}

					Object profitObj = map.get("profit");
					if (profitObj instanceof Number)
					{
						opp.setProfit(((Number) profitObj).intValue());
					}

					Object buyPriceObj = map.get("buy_price");
					if (buyPriceObj instanceof Number)
					{
						opp.setBuyPrice(((Number) buyPriceObj).intValue());
					}

					opportunities.add(opp);
				}
			}
		}

		return opportunities;
	}

	/**
	 * Response from /alchemy endpoint.
	 */
	@lombok.Data
	public static class AlchemyResponse
	{
		private List<AlchemyOpportunity> members;
		private List<AlchemyOpportunity> f2p;
		private int nextRefresh;
		private long timestamp;
	}
}
