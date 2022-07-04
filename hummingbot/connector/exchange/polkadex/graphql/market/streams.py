from gql import gql

from auth.client import subscribe_query_command


async def on_new_candle_stick(market, interval, callback):
    query = gql(
        """
subscription OnCandleStickEvents($interval: String!, $m: String!) {
  onCandleStickEvents(interval: $interval, m: $m) {
    c
    h
    l
    o
    t
    v_base
    v_quote
  }
}
""")
    variables = {"m": market, "interval": interval}

    await subscribe_query_command(query, variables, callback)


async def on_new_ticker(market, callback):
    query = gql(
        """
subscription OnNewTicker($m: String!) {
  onNewTicker(m: $m) {
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
}
""")
    variables = {"m": market}

    await subscribe_query_command(query, variables, callback)
