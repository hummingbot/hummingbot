# Pure Market Making

## How it Works

In the *pure* market making strategy, Hummingbot continually posts limit bid and ask offers on a market and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate kill switch rate. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

### Schematic

The diagram below illustrates how market making works.  Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites: Inventory

1. You will need to hold sufficient inventory of quote and/or base currencies on the exchange to place orders of the exchange's minimum order size.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

### Placing Orders: Minimum Order Size

When placing orders, if the size of the order determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

> For example, if the `bid order amount * bid price` **<** `exchange's minimum order size` while `ask order amount * ask price` **>** `exchange's minimum order size`, a sell order would be created but no bid order would be created.

When using the [multiple order mode](#multiple-order-configuration), this may result in some (or none) of the orders being placed on one side.

> For example, if the `bid order amount 1 * bid price 1` **<** `exchange's minimum order size` while `bid order amount 2 * bid price 2` **>** `exchange's minimum order size`, then only the 2nd bid order would be created.

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

  | Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `pure_market_making`. <br/><br/>Currently available options: `arbitrage` or `cross_exchange_market_making` or `pure_market_making` or `discovery` or `simple_trade`  *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your maker exchange name >>>`: | The exchange where the bot will place bid and ask orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, or `bamboo_relay` *(case sensitive)* |
| `Enter quantity of orders per side (bid/ask) (single/multiple, default is single)>>> `: | `single` or `multiple`<br />Specify if you would like a single order per side (i.e. one bid and one ask), or multiple orders each side.<br /><br />Multiple allows for different prices and sizes for each side. See [additional configuration for multiple orders](#multiple-order-configuration). |
| `Enter the token symbol you would like to trade on [maker exchange name] >>>`: | Enter the token symbol for the *maker exchange*.<br/>Example input: `ETH-USD`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: options available are based on each exchange's methodology for labeling currency pairs. Ensure that the pair is a valid pair for the selected exchange.</td></tr></tbody></table> |
| `How far away from the mid price do you want to place the first bid (Enter 0.01 to indicate 1%)? >>>`: | This sets `bid_place_threshold` (see [definition](#configuration-parameters)). |
| `How far away from the mid price do you want to place the first ask (Enter 0.01 to indicate 1%)? >>>`: | This sets `ask_place_threshold` (see [definition](#configuration-parameters)). |
| `How often do you want to cancel and replace bids and asks (in seconds)? >>>`: | This sets the `cancel_order_wait_time` (see [definition](#configuration-parameters)). |
| `What is your preferred quantity per order (denominated in the base asset, default is 1)? >>>`: | This sets `order_amount` (see [definition](#configuration-parameters)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://docs.hummingbot.io/connectors/binance/) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Enter your IDEX API key >>>` | On Friday August 23, IDEX released updates to its servers requiring authentication/use of API keys to access its APIs. For more information, see [IDEX API key](/connectors/idex/#api-key). |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on decentralized exchange.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see: Setting up your Ethereum node](/installation/node/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |
| `At what percentage of loss would you like the bot to stop trading? (Enter 0.03 to indicate 3%. Enter -1.0 to disable) >>>` | This sets `stop_loss_pct` (see [definition](#configuration-parameters)) |
| `What type of price data would you like to use for stop loss (fixed/dynamic) ? >>>` | This sets `stop_loss_price_type` (see [definition](#configuration-parameters)) |
| `What base token would you like to use to calculate your inventory value? (Default "USD") >>>` | This sets `stop_loss_base_token` (see [definition](#configuration-parameters)) |
| `Would you like to enable inventory skew? (y/n) >>>` | This sets `inventory_skew_enabled` (see [definition](#configuration-parameters)) |
| `What is your target base asset inventory percentage (Enter 0.01 to indicate 1%)? >>> ` | This sets `inventory_target_base_percent` (see [definition](#configuration-parameters)) |
| `How long do you want to wait before placing the next order in case your order gets filled (in seconds). (Default is 10 seconds)? >>> " ` | This sets `filled_order_replenish_wait_time` (see [definition](#configuration-parameters)) |
| `Do you want to enable order_filled_stop_cancellation. If enabled, when orders are completely filled, the other side remains uncanceled (Default is False)? >>> " ` | This sets `enable_order_filled_stop_cancellation` (see [definition](#configuration-parameters)) |

### Multiple Order Configuration

Multiple orders allow you to create multiple orders for each bid and ask side, e.g. multiple bid orders with different prices and different sizes.

 | Prompt | Description |
|-----|-----|
| `How many orders do you want to place on both sides, (default is 1) ? >>>`: | This sets `number_of_orders` (see [definition](#configuration-parameters)) |
| `What is the size of the first bid and ask order, (default is 1) >>>`: | This sets `order_start_size` (see [definition](#configuration-parameters)) |
| `How much do you want to increase the order size for each additional order (default is 0) ? >>>` | This sets `order_step_size` (see [definition](#configuration-parameters)) |
| `Enter the price increments (as percentage) for subsequent orders (Enter 0.01 to indicate 1%)? >>>` | This sets `order_interval_percent` (see [definition](#configuration-parameters)) <br/><table><tbody><tr><td bgcolor="#e5f8f6">**Warning**: If you set this to a very low number, multiple orders may be placed on the same price level. For example for an asset like SNM/BTC, if you set an order interval percent of 0.004 (~0.4%) because of low asset value the price of the next order will be rounded to the nearest price supported by the exchange, which in this case might lead to multiple orders being placed at the same price level.</td></tr></tbody></table> |

### Inventory-Based Dynamic Order Sizing

This function allows you to specify a target base to quote asset inventory ratio and adjust order sizes whenever the current portfolio ratio deviates from this target.

For example, if you are targeting a 50/50 base to quote asset ratio but the current value of your base asset accounts for more than 50% of the value of your inventory, then bid order amount (buy base asset) is decreased, while ask order amount (sell base asset) is increased.

 | Prompt | Description |
|-----|-----|
| `Would you like to enable inventory skew? (y/n) >>>`: | This sets `inventory_skew_enabled` (see [definition](#configuration-parameters)) |
| `What is your target base asset inventory percentage (Enter 0.01 to indicate 1%) >>>`: | This sets `inventory_target_base_percent` (see [definition](#configuration-parameters)) |


### Order Adjustment based on filled events

Currently, hummingbot places orders as soon as there are no active orders. If there is a sustained movement in the market in any one direction for sometime, there is a risk that you might end up with a lot of base tokens in the case of a downward move or a lot of quote tokens in the case of an upward move.

You can add a delay using `filled_order_replenish_wait_time` for placing the next order immediately after the previous order gets completely filled, which will help address the above scenario.

Example: 
Assume your buy order gets filled at 1:00:00 and the delay is set to be 10 seconds. The next orders are placed at 1:00:10. The sell order is also cancelled within this delay period and placed at this time (1:00:10) to ensure both buy and sell orders use the same reference mid price and are in sync.

There is now an option using `enable_order_filled_stop_cancellation` to leave the orders on the other side hanging (not canceled) whenever a buy/sell order is completed.

Example:
Assume you are running Pure Market making in single order mode, the order size is 1 and the mid price is 100. Then,

1. If your bid threshold is 0.01, then your bid is placed at 99
2. If your ask threshold is 0.01, then your ask is placed at 101
3. If your current bid at 99 is fully filled (i.e), your current buy order for the size of 1 is fully completed
4. Now after the `cancel_order_wait_time` the ask order at 101 would be canceled normally
5. With the `enable_order_filled_stop_cancellation` parameter, you can leave this order hanging
6. After the `cancel_order_wait_time` you will now see two asks and one bid order, which will be the new bid and ask orders created after the wait time, along with the earlier un-canceled ask order.

The `enable_order_filled_stop_cancellation` can be used if there is enough volatility such that the hanging order might eventually get filled. It should also be used with caution, as the user should monitor the bot regularly to manually cancel orders which don't get filled. It is recommended to disable inventory skew while running this feature.

As these are experimental features, we are currently rolling them out to only `single order mode` for testing and receiving further feedback from the community.

 | Prompt | Description |
|-----|-----|
| `How long do you want to wait before placing the next order in case your order gets filled (in seconds). (Default is 10 seconds)? >>> " ` | This sets `filled_order_replenish_wait_time` (see [definition](#configuration-parameters)) |
| `Do you want to enable order_filled_stop_cancellation. If enabled, when orders are completely filled, the other side remains uncanceled (Default is False)? >>> " ` | This sets `enable_order_filled_stop_cancellation` (see [definition](#configuration-parameters)) |

#### Determining order size

The input `order_amount` is adjusted by the ratio of current base (or quote) percentage versus target percentage:

![Inventory skew calculations](/assets/img/inventory-skew-calculation.png)

## Configuration Parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_pure_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **order_amount**<br /><small>(single order strategy)</small> | The order amount for the limit bid and ask orders. <br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place orders if you do not have sufficient balance for both sides of the order <br/>
| **cancel_order_wait_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 60 seconds_. <br/><br/> The limit bid and ask orders are cancelled and new bids and asks are placed according to the current mid price and settings at this interval.
| **bid_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%) <br/> The strategy will place the buy(bid) order 1% away from the mid price if set to 0.01 <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set bid_place_threshold to 0.1 which is 10%, it will place your buy order (bid) at 10% below mid price of 100 which is 90.*
| **ask_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%) <br/> The strategy will place the sell(ask) order 1% away from the mid price if set to 0.01 <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set ask_place_threshold to 0.1 which is 10%, it will place your sell order (ask) at 10% above mid price of 100 which is 110.*
| **number_of_orders**<br /><small>(multiple order strategy)</small> | The number of orders to place for each side.<br />*Example: entering `3` places three bid **and** three ask orders.*
| **order_start_size**<br /><small>(multiple order strategy)</small> | The size of the `first` order, which is the order closest to the mid price (i.e. best bid and best ask).
| **order_step_size**<br /><small>(multiple order strategy)</small> | The magnitude of incremental size increases for orders subsequent orders from the first order.<br />*Example: entering `1` when the first order size is `10` results in bid sizes of `11` and `12` for the second and third orders, respectively, for a `3` order strategy.*
| **order_interval_percent**<br /><small>(multiple order strategy only)</small> | The percentage amount increase in price for subsequent orders from the first order. <em>Example:<br /> for a mid price of 100, `ask_place_threshold` of 0.01, and `order_interval_percent` of 0.005,<br />the first, second, and third ask prices would be **101** (= 100 + 0.01 x 100), **101.5** (= 101 + 0.005 x 100), and **102**.</em>
| **inventory_skew_enabled** | When this is `true`, the bid and ask order sizes are adjusted based on the `inventory_target_base_percent`.
| **inventory_target_base_percent** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%) <br/> The strategy will place bid and ask orders with adjusted sizes (based on `order_amount`, `order_start_size`) and try to maintain this base asset vs. total (base + quote) asset value.<br/><br/>*Example: You are market making ETH / USD with `order_amount: 1` and balances of 10 ETH and 1000 USD. Your current base asset value is ~67% and quote asset value is ~33%. If `inventory_target_base_percent: 0.5`, the order amount will be adjusted from 1 ETH bid, 1 ETH ask to 0.67 ETH bid, 1.33 ETH ask.*
| **filled_order_replenish_wait_time** | An amount in seconds, which specifies the delay before placing the next order for single order mode. _Default value: 10 seconds_. <br/> See section above on Order Adjustment based on filled events.
| **enable_order_filled_stop_cancellation** | When this is `true`, the orders on the side opposite to the filled orders remains uncanceled. _Default value: False_. <br/> See section above on Order Adjustment based on filled events.

## Risks and Trading Mechanics

!!! warning
    Not financial or investment advice.  Below are descriptions of some risks associated with the pure market making strategy.  There may be additional risks not described below.

### Ideal case

Pure market making strategies works best when you have a market that's relatively calm, but with sufficient trading activity. What that means for a pure market makers is, he would be able to get both of his bid and ask offers traded regularly; the price of his inventory doesn't change by a lot so there's no risk of him ending up on the wrong side of a trend. Thus he would be able to repeatedly capture small profits via the bid/ask spread over time.

![Figure 2: A clam market with regular trading activity](/assets/img/pure-mm-calm.png)

In the figure above, the period between 25 Feb and 12 Mar would be an example of the ideal case. The price of the asset stayed within a relatively small range, and there was sufficient trading activity for a market maker's offers to be taken regularly.

The only thing a market maker needs to worry about in this scenario is he must make sure the trading spread he sets is larger than the trading fees given to the exchange.

### Low trading activity

Markets with low trading activity higher risk for pure market making strategies. Here's an example:

![Figure 3: A market with low trading activity](/assets/img/pure-mm-low-volume.png)

In any market with low trading activity, there's a risk where the market maker may need to hold onto inventory for a long time without a chance to trade it back. During that time, the prices of the traded assets may rise or drop dramatically despite seeing no or little trading activity on the exchange. This exposes the market maker to inventory risk, even after mitigating some of this risk by using wider bid spreads.

Other strategies may be more suitable from a risk perspective in this type of market, e.g. [cross-exchange market making](/strategies/cross-exchange-market-making).

### Volatile or trending markets

Another common risk that market makers need to be aware of is trending markets. Here's one example:

![Figure 4: A trending market](/assets/img/pure-mm-trending.png)

If a pure market maker set his spreads naively in such a market, e.g. equidistant bid/ask spread, there's a risk of the market maker's bid consistently being filled as prices trend down, while at the same time the market continues to move away from the market maker's ask, decreasing the probability of sells.  This would result in an accumulation of inventory at exactly the time where this would reduce inventory inventory value, which is "wrong-way" risk.

However, it is still possible to improve the probability of generating profits in this kind of market by skewing bid asks, i.e. setting a wider bid spread (e.g. -4%) than ask spread (e.g. +0.5%).  In this way, the market maker is trying to catch price spikes in the direction of the trend and buy additional inventory only in the event of a larger moves, but sell more quickly when there is an opportunity so as to minimize the duration the inventory is held.  This approach also has a mean reversion bias, i.e. buy only when there is a larger move downwards, in the hopes of stabilization or recovery after such a large move.

Market making in volatile or trending markets is more advanced and risky for new traders. It's recommended that a trader looking to market make in this kind of environment to get mentally familiar with it (e.g. via paper trading) before committing meaningful capital to the strategy.

### Technology / infrastructure risk

There are many moving parts when operating a market making bot that **all** have to work together in order to properly function:

- Hummingbot code
- Exchange APIs
- Ethereum blockchain and node
- Network connectivity
- Hummingbot host computer

A fault in any component may result in bot errors, which can range from minor and inconsequential to major.

It is essential for any market making bot to be able to regularly refresh its bid and ask offers on the market in order to adjust to changing market conditions.  If a market making bot is disconnected from the exchange for an extended period of time, then the bid/ask offers it previously made would be left on the market and subject to price fluctuations of the market. Those orders may be filled at a loss as market prices move, while the market maker is offline.  It is very important for any market maker to make sure technical infrastructure is secure and reliable.
