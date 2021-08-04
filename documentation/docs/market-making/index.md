# Market Making Features

These features give you more control over how your market making bot behaves. Please take the time to understand how these parameters work before risking extensive capital with bots that utilize them.

!!! note
    Currently, these features are limited to certain market making strategies, such as [pure market making](/strategies/pure_market_making). In the future, we aim to standardize the most popular features as modules or add them to the strategy base class, so that they are available to all Hummingbot strategies.

## How to configure

There are two ways to configure these parameters:

1. Run `config` to see the current strategy settings. Run command `config [parameter_name]` to reconfigure the parameter.
2. Outside of the Hummingbot client, you can edit the strategy configuration file directly using a text editor and then import it later.

## Advanced configuration parameters

| Feature | Parameter | Prompt | Definition |
|---------|-----------|--------|------------|
| [Order Levels](./order-levels) | `order_levels` | `How many orders do you want to place on both sides?` | The number of order levels to place for each side of the order book. |
| [Order Levels](./order-levels) | `order_level_amount` | `How much do you want to increase or decrease the order size for each additional order?` | The size can either increase(if set to a value greater than zero) or decrease(if set to a value less than zero) for subsequent order levels after the first level. |
| [Order Levels](./order-levels) | `order_level_spread` | `Enter the price increments (as percentage) for subsequent orders?` | The incremental spread increases for subsequent order levels after the first level. |
| [Inventory Skew](./inventory-skew) | `inventory_skew_enabled` | `Would you like to enable inventory skew? (Yes/No)` | Allows the user to set and maintain a target inventory split between base and quote assets. |
| [Inventory Skew](./inventory-skew) | `inventory_target_base_pct` | `On [exchange], you have [base_asset_balance] and [quote_asset_balance]. By market value, your current inventory split is [base_%_ratio] and [quote_%_ratio]. Would you like to keep this ratio?` | Target amount held of the base asset, expressed as a percentage of the total base and quote asset value. |
| [Inventory Skew](./inventory-skew) | `inventory_range_multiplier` | `What is your tolerable range of inventory around the target, expressed in multiples of your total order size?` | This expands the range of tolerable inventory level around your target base percent, as a multiple of your total order size. Larger values expand this range. |
| [Filled Order Delay](./filled-order-delay) | `filled_order_delay` | `How long do you want to wait before placing the next order if your order gets filled (in seconds)?` | How long to wait before placing the next set of orders in case at least one of your orders gets filled. |
| [Hanging Orders](./hanging-orders) | `hanging_orders_enabled` | `Do you want to enable hanging orders? (Yes/No)` | When enabled, the orders on the side opposite to the filled orders remains active. |
| [Hanging Orders](./hanging-orders) | `hanging_orders_cancel_pct` | `At what spread percentage (from mid price) will hanging orders be canceled?` | Cancels the hanging orders when their spread goes above this value. |
| [Minimum Spread](./minimum-spread) | `minimum_spread` | `At what minimum spread should the bot automatically cancel orders` | If the spread of any active order fall below this param value, it will be automatically cancelled. |
| [Order Refresh Tolerance](./order-refresh-tolerance) | `order_refresh_tolerance_pct` | `Enter the percent change in price needed to refresh orders at each cycle` | The spread (from mid price) to defer order refresh process to the next cycle. |
| [Price Band](./price-band) | `price_ceiling` | `Enter the price point above which only sell orders will be placed` | Place only sell orders when mid price goes above this price. |
| [Price Band](./price-band) | `price_floor` | `Enter the price below which only buy orders will be placed` | Place only buy orders when mid price falls below this price. |
| [Ping Pong](./ping-pong) | `ping_pong_enabled` | `Would you like to use the ping pong feature and alternate between buy and sell orders after fills?` | Whether to alternate between buys and sells. |
| [Order Optimization](./order-optimization) | `order_optimization_enabled` | `Do you want to enable best bid ask jumping? (Yes/No)` | Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market. |
| [Order Optimization](./ask_order_optimization_depth) | `ask_order_optimization_depth` | `How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)?` | The depth in base asset amount to be used for finding top bid ask. |
| [Order Optimization](./bid_order_optimization_depth) | `bid_order_optimization_depth` | `How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)?` | The depth in base asset amount to be used for finding top bid. |
| [Add Transaction Costs](./add-transaction-costs)  | `add_transaction_costs` | `Do you want to add transaction costs automatically to order prices? (Yes/No)` | Whether to enable adding transaction costs to order price calculation. |
| [External Price Source](./price-source) | `price_source_enabled` | `Would you like to use an external pricing source for mid-market price? (Yes/No)` | When enabled, allows users to use an external pricing source for the mid price. |
| [External Price Source](./price-source) | `price_source_type` | `Which type of external price source to use? (exchange/custom_api)` | The type of external pricing source. |
| [External Price Source](./price-source) | `price_source_exchange` | `Enter external price source exchange name` | Name of exchange to be used for external pricing source. |
| [External Price Source](./price-source) | `price_source_market` | `Enter the token pair on [price_source_exchange]` | The trading pair for the price source exchange. |
| [External Price Source](./price-source) | `price_source_custom` | `Enter pricing API URL` | An external API that returns price. |
| [External Price Source](./price-source) | `take_if_crossed` | `Do you want to let your maker orders match and fill if they cross the order book?` | Take order if they cross orderbook when external price source is enabled. |
