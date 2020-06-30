# Cross Exchange Market Making

## How It Works

Cross exchange market making is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/hummingbot.pdf).

!!! warning "Updates to strategy"
    The cross exchange market making strategy has been updated as of v0.15.0, so that it will always place the order at the minimum profitability level. If the sell price for the specified volume on the taker exchange is 100, and you set the min_profitability as 0.01, it will place the maker buy order at 99. The top depth tolerance is also now specified by the user in base currency units. Please do not use old configuration files for running this strategy.

### Schematic

The diagrams below illustrate how cross exchange market making works.  The transaction involves two exchanges, a **taker exchange** and a **maker exchange**.  Hummingbot uses the market levels available on the taker exchange to create bid and ask orders (act as a market maker) on the maker exchange (*Figure 1*).

<small><center>***Figure 1: Hummingbot acts as market maker on maker exchange***</center></small>

![Figure 1: Hummingbot acts as market maker on maker exchange](/assets/img/xemm-1.png)

**Buy order**: Hummingbot can sell the asset on the taker exchange for 99 (the best bid available); therefore, it places a buy order on the maker exchange at a lower value of 98.

**Sell order**: Hummingbot can buy the asset on the taker exchange for 101 (the best ask available), and therefore makes a sell order on the maker exchange for a higher price of 102.

<small><center>***Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange***</center></small>

![Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange](/assets/img/xemm-2.png)

If a buyer (*Buyer D*) fills Hummingbot's sell order on the maker exchange (*Figure 2* ❶), Hummingbot immediately buys the asset on the taker exchange (*Figure 2* ❷).

The end result: Hummingbot has sold the same asset at \$102 (❶) and purchased it for $101 (❷), for a profit of $1.

## Prerequisites

### Inventory

1. For cross-exchange market making, you will need to hold inventory on two exchanges, one where the bot will make a market (the **maker exchange**) and another where the bot will source liquidity and hedge any filled orders (the **taker exchange**).

2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

Initially, we assume that the maker exchange is an Ethereum-based decentralized exchange and that the taker exchange is Binance.

### Minimum Order Size

When placing orders on the maker market and filling orders on the taker market, the order amount should meet the exchange's minimum order size and minimum trade size.

You can find more information about this for each [Connector](https://docs.hummingbot.io/connectors/) under Miscellaneous section.

### Adjusting Orders and Maker Price calculations

If the user has the following configuration,

order_amount: 1 ETH <br/>
min_profitability: 5 <br/>

and as per market conditions we have the following,

Sell price on Taker: 100 USDT (on a volume weighted average basis) <br/>
Top Bid price on Maker: 90 USDT (existing order on the order book, which is not the user's current order) <br/>

If `adjust_order_enabled` is set to `True`:
The bid price according to min profitability is 95 (100*(1-0.05)). However as top bid price is 90, the strategy will place the bid order above the existing top bid at 90.01 USDT

If `adjust_order_enabled` is set to `False`:
The bid price according to min profitability is 95 (100*(1-0.05)). Here the strategy will place the bid order at 95.

## Configuration Walkthrough

The following walks through all the steps when running `create` command.

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **maker_market** | `Enter your maker exchange name` | The exchange where the bot will place maker orders. |
| **taker_market** | `Enter your taker exchange name` | The exchange where the bot will execute taker orders. |
| **maker_market_trading_pair** | `Enter the token trading pair you would like to trade on maker market: [maker_market]` | Trading pair for the maker exchange. |
| **taker_market_trading_pair** | `Enter the token trading pair you would like to trade on taker market: [taker_market]` | Trading pair for the taker exchange. |
| **min_profitability** | `What is the minimum profitability for you to make a trade?` | Minimum required profitability in order for Hummingbot to place an order on the maker exchange. |
| **order_amount** | `What is the amount of [base_asset] per order? (minimum [min_amount])` | An amount expressed in base currency of maximum allowable order size. |

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

## Advanced Parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_xemm_[#].yml`).

| Term | Definition |
|------|------------|
| **adjust_order_enabled** | If enabled, the strategy will place the order on top of the top bid and ask if it is more profitable to place it there. If disabled, the strategy will ignore the top of the maker order book for price calculations and only place the order based on taker price and min_profitability. Refer to Adjusting orders and maker price calculations section above. _Default value: True_
| **active_order_canceling** | If enabled, Hummingbot will cancel orders that becomes unprofitable based on the `min_profitability` threshold. If disabled, Hummingbot will allow any outstanding orders to expire, unless `cancel_order_threshold` is reached.
| **cancel_order_threshold** | This parameter works when `active_order_canceling` is disabled. If the profitability of an order falls below this threshold, Hummingbot will cancel an existing order and place a new one, if possible.  This allows the bot to cancel orders when paying gas to cancel (if applicable) is a better than incurring the potential loss of the trade.
| **limit_order_min_expiration** | An amount in seconds, which is the minimum duration for any placed limit orders.
| **top_depth_tolerance** | An amount expressed in base currency which is used for getting the top bid and ask, ignoring dust orders on top of the order book.<br/><br/>*Example: If you have a top depth tolerance of `0.01 ETH`, then while calculating the top bid, you exclude orders starting from the top until the sum of orders excluded reaches `0.01 ETH`.*
| **anti_hysteresis_duration** | An amount in seconds, which is the minimum amount of time interval between adjusting limit order prices.
| **order_size_taker_volume_factor** | Specifies the percentage of hedge-able volume on taker side which will be considered for calculating the market making price.
| **order_size_taker_balance_factor** | Specifies the percentage of asset balance to be used for hedging the trade on taker side.
| **order_size_portfolio_ratio_limit** | Specifies the ratio of total portfolio value on both maker and taker markets to be used for calculating the order size if order_amount is not specified.