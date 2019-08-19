# Cross Exchange Market Making

## Architecture

The cross exchange market making strategy performs market making trades between two markets: it emits limit orders to a less liquid, larger spread market; and emits market orders on a more liquid, smaller spread market whenever the limit orders were hit. This, in effect, sends the liquidity from the more liquid market to the less liquid market.

In Hummingbot code and documentation, we usually refer to the less liquid market as the "maker side" - since the cross exchange market making strategy is providing liquidty there. We then refer to the more liquid market as the "taker side" - since the strategy is taking liquidity there.

The cross exchange market making strategy's code is divided into two major parts:

 1. Order creation and adjustment

    Periodically creates and adjusts limit orders on the maker side.
 
 2. Hedging order fills

    Performs the opposite, hedging trade on the taker side, whenever a maker order has been filled.

## Order Creation and Adjustment

Here's a high-level view of the logical flow of the order creation and adjustment part. The overall logic of order creation and adjustment is pretty involved, but it can be roughly divided to the **Cancel Order Flow** and the **Create Order Flow**.

The cross exchange market making strategy regularly refreshes the limit orders it has on the maker side market by regularly cancelling old orders (or waiting for existing order to expire), and creating new limit orders. This process ensures the limit orders it has on the maker side are always of the correct and profitable prices.

![Figure 1: Order creation and adjustment flow chart](/assets/img/xemm-flowchart-1.svg)

### Cancel Order Flow

The cancel order flow regularly monitors all active limit orders on the maker side, to ensure they are all valid and profitable over time. If any active limit order becomes invalid (e.g. because the asset balance changed) or becomes unprofitable (due to market price changes), then it should cancel such orders.

#### Active order cancellation setting

The [`active_order_canceling`](/strategies/corss-exchange-market-making/) setting changes how the cancel order flow operates. `active_order_canceling` should be enabled when the maker side is a centralized exchange (e.g. Binance, Coinbase Pro), and it should be disabled when the maker side is a decentralized exchange.

When `active_order_canceling` is enabled, the cross exchange market making strategy would refresh orders by actively cancelling them regularly. This is optimal for centralized exchanges because it allows the strategy to respond quickly when, for example, market prices have significantly changed. This should not be chosen for decentralized exchanges, because actively cancelling orders on DEXes can often take a long time and may also require gas cost.

When `active_order_canceling` is disbled, the cross exchange market making strategy would emit limit orders that automatically expire after a predefined time period. This means the strategy can just wait for them to expire to refresh the maker orders, rather than having to cancel them actively. This is useful for decentralized exchanges because it avoids the potentially very long cancellation delays there, and it also does not cost any gas to wait for order expiration.

It is still possible for the strategy to actively cancel orders with `active_order_canceling` disabled, via the [`cancel_order_threshold`](/strategies/corss-exchange-market-making/) setting. For example, you can set it to -0.05 s.t. the strategy would still cancel a limit order on a DEX when it's profitability dropped below -5%. This can be used as a safety switch to guard against sudden and large price changes on decentralized exchanges.

#### Is hedging profitable?

Assuming active order canceling is enabled, the first check the strategy does with each active maker order is whether it is still profitable or not. The current profitability of an order is calculated assuming the order is filled and hedged on the taker market immediately.

If the profit ratio calculated for the maker order is less than the [`min_profitability`](/strategies/corss-exchange-market-making/) setting, then the order is canceled.

Otherwise, the strategy will go onto the next check.

#### Is there sufficient account balance?

The next check afterwards checks whether there's enough asset balance left to satisfy the maker order. If there is not enough balance left on the exchange, the order would be cancelled.

Otherwise, the strategy will go onto the next check.

#### Is the price correct?



### Create Order Flow

## Hedging Order Fills