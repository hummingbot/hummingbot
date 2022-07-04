from gql import gql
from auth.client import execute_query_command


async def get_recent_trades(market, limit, next_token):
    query = gql(
        """
query getRecentTrades($market: String!, $limit: Int, $nextToken: String) {
  getRecentTrades(m: $market, limit: $limit, nextToken: $nextToken) {
    nextToken
    items {
      p
      q
      t
    }
  }
}
""")

    variables = {"market": market}

    if limit is not None:
        variables["limit"] = limit
    if next_token is not None:
        variables["nextToken"] = next_token

    result = await execute_query_command(query, variables)
    return result["getRecentTrades"]


async def get_orderbook(market, limit, next_token):
    query = gql(
        """
query getOrderbook($market: String!, $limit: Int, $nextToken: String) {
  getOrderbook(market: $market, limit: $limit, nextToken: $nextToken) {
    nextToken
    items {
      price
      qty
      side
    }
  }
}
""")

    variables = {"market": market}

    if limit is not None:
        variables["limit"] = limit
    if next_token is not None:
        variables["nextToken"] = next_token

    result = await execute_query_command(query, variables)
    return result["getOrderbook"]


async def get_all_market_tickers():
    query = gql(
        """
query getAllMarketTickers {
  getAllMarketTickers {
    items {
      close
      high
      low
      m
      open
      priceChange24Hr
      priceChangePercent24Hr
      volumeBase24hr
      volumeQuote24Hr
    }
    nextToken
  }
}
""")

    variables = {}

    result = await execute_query_command(query, variables)
    return result["getAllMarketTickers"]


async def get_all_assets(limit, next_token):
    query = gql(
        """
query getAllAssets($nextToken: String, $limit: Int) {
  getAllAssets(nextToken: $nextToken, limit: $limit) {
    items {
      ticker
      withdrawal_fee
    }
  }
}
""")

    variables = {}
    if limit is not None:
        variables["limit"] = limit
    if next_token is not None:
        variables["nextToken"] = next_token

    result = await execute_query_command(query, variables)
    return result["getAllAssets"]
