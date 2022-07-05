from gql import gql

from hummingbot.connector.exchange.polkadex.graphql.auth.client import execute_query_command


async def get_klines_by_market_and_interval(market, interval, from_date, to_date):
    query = gql(
        """
query getKlinesbyMarketInterval($from: AWSDateTime!, $interval: String!, $market: String!, $to: AWSDateTime!) {
  getKlinesbyMarketInterval(from: $from, interval: $interval, market: $market, to: $to) {
    items {
      c
      h
      interval
      l
      m
      o
      t
      v_base
      v_quote
    }
  }
}
""")
    variables = {"from": from_date.isoformat(timespec="seconds") + "Z",
                 "to": to_date.isoformat(timespec="seconds") + "Z",
                 "market": market,
                 "interval":interval}

    result = await execute_query_command(query, variables)
    return result["getKlinesbyMarketInterval"]