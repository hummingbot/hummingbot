# Cross Exchange Market Making

## Architecture

The cross exchange market making strategy performs market making trades between two markets: it emits limit orders to a less liquid, larger spread market; and emits market orders on a more liquid, smaller spread market whenever the limit orders were hit. This, in effect, sends the liquidity from the more liquid market to the less liquid market.

In Hummingbot code and documentation, we usually refer to the less liquid market as the "maker side" - since the cross exchange market making strategy is providing liquidity there. We then refer to the more liquid market as the "taker side" - since the strategy is taking liquidity there.

The cross exchange market making strategy's code is divided into two major parts:

 1. Order creation and adjustment

    Periodically creates and adjusts limit orders on the maker side.
 
 2. Hedging order fills

    Performs the opposite, hedging trade on the taker side, whenever a maker order has been filled.

## Order Creation and Adjustment

Here's a high-level view of the logical flow of the order creation and adjustment part. The overall logic of order creation and adjustment is pretty involved, but it can be roughly divided to the **Cancel Order Flow** and the **Create Order Flow**.

The cross exchange market making strategy regularly refreshes the limit orders it has on the maker side market by regularly cancelling old orders (or waiting for existing order to expire), and creating new limit orders. This process ensures the limit orders it has on the maker side are always of the correct and profitable prices.

![Figure 1: Order creation and adjustment flow chart](/assets/img/xemm-flowchart-1.svg)

The entry point of this logic flow is the `c_process_market_pair()` function in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).

### Cancel Order Flow

The cancel order flow regularly monitors all active limit orders on the maker side, to ensure they are all valid and profitable over time. If any active limit order becomes invalid (e.g. because the asset balance changed) or becomes unprofitable (due to market price changes), then it should cancel such orders.

![Figure 2: Cancel order flow chart](/assets/img/xemm-flowchart-2.svg)

#### Active order cancellation setting

The [`active_order_canceling`](/strategies/cross-exchange-market-making/) setting changes how the cancel order flow operates. `active_order_canceling` should be enabled when the maker side is a centralized exchange (e.g. Binance, Coinbase Pro), and it should be disabled when the maker side is a decentralized exchange.

When `active_order_canceling` is enabled, the cross exchange market making strategy would refresh orders by actively cancelling them regularly. This is optimal for centralized exchanges because it allows the strategy to respond quickly when, for example, market prices have significantly changed. This should not be chosen for decentralized exchanges that charge gas for cancelling orders (such as Radar Relay).

When `active_order_canceling` is disabled, the cross exchange market making strategy would emit limit orders that automatically expire after a predefined time period. This means the strategy can just wait for them to expire to refresh the maker orders, rather than having to cancel them actively. This is useful for decentralized exchanges because it avoids the potentially very long cancellation delays there, and it also does not cost any gas to wait for order expiration.

It is still possible for the strategy to actively cancel orders with `active_order_canceling` disabled, via the [`cancel_order_threshold`](/strategies/cross-exchange-market-making/) setting. For example, you can set it to -0.05 such that the strategy would still cancel a limit order on a DEX when it's profitability dropped below -5%. This can be used as a safety switch to guard against sudden and large price changes on decentralized exchanges.

#### Is hedging profitable?

Assuming active order canceling is enabled, the first check the strategy does with each active maker order is whether it is still profitable or not. The current profitability of an order is calculated assuming the order is filled and hedged on the taker market immediately.

If the profit ratio calculated for the maker order is less than the [`min_profitability`](/strategies/cross-exchange-market-making/) setting, then the order is canceled.

The logic of this check can be found in the function `c_check_if_still_profitable()` in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).

Otherwise, the strategy will go onto the next check.

#### Is there sufficient account balance?

The next check afterwards checks whether there's enough asset balance left to satisfy the maker order. If there is not enough balance left on the exchange, the order would be cancelled.

The logic of this check can be found in the function `c_check_if_sufficient_balance()` in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).

Otherwise, the strategy will go onto the next check.

#### Is the price correct?

Asset prices on both the maker side and taker side are always changing, and thus the optimal prices for the limit orders on the maker side would change over time as well.

The cross exchange market making strategy calculates the optimal pricing from the following factors:

 1. Current market order prices on the taker side.
 2. Current order book depth on the maker side.
 3. [`top_depth_tolerance`](/strategies/cross-exchange-market-making/) setting, which is applied to the order book depths on maker side.
 4. [`min_profitability`](/strategies/cross-exchange-market-making/) setting, which is applied to the market order prices on the taker side.

If the price of the active order is different from the optimal price calculated, then the order would be cancelled. Otherwise, the strategy would allow the order to stay.

The logic of this check can be found in the function `c_check_if_price_correct()` in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).

After all the active orders on make side have been checked, the strategy will proceed to the create order flow.

### Create Order Flow

After going through the cancel order flow, the cross exchange market making strategy would check and re-create any missing limit orders on the maker side.

![Figure 3: Cancel order flow chart](/assets/img/xemm-flowchart-3.svg)

The logic inside the create order flow is relatively straightforward. It checks whether there are existing bid and ask orders on the maker side. If any of the orders are missing, it will check whether it is profitable to create one at the moment. If it's profitable to create the missing orders, it will calculate the optimal pricing and size and create those orders.

The logic of the create order flow can be found in the function `c_check_and_create_new_orders()` in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).

## Hedging Order Fills

The cross exchange market making strategy would always immediately hedge any order fills from the maker side, regardless of how profitable the hedge is at the moment. The rationale is, it is more useful to minimize unnecessary exposure to further market risks for the users, than to wait speculatively for a profitable moment to hedge the maker order fill - which may never come.

![Figure 4: Hedging order fills flow chart](/assets/img/xemm-flowchart-4.svg)

The logic of the hedging order fill flow can be found in the function `c_did_fill_order()` and `c_check_and_hedge_orders()` in [`cross_exchange_market_making.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx).
