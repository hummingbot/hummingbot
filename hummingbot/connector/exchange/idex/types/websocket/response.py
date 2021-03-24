# import typing
#
# from dataclasses import dataclass
# from ..enums import CandleInterval, OrderSide, OrderTimeInForce, \
#     OrderSelfTradePrevention, OrderStateChange, OrderStatus, OrderType, Liquidity, EthTransactionStatus
# from .request import WebSocketRequestSubscription
#
#
# @dataclass
# class WebSocketResponseTickerShort:
#     """
#     string m - (market) Market symbol
#     number t - (time) Timestamp when the statistics were computed, the opening time of the period is 24 hours prior
#     string o - (open) Price of the first trade in the period in quote terms
#     string h - (high) Highest traded price in the period in quote terms
#     string l - (low) Lowest traded price in the period in quote terms
#     string c - (close) Price of the last trade in the period in quote terms
#     string Q - (closeQuantity) Quantity of the last trade in th period in base terms
#     string v - (baseVolume) Trailing 24-hour trading volume in base terms
#     string q - (quoteVolume) Trailing 24-hour trading volume in quote terms
#     string P - (percentChange) Percentage change from open price to close price
#     number n - (numTrades) Number of trades in the period
#     string a - (ask) Best ask price on the order book in quote terms
#     string b - (bid) Best bid price on the order book in quote terms
#     number u - (sequence) Fill sequence number of the last trade in the period
#     """
#
#     m: str
#     t: float
#     o: str
#     h: str
#     l: str
#     c: str
#     Q: str
#     v: str
#     q: str
#     P: str
#     n: int
#     a: str
#     b: str
#     u: int
#
#
# @dataclass
# class WebSocketResponseCandleShort:
#     """
#     string m - (market) Market symbol
#     number t - (time) Timestamp when the statistics were computed, time is always between the start and end timestamps of the interval
#     string i - (interval) Interval duration, see Interval Values
#     number s - (start) Timestamp of the start of the interval
#     number e - (end) Timestamp of the end of the interval
#     string o - (open) Price of the first trade in the interval in quote terms
#     string h - (high) Highest traded price in the interval in quote terms
#     string l - (low) Lowest traded price in the interval in quote terms
#     string c - (close) Price of the last trade in the interval in quote terms
#     string v - (volume) Trading volume in the interval in base terms
#     number n - (numTrades) Number of trades in the candle
#     number u - (sequence) Fill sequence number of the last trade in the interval
#     """
#     m: str
#     t: float
#     i: CandleInterval
#     s: float
#     e: float
#     o: str
#     h: str
#     l: str
#     c: str
#     v: str
#     n: int
#     u: int
#
#
# @dataclass
# class WebSocketResponseTradeShort:
#     """
#     string m - (market) Market symbol
#     string i - (fillId) Trade identifier
#     string p - (price) Price of the trade in quote terms
#     string q - (quantity) Quantity of the trade in base terms
#     string Q - (quoteQuantity) Quantity of the trade in quote terms
#     number t - (time) Timestamp of the trade
#     string s - (makerSide) Maker side of the trade, buy or sell
#     number u - (sequence) Fill sequence number of the trade
#     """
#     m: str
#     i: str
#     p: str
#     q: str
#     Q: str
#     t: float
#     s: OrderSide
#     u: int
#
#
# @dataclass
# class WebSocketResponseL1OrderBookShort:
#     """
#     string m - (market) Market symbol
#     number t - (time) Timestamp of the order book update
#     string b - (bidPrice) Best bid price
#     string B - (bidQuantity) Quantity available at the best bid price
#     string a - (askPrice) Best ask price
#     string A - (askQuantity) Quantity available at the best ask price
#     """
#     m: str
#     t: float
#     b: str
#     B: str
#     a: str
#     A: str
#
#
# @dataclass
# class WebSocketResponseL2OrderBookShort:
#     """
#     string m - (market) Market symbol
#     number t - (time) Timestamp of the order book update
#     number u - (sequence) Order book update sequence number of the update
#     WebSocketResponseL2OrderBookChange b - (bids) Array of bid price level updates
#     WebSocketResponseL2OrderBookChange a - (asks) Array of ask price level updates
#     """
#     m: str
#     t: float
#     u: int
#     b: typing.List[typing.List]
#     a: typing.List[typing.List]
#
#
# @dataclass
# class WebSocketResponseL2OrderBookLong:
#     """
#     string m - (market) Market symbol
#     number t - (time) Timestamp of the order book update
#     number u - (sequence) Order book update sequence number of the update
#     WebSocketResponseL2OrderBookChange b - (bids) Array of bid price level updates
#     WebSocketResponseL2OrderBookChange a - (asks) Array of ask price level updates
#     """
#     market: str
#     time: float
#     sequence: int
#     bids: typing.List[typing.List]
#     asks: typing.List[typing.List]
#
#
# @dataclass
# class WebSocketResponseBalanceShort:
#     """
#     string w - (wallet) Target wallet address
#     string a - (asset) Asset symbol
#     string q - (quantity) Total quantity of the asset held by the wallet on the exchange
#     string f - (availableForTrade) Quantity of the asset available for trading; quantity - locked
#     string l - (locked) Quantity of the asset held in trades on the order book
#     string d - (usdValue) Total value of the asset held by the wallet on the exchange in USD
#     """
#     w: str
#     a: str
#     q: str
#     f: str
#     l: str
#     d: str
#
#
# @dataclass
# class WebSocketResponseOrderFillShort:
#     """
#     string i - (fillId) Fill identifier
#     string p - (price) Price of the fill in quote terms
#     string q - (quantity) Quantity of the fill in base terms
#     string Q - (quoteQuantity) Quantity of the fill in quote terms
#     number t - (time) Timestamp of the fill
#     string s - (makerSide) Maker side of the fill, buy or sell
#     string u - (sequence) Fill sequence number
#     string f - (fee) Fee amount collected on the fill
#     string a - (feeAsset) Symbol of asset in which fees collected
#     string [g] - (gas) Amount collected to cover trade settlement gas costs, only present for taker
#     string l - (liquidity) Whether the fill is the maker or taker in the trade from the perspective of the requesting user account, maker or taker
#     string T - (txId) Ethereum id of the trade settlement transaction
#     string S - (txStatus) Status of the trade settlement transaction, see values
#     """
#     i: str
#     p: str
#     q: str
#     Q: str
#     t: float
#     s: OrderSide
#     u: int
#     f: str
#     a: str
#     l: Liquidity
#     S: EthTransactionStatus
#     g: typing.Optional[str] = None
#     T: typing.Optional[str] = None
#
#
# @dataclass
# class WebSocketResponseOrderShort:
#     """
# string m - (market) Market symbol
# string i - (orderId) Exchange-assigned order identifier
# string [c] - (clientOrderId) Client-specified order identifier
# string w  - (wallet) Ethereum address of placing wallet
# string t - (executionTime) Timestamp of the most recent update
# number T - (time) Timestamp of initial order processing by the matching engine
# string x - (update) Type of order update, see values
# string X - (status) Order status, see values
# number [u] - (sequence) order book update sequence number, only included if update type triggers an order book update
# string o - (type) Order type, see values
# string S - (side) Order side, buy or sell
# string [q] - (originalQuantity) Original quantity specified by the order in base terms, omitted for market orders specified in quote terms
# string [Q] - (originalQuoteQuantity) Original quantity specified by the order in quote terms, only present for market orders specified in quote terms
# string z - (executedQuantity) Quantity that has been executed in base terms
# string [Z] - (cumulativeQuoteQuantity) Cumulative quantity that has been spent (buy orders) or received (sell orders) in quote terms, omitted if unavailable for historical orders
# string [v] - (avgExecutionPrice) Weighted average price of fills associated with the order; only present with fills
# string [p] - (price) Original price specified by the order in quote terms, omitted for all market orders
# string [P] - (stopPrice) Stop loss or take profit price, only present for stopLoss, stopLossLimit, takeProfit, and takeProfitLimit orders
# string [f] - (timeInForce) Time in force policy, see values, only present for all limit orders specifying a non-default (gtc) policy
# string [V] - (selfTradePrevention) Self-trade prevention policy, see values, only present for orders specifying a non-default (dc) policy
# WebSocketResponseOrderFillShort] [F] - (fills) Array of order fill objects
#     """
#     m: str
#     i: str
#     w: str
#     t: float
#     T: float
#     x: OrderStateChange
#     X: OrderStatus
#     o: OrderType
#     S: OrderSide
#     z: str
#     c: typing.Optional[str] = None
#     u: typing.Optional[int] = None
#     q: typing.Optional[str] = None
#     Q: typing.Optional[str] = None
#     Z: typing.Optional[str] = None
#     v: typing.Optional[str] = None
#     p: typing.Optional[str] = None
#     P: typing.Optional[str] = None
#     f: typing.Optional[OrderTimeInForce] = None
#     V: typing.Optional[OrderSelfTradePrevention] = None
#     F: typing.Optional[typing.List[WebSocketResponseOrderFillShort]] = None
#
#
# @dataclass
# class WebSocketResponseErrorData:
#     code: str
#     message: str
#
#
# @dataclass
# class WebSocketResponseError:
#     """
#     string [cid]
#     string type - error
#     Object data
#     string data.code - error short code
#     string data.message - human readable error message
#     """
#     type: typing.Literal["error"]
#     data: WebSocketResponseErrorData
#     cid: typing.Optional[str] = None
#
#
# @dataclass
# class WebSocketResponseSubscriptions:
#     """
#     string [cid]
#     string method - subscriptions
#     WebSocketRequestSubscription subscriptions
#     string Subscription.name - subscription name
#     string Subscription.markets - markets
#     string [Subscription.interval] - candle interval
#     string [Subscription.wallet] - wallet address
#     """
#     type: typing.Literal['subscriptions']
#     subscriptions: typing.List[WebSocketRequestSubscription]
#     cid: typing.Optional[str] = None
