# Pure Market Making

## How it Works

In the *pure* market making strategy, Hummingbot continually posts limit bid and ask offers on a market and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate stop loss limits. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

### Schematic

The diagram below illustrates how market making works.  Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

### Risks and Trading Mechanics

#### Ideal case

Pure market making strategies works best when you have a market that's relatively calm, but with sufficient trading activity. What that means for a pure market makers is, he would be able to get both of his bid and ask offers traded regularly; the price of his inventory doesn't change by a lot so there's no risk of him ending up on the wrong side of a trend. Thus he would just keep making small profits via the bid/ask spread over and over.

![Figure 2: A clam market with regular trading activity](/assets/img/pure-mm-calm.png)

In the figure above, the period between 25 Feb and 12 Mar would be an example of the ideal case. The price of the asset stayed within a relatively small range, and there was sufficient trading activity for a market maker's offers to be taken regularly.

The only thing a market maker needs to worry about in this scenario is he must make sure the trading spread he sets is larger than the trading fees given to the exchange.

#### Low trading activity

Markets with low trading activity are not suitable for pure market making strategies. Here's an example:

![Figure 3: A market with low trading activity](/assets/img/pure-mm-low-volume.png)

In any market with low trading activity, there's a risk where the market maker may need to hold onto inventory for a long time without a chance to trade it back. During that time, the prices of the traded assets may rise or drop dramatically despite seeing no or little trading activity on the exchange. This puts the market maker exposed to wrong side risks to whatever inventory he happens to be holding.

It's best to avoid using the pure market making strategies on this kind of market, and use other strategies that are more suitable. e.g. [cross-exchange market making](/strategies/cross-exchange-market-making).

#### Volatile or trending markets

Another common risk that market makers need to be aware of is trending markets. Here's one example:

![Figure 4: A trending market](/assets/img/pure-mm-trending.png)

If a pure market maker set his spreads naively in the market above, say, +-1%, then he'll most likely lose money by consistently buying the asset up while it's dropping, and having difficulty to sell soon enough. He'll very likely end up on the wrong side of the market consistently.

It is still possible for a market maker to make money in this kind of market, usually by setting his spreads in the same direction of the trend. e.g. instead of +-1%, a market maker may set his bids at -4% and his asks at +0.2%. In this way, the market maker is trying to catch price spikes in the direction of the trend, and then try to do the opposite trade as soon as possible to exploit the brief price recovery that usually follows.

Market making in volatile or trending markets is more advanced and risky for new traders. It's recommended that a trader looking to market make in this kind of environment to get mentally familiar with it (e.g. via paper trading) before committing capital to the strategy.

#### Unreliable network connection

One more risk that anybody running a market making bot must be aware of is technical risk - how reliable his infrastructure, especially his network connection is.

It is essential for any market making bot to be able to regularly refresh its bid and ask offers on the market, s.t. it can keep its offers at profitable prices.

If a market making bot is disconnected from the exchange for an extended period of time, then the bid/ask offers it previously made would be left on the market and subject to price fluctuations of the market. They may be traded at a loss as market prices move, while the market maker himself is offline.

It is very important for any market maker to make sure his technical infrastructure is secure and reliable.

## Prerequisites: Inventory

1. You will need to hold inventory of quote and base currencies on the exchange.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

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
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see: Setting up your Ethereum node](/installation/node/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |
| `At what percentage of loss would you like the bot to stop trading? (Enter 0.03 to indicate 3%. Enter -1.0 to disable) >>>` | This sets `stop_loss_pct` (see [definition](#configuration-parameters)) |
| `What type of price data would you like to use for stop loss (fixed/dynamic) ? >>>` | This sets `stop_loss_price_type` (see [definition](#configuration-parameters)) |
| `What base token would you like to use to calculate your inventory value? (Default "USD") >>>` | This sets `stop_loss_base_token` (see [definition](#configuration-parameters)) |

### Multiple Order Configuration

Multiple orders allow you to create multiple orders for each bid and ask side, e.g. multiple bid orders with different prices and different sizes.

 | Prompt | Description |
|-----|-----|
| `How many orders do you want to place on both sides, (default is 1) ? >>>`: | This sets `number_of_orders` (see [definition](#configuration-parameters)) |
| `What is the size of the first bid and ask order, (default is 1) >>>`: | This sets `order_start_size` (see [definition](#configuration-parameters)) |
| `How much do you want to increase the order size for each additional order (default is 0) ? >>>` | This sets `order_step_size` (see [definition](#configuration-parameters)) |
| `Enter the price increments (as percentage) for subsequent orders (Enter 0.01 to indicate 1%)? >>>` | This sets `order_interval_percent` (see [definition](#configuration-parameters)) |

## Configuration parameters

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
| **stop_loss_pct** | The threshold amount upon which `hummingbot` will cease placing orders if the value of inventory has fallen.
| **stop_loss_price_type** | The pricing methdology used by `hummingbot` uses when calculating inventory value when evaluating the stop loss feature.<ul><li>`fixed`: uses the assets prices from when the strategy was first started.<li>`dynamic`: uses current prevailing prices for assets.</ul>
| **stop_loss_base_token** | The base currency into which inventory is valued for purposes of evaluating stop loss.

## Architecture

The built-in pure market making strategy in Hummingbot periodically requests limit order proposals from configurable order pricing and sizing plugins, and also periodically refreshes the orders by cancelling existing limit orders.

Here's a high level view of the logic flow inside the built-in pure market making strategy.

![Figure 5: Pure market making strategy logical flowchart](/assets/img/pure-mm-flowchart.svg)

The pure market making strategy operates in a tick-by-tick manner, as described in the [Strategies Overview](/strategies) document. Each tick is typically 1 second, although it can be programmatically modified to longer or shorter durations.

At each tick, the pure market making strategy would first query the order filter plugin whether to proceed or not. Assuming the answer is yes, then it'll query the order pricing and sizing plugins and calculate whether and what market making orders it should emit. At the same time, it'll also look at any existing limit orders it previously placed on the market and decide whether it should cancel those.

The process repeats over and over at each tick, causing limit orders to be periodically placed and cancelled according to the proposals made by the order pricing and sizing plugins.

### Plugins

There are a few plugin interfaces that the pure market making strategy depends on arriving at its order proposals.

![Figure 6: Pure market making strategy plugins](/assets/img/pure-mm-uml.svg)

* [`OrderFilterDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_filter_delegate.pxd)

    Makes the Yes / No decision to proceed with processing the current clock tick or not.

* [`OrderPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_pricing_delegate.pxd)

    Returns a [`PriceProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of prices for creating bid and ask orders. If no order should be created at the current clock tick (e.g. because there're already existing orders), it may choose to return empty lists instead.

* [`OrderSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_sizing_delegate.pxd)

    Returns a [`SizingProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of order sizes for creating bid and ask orders, given the pricing proposal. If a proposed order at a certain price should not be created (e.g. there's not enough balance on the exchange), it may choose to return zero size for that order instead.

### Built-in Plugins

If you configure the pure market making strategy with multiple orders **disabled**, then Hummingbot will be using [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx) and [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) for the pricing and sizing plugins.

#### ConstantSpreadPricingDelegate

If you look into the logic of the [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx), it's extremely simple - it'll always propose a bid and an ask order at a pre-configured spread from the current mid-price. It doesn't do any checks about whether you have existing orders, or have enough balance to create the orders - but that's fine.

#### ConstantSizeSizingDelegate

The logic inside [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) looks a bit more involved, because it's checking whether there're existing limit orders that are still active, and also whether there's enough balance in the exchange to create new orders. But beyond the checks, it's really just proposing constant order size proposals.

If all the checks are green (i.e. no active limit orders, and enough balance to make new orders), then it will make an order size proposal with the pre-configured size on both the bid and ask sides. Otherwise, it'll propose 0 order sizes.

If you configure the pure market making strategy with multiple orders **enabled**, then Hummingbot will be using [`ConstantMultipleSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_multiple_spread_pricing_delegate.pyx) and [`StaggeredMultipleSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/staggered_multiple_size_sizing_delegate.pyx) for the pricing and sizing plugins instead.

### Refreshing orders periodically

For each limit order that was emitted by the pure market making strategy, an expiry timestamp would be generated for that order and the order will be tracked by the strategy. The time until expiry for new orders is configured via the **cancel_order_wait_time** option in [Configuration Parameters](#configuration-parameters).

Once an order's expiration time has passed, the pure market making strategy will create a cancel order proposal for that order.

### Executing order proposals

After collecting all the order pricing, sizing and cancel order proposals from plugins and the internal refresh order logic - the pure market making strategy logic will merge all of the proposals and execute them.

### Example Order Flow

Below is a hypothetical example of how the pure market making strategy works for a few clock ticks.

At clock tick *n*, there may be existing limit orders on both the bid and ask sides, and both have not yet expired. Assuming we're using the `ConstantSizeSizingDelegate` and `ConstantSpreadPricingDelegate` in this case, the proposed sizes for new orders will be 0. There'll be no cancel order proposals. So the strategy will do nothing for this clock tick.

At clock tick *n+1*, the limit bid order has expired. The strategy will then generate a cancel order proposal for the expired bid order. The cancellation will then be send to the exchange and executed.

At clock tick *n+2*, the `ConstantSizSizingDelegate` notices there's no longer an order at the bid side. So it'll propose a non-zero order size for a new bid order. Let's assume the existing ask order hasn't expired yet, so no cancellation proposals will be generated at this clock tick. At the execution phase, the strategy will simply create a bid order calculated from the current market mid-price. Thus the bid order is refreshed.

This cycle of order creation and order cancellation will repeat again and again for as long as the strategy is running. If a limit order is completely filled by a market order, the strategy will simply refresh it at the next clock tick.
