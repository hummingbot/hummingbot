# Advanced Market Making

These advanced parameters give you more control over how your bot behaves. Please take the time to understand how these parameters work before risking extensive capital.

## Configuring Advanced Parameters

When the strategy is already running, run command `config advanced_mode`. This will stop the strategy and walk you through in reconfiguring all the advanced parameters.

## [Multiple Orders](./multiple-orders)

These parameters allow you to set multiple levels of orders on each side and gives you more fine-grained control over the spreads and sizes of each set of orders. See [Multiple orders](./multiple-orders) for more information.

## Inventory Skew

## Hanging Orders

## Filled Order Delay

By default, Hummingbot places orders as soon as there are no active orders; i.e., Hummingbot immediately places a new order to replace a filled order. If there is a sustained movement in the market in any one direction for some time, there is a risk of continued trading in that direction: For example, continuing to buy and accumulate base tokens in the case of a prolonged downward move or continuing to sell in the case of a prolonged upward move.

The `filled_order_replenish_wait_time` parameter allows for a delay when placing a new order in the event of an order being filled, which will help mitigate the above scenarios.

**Example:**

If you have a buy order that is filled at 1:00:00 and the delay is set as 60 seconds, the next orders placed will be at 1:01:00. The sell order is also cancelled within this delay period and placed at 1:01:00 to ensure that both buy and sell orders stay in sync.

| Prompt | Description |
|-----|-----|
| `How long do you want to wait before placing the next order if your order gets filled (in seconds)? >>>` | This sets `filled_order_replenish_wait_time` ([definition](#configuration-parameters)). |

### Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `Enter quantity of bid/ask orders per side (single/multiple) >>> ` | Enter `single` to place only 1 order per side (i.e. 1 bid and 1 ask)<br/><br/>Enter `multiple` to place multiple orders on each side.<br /><br />Multiple order also allows you to set different prices and sizes on each side. See [additional configuration for multiple orders](#multiple-order-configuration). |
| `Would you like to enable inventory skew? (Yes/No) >>>` | More information in [Inventory-Based Dynamic Order Sizing](#inventory-based-dynamic-order-sizing) section. |
| `How long do you want to wait before placing the next order if your order gets filled (in seconds)? >>>` | More information in [Order Replenish Time](#order-replenish-time) section. |
| `Do you want to enable hanging orders? (Yes/No) >>>` | More information in ["Hanging Orders"](#hanging-orders) section. |
| `Do you want to enable best bid ask jumping? (Yes/No) >>>` | More information in [Best Bid Ask Jumping](#best-bid-ask-jumping) section. |
| `Do you want to add transaction costs automatically to order prices? (Yes/No) >>>` | More information in [Adding Transaction Costs to Prices](#adding-transaction-costs-to-prices) section. |
| `Would you like to use an external pricing source for mid-market price? (Yes/No) >>>` | More information in [External Pricing Source Configuration](#external-pricing-source-configuration) section. |

### Adding Transaction Costs to Prices

Transaction costs can now be added to the price calculation. `fee_pct` refers to the percentage maker fees per order (generally common in Centralized exchanges) while `fixed_fees` refers to the flat fees (generally common in Decentralized exchanges).

- The bid order price will be calculated as:

![Bid price with transaction cost](/assets/img/trans_cost_bid.PNG)

- The ask order price will be calculated as:

![Ask price with transaction cost](/assets/img/trans_cost_ask.PNG)

Adding the transaction cost will reduce the bid order price and increase the ask order price i.e. putting your orders further away from the mid price.

We currently display warnings if the adjusted price post adding the transaction costs is 10% away from the original price. This setting can be modified by changing `warning_report_threshold` in the `c_add_transaction_costs_to_pricing_proposal` function inside `hummingbot/strategy/pure_market_making/pure_market_making_v2.pyx`.

If the buy price with the transaction cost is zero or negative, it is not profitable to place orders and orders will not be placed.

| Prompt | Description |
|-----|-----|
| `Do you want to add transaction costs automatically to order prices? (Yes/No) >>>` | This sets `add_transaction_costs` ([definition](#configuration-parameters)). |

## Advanced Configuration Parameters

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf/conf_pure_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **order\_amount**<br /><small>(single order strategy)</small> | The order amount for the limit bid and ask orders. <br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place orders if you do not have sufficient balance for both sides of the order. <br/>
| **cancel\_order\_wait\_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 30 seconds_. <br/><br/> The limit bid and ask orders are cancelled and new bids and asks are placed according to the current mid price and settings at this interval.
| **bid\_place\_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the buy (bid) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set bid_place_threshold to 0.1 which is 10%, it will place your buy order (bid) at 10% below mid price of 100 which is 90.*
| **ask\_place\_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the sell (ask) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set ask_place_threshold to 0.1 which is 10%, it will place your sell order (ask) at 10% above mid price of 100 which is 110.*
| **number\_of\_orders**<br /><small>(multiple order strategy)</small> | The number of orders to place for each side.<br /> <em>Example: Entering `3` places three bid **and** three ask orders.</em>
| **order\_start\_size**<br /><small>(multiple order strategy)</small> | The size of the `first` order, which is the order closest to the mid price (i.e. best bid and best ask).
| **order\_step\_size**<br /><small>(multiple order strategy)</small> | The magnitude of incremental size increases for orders subsequent orders from the first order.<br />*Example: Entering `1` when the first order size is `10` results in bid sizes of `11` and `12` for the second and third orders, respectively, for a `3` order strategy.*
| **order\_interval\_percent**<br /><small>(multiple order strategy only)</small> | The percentage amount increase in price for subsequent orders from the first order. <br /> <em>Example: For a mid price of 100, `ask_place_threshold` of 0.01, and `order_interval_percent` of 0.005,<br />the first, second, and third ask prices would be **101** (= 100 + 0.01 x 100), **101.5** (= 101 + 0.005 x 100), and **102**.</em>
| **inventory\_skew\_enabled** | When this is `true`, the bid and ask order sizes are adjusted based on the `inventory_target_base_percent`.
| **inventory\_target\_base\_percent** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place bid and ask orders with adjusted sizes (based on `order_amount`, `order_start_size`) and try to maintain this base asset vs. total (base + quote) asset value.<br/><br/>*Example: You are market making ETH / USD with `order_amount: 1` and balances of 10 ETH and 1000 USD. Your current base asset value is ~67% and quote asset value is ~33%. If `inventory_target_base_percent: 0.5`, the order amount will be adjusted from 1 ETH bid, 1 ETH ask to 0.67 ETH bid, 1.33 ETH ask.*
| **inventory\_range\_multiplier** | The allowable trade range around the `inventory_target_base_percent`, expressed in multiples of the total order size.<br/><br/>For example, if you're using multiple-order mode on ETHUSD, the order start size is 1, the order step size is 0.5, and number of orders on each side is 3 - then the total order size is \( 2 \times (1 + 1.5 + 2.0) = 9.0 \) ETH.<br/><br/>Setting `inventory_range_multiplier` to 2.0 in the example above means you allow the strategy to trade up to \( 2.0 \times 9.0 = 18.0 \) ETH above and below the target percentage.<br/><br/>If you're below allowable the trading range, then the strategy will stop making more ask orders, and if you're above the allowable trading range, then the strategy will stop making more bid orders.
| **filled\_order\_replenish\_wait\_time** | An amount in seconds, which specifies the delay before placing the next order for single order mode. _Default value: 60 seconds_. <br/>
| **enable\_order\_filled\_stop\_cancellation** | When this is `true`, the orders on the side opposite to the filled orders remains uncanceled. _Default value: False_. <br/>
| **best\_bid\_ask\_jump\_mode** | When this is `true`, the bid and ask order prices are adjusted based on the current top bid and ask prices in the market. _Default value: False_. <br/>
| **best\_bid\_ask\_jump\_orders\_depth** | If `best_bid_ask_jump_mode` is `true`, this specifies how deep into the orderbook to go for calculating the top bid and ask prices including the user's active orders. _Default value: 0_. <br/>
| **add\_transaction\_costs** | Parameter to enable/disable adding transaction costs to order prices. _Default value: true_. <br/>
| **external\_pricing\_source** | If external price source will be used for the mid price. _Default value: false_. <br/>
| **external\_price_source\_type** | The type of external pricing source (exchange/feed/custom_api). <br/>
| **external\_price\_source\_exchange** | An external exchange that has the same trading pair. <br/>
| **external\_price\_source\_feed\_base\_asset** | The base asset from data feed, e.g. ETH. <br/>
| **external\_price\_source\_feed\_quote\_asset** | The quote asset from data feed, e.g. USD. <br/>
| **external\_price\_source\_custom\_api** | An API URL that returns price only, i.e. only decimal or whole number is expected. <br/>
