# Strategies Architecture

![StrategyBase class relations](/assets/img/strategy-uml.svg)

Strategy modules in Hummingbot are modules that monitor markets and make trading decisions. All strategy classes are derived from the [`StrategyBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx) class, which is derived from the [`TimeIterator`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx) class.

The concrete strategy classes included with Hummingbot, including [`ArbitrageStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx), [`CrossExchangeMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx), and [`PureMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making_v2.pyx) - are all child classes of `StrategyBase`.

Each `StrategyBase` object may be managing multiple [`MarketBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx) and [`WalletBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/wallet/wallet_base.pyx) objects.

## How It Works

All strategy modules are child classes of [`TimeIterator`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/time_iterator.pyx), which is called via `c_tick()` every second.

What this means is, a running strategy module is called every second via its `c_tick()` method to check on the markets and wallets, and decide whether it should perform any trades or not. One way to think about it is that a strategy module acts like it's watching a movie frame-by-frame via `c_tick()`, and reacts to what it sees in real time via trading actions.

If you're reading or writing a strategy module, the `c_tick()` function should be treated as the entry point of a strategy module. If you're reading a strategy module's code, `c_tick()` should be where you start. If you're writing a new strategy module, `c_tick()` is also going to where you start writing the important bits of your strategy.

## Markets

Each `StrategyBase` object may be associated with multiple markets.

- `cdef c_add_markets(self, list markets)`

    Associates a list of `MarketBase` objects to this `StrategyBase` object.

- `cdef c_remove_markets(self, list markets)`

    Disassociates a list of `MarketBase` objects from this `StrategyBase` object.

- `active_markets` property

    List of `MarketBase` objects currently associated with this `StrategyBase` object.

## Market Event Interfaces

The `StrategyBase` class comes with a set of interface functions for handling market events from associated `MarketBase` objects, which may be overridded by child classes to receive and process market events.

The event interface functions are as follows:

- `cdef c_did_create_buy_order(self, object order_created_event)`

    A buy order has been created. Argument is a [`BuyOrderCreatedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_create_sell_order(self, object order_created_event)`

    A sell order has been created. Argument is a [`SellOrderCreatedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_fill_order(self, object order_filled_event)`

    An order has been filled in the market. Argument is a [`OrderFilledEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_fail_order(self, object order_failed_event)`

    An order has failed in the market. Argument is a [`MarketOrderFailureEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_cancel_order(self, object cancelled_event)`

    An order has been cancelled. Argument is a [`OrderCancelledEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_expire_order(self, object expired_event)`

    An order has expired. Argument is a [`OrderExpiredEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_complete_buy_order(self, object order_completed_event)`

    A buy order has been completely filled. Argument is a [`BuyOrderCompletedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_complete_sell_order(self, object order_completed_event)`

    A sell order has been completely filled. Argument is a [`SellOrderCompletedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

## Creating and Cancelling Orders

`StrategyBase` includes pre-defined logic for creating and cancelling trading orders - which are the primary ways for a strategy to interact with associated markets.

It is highly encouraged to use these functions to create and remove orders, rather than calling functions like `c_buy()` and `c_sell()` on `MarketBase` objects directly - since the functions from `StrategyBase` provides order tracking functionalities as well.

### Place order
```cython
cdef str c_buy_with_specific_market(self, 
                                    object market_trading_pair_tuple,
                                    object amount,
                                    object order_type = *,
                                    object price = *,
                                    double expiration_seconds = *
                                    )

cdef str c_sell_with_specific_market(self,
                                     object market_trading_pair_tuple,
                                     object amount,
                                     object order_type = *,
                                     object price = *,
                                     double expiration_seconds = *
                                     )
```
Creates a buy or a sell order in the market specified by `market_trading_pair_tuple`and returns the order ID string.

**Arguments**

- **market_trading_pair_tuple**: a [`MarketTradingPairTuple`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/market_trading_pair_tuple.py) object specifying the `MarketBase` object and trading pair to create the order for.
- **amount**: a `Decimal` object, specifying the order size in terms of the base asset.
- **order_type**: an optional [`OrderType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) enum specifying the order type. Default value is `OrderType.MARKET`.
- **price**: an optional `Decimal` object, specifying the price for a limit order. This parameter is ignored if `order_type` is not `OrderType.LIMIT` or `OrderType.LIMIT_MAKER`.
- **expiration_seconds**: an optional number, which specifies how long a limit should automatically expire. This is only used by Ethereum-based decentralized exchanges like Radar Relay where active order cancellation costs gas. By default, passive cancellation via expiration is used on these exchanges.

### Cancel order
```cython
 c_cancel_order(self, object market_pair, str order_id)
```
Cancels an active order from a market.

**Arguments**

- **market_pair**: a `MarketTradingPairTuple` object specifying the `MarketBase` object and the trading pair to cancel order from.
- **order_id**: Order ID string returned from a previous call to order creation functions above.

## Order Tracking

Each `StrategyBase` object comes with an internal attribute `_sb_order_tracker`, which is an [`OrderTracker`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/order_tracker.pyx) object. The `OrderTracker` object is responsible for tracking all active and in-flight orders created by the `StrategyBase` object, and also all in-flight order cancels.

![StrategyBase and order tracker](/assets/img/strategy-order-tracker.svg)

When writing or modifying a strategy module, you can use the built-in `OrderTracker` object to query the active or in-flight orders / cancels you currently have. It's useful for preventing issuing duplicate orders or order cancels.

Below are some of the user functions or properties under `OrderTracker` that you can use:

- `active_maker_orders` property

    Returns a list of still active limit orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `market_pair_to_active_orders` property

    Returns a dictionary mapping from market trading pair tuples to lists of active limit orders.

    Return type: `Dict[MarketTradingPairTuple, List[LimitOrder]]`

- `active_bids` property

    Returns a list of active limit bid orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `active_asks` property

    Returns a list of active limit ask orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `tracked_taker_orders` property

    Returns a list of in-flight or active market orders, with their market object. This is useful for decentralized exchanges where market orders may take a minute to settle due to block delay.

    Return type: `List[Tuple[MarketBase, MarketOrder]]`

- `in_flight_cancels` property

    Returns a dictionary of order IDs that are being cancelled.

    Return type: `Dict[str, float]`
