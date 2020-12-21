import typing


WEBSOCKET_AUTHENTICATED_SUBSCRIPTIONS = typing.Literal[
  'balances',
  'orders'
]


WEBSOCKET_UNAUTHENTICATED_SUBSCRIPTIONS = typing.Literal[
  'candles',
  'l1orderbook',
  'l2orderbook',
  'tickers',
  'trades'
]
