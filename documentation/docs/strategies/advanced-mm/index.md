# Advanced Market Making

These advanced parameters give you more control over how your bot behaves. Please take the time to understand how these parameters work before risking extensive capital with bots that utilize them.

## How to Configure

There are two ways to configure these parameters:

1. Run `config` to see the current strategy settings. Run command `config [parameter_name]` to reconfigure the parameter.
2. Outside of the Hummingbot client, you can edit the strategy configuration file directly using a text editor and then import it later.

## Advanced Configuration Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| [**order_levels**](./multiple-orders) | `How many orders do you want to place on both sides?` | The number of order levels to place for each side of the order book. |
| [**order_level_amount**](./multiple-orders) | `How much do you want to increase the order size for each additional order?` | The incremental size increase for subsequent order levels after the first level. |
| [**order_level_spread**](./multiple-orders) | `Enter the price increments (as percentage) for subsequent orders?` | The incremental spread increases for subsequent order levels after the first level. |
| [**inventory_skew_enabled**](./inventory-skew) | `Would you like to enable inventory skew? (Yes/No)` | Allows the user to set and maintain a target inventory split between base and quote assets. |
| [**inventory_target_base_pct**](./inventory-skew) | `What is your target base asset percentage?` | Target amount held of the base asset, expressed as a percentage of the total base and quote asset value. |
| [**inventory_range_multiplier**](./inventory-skew) | `What is your tolerable range of inventory around the target, expressed in multiples of your total order size?` | This expands the range of tolerable inventory level around your target base percent, as a multiple of your total order size. Larger values expand this range. |
| [**filled_order_delay**](./filled-order-delay) | `How long do you want to wait before placing the next order if your order gets filled (in seconds)?` | How long to wait before placing the next set of orders in case at least one of your orders gets filled. |
| [**hanging_orders_enabled**](./hanging-orders) | `Do you want to enable hanging orders? (Yes/No)` | When enabled, the orders on the side opposite to the filled orders remains active. |
| [**hanging_orders_cancel_pct**](./hanging-orders) | `At what spread percentage (from mid price) will hanging orders be canceled?` | Cancels the hanging orders when their spread goes above this value. |
| [**order_optimization_enabled**](./order-optimization) | `Do you want to enable best bid ask jumping? (Yes/No)` | Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market. |
| [**order_optimization_depth**](./order-optimization) | `How deep do you want to go into the order book for calculating the top bid and ask, ignoring dust orders on the top (expressed in base asset amount)?` | The depth in base asset amount to be used for finding top bid and ask. |
| [**add_transaction_costs**](./add-transaction-costs) | `Do you want to add transaction costs automatically to order prices? (Yes/No)` | Whether to enable adding transaction costs to order price calculation. |
| [**price_source_enabled**](./price-source) | `Would you like to use an external pricing source for mid-market price? (Yes/No)` | When enabled, allows users to use an external pricing source for the mid price. |
| [**price_source_type**](./price-source) | `Which type of external price source to use? (exchange/custom_api)` | The type of external pricing source. |
| [**price_source_exchange**](./price-source) | `Enter external price source exchange name` | Name of exchange to be used for external pricing source. |
| [**price_source_market**](./price-source) | `Enter the token pair on [price_source_exchange]` | The trading pair for the price source exchange. |
| [**price_source_custom**](./price-source) | `Enter pricing API URL` | An external API that returns price. |