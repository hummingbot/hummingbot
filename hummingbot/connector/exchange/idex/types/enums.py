# import typing
#
#
# __all__ = [
#     "CandleInterval",
#     "EthTransactionStatus",
#     "Liquidity",
#     "MarketStatus",
#     "OrderSelfTradePrevention",
#     "OrderSide",
#     "OrderStateChange",
#     "OrderStatus",
#     "OrderTimeInForce",
#     "OrderType",
# ]
#
#
# CandleInterval = typing.Literal[
#     "1m",
#     "5m",
#     "15m",
#     "30m",
#     "1h",
#     "6h",
#     "1d"
#     # NOTE: Other intervals are not documented in https://docs.idex.io/#api-request-amp-response-values
# ]
#
#
# EthTransactionStatus = typing.Literal[
#     "pending",
#     "mined",
#     "failed"
# ]
#
#
# Liquidity = typing.Literal[
#     "maker",
#     "taker"
# ]
#
#
# MarketStatus = typing.Literal[
#     "inactive",
#     "cancelsOnly",
#     "limitMakerOnly",
#     "active"
# ]
#
#
# OrderSelfTradePrevention = typing.Literal[
#     "dc",
#     "co",
#     "cn",
#     "cb",
# ]
#
#
# OrderSide = typing.Literal[
#     "buy",
#     "sell",
# ]
#
#
# OrderStateChange = typing.Literal[
#     "new",
#     "activated",
#     "fill",
#     "canceled",
#     "expired",
# ]
#
#
# OrderStatus = typing.Literal[
#     "active",
#     "open",
#     "partiallyFilled",
#     "filled",
#     "canceled",
#     "rejected",
#     "expired",
#     "testOnlyAccepted",
#     "testOnlyRejected",
# ]
#
#
# OrderTimeInForce = typing.Literal[
#     "gtc",
#     "gtt",
#     "ioc",
#     "fok",
# ]
#
#
# OrderType = typing.Literal[
#     "market",
#     "limit",
#     "limitMaker",
#     "stopLoss",
#     "stopLossLimit",
#     "takeProfit",
#     "takeProfitLimit",
# ]
