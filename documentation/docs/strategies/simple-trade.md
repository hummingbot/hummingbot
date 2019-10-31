# Simple Trade

## How it Works

In the Simple Trade strategy, Hummingbot executes orders after a certain time delay, as specified by the user. For limit orders, the strategy also provides the user with the additional option to cancel them after a certain time period.

!!! warning
    The strategy is only supposed to provide the user with a basic template for developing custom strategies. Please set variables responsibly.

## Prerequisites: Inventory

1. You will need to hold inventory of currencies on the exchange on which you are trading.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

  | Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>` | Enter `simple_trade`. |
| `Import previous configs or create a new config file? (import/create) >>>` | When running the bot for the first time, enter `create`. If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter the name of the exchange >>>` | The exchange where the bot will place the orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [market] >>>` | Enter the token symbol for the *exchange*.<br/>Example input: `ETH-USD`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: options available are based on each exchange's methodology for labeling currency pairs. Ensure that the pair is a valid pair for the selected exchange.</td></tr></tbody></table> |
| `Enter type of order (limit/market) default is market >>> " >>>` | `limit` or `market`<br /> Specify if you would like to place a limit order or market order. See [additional configuration for limit orders](#limit-order-configuration).|
| `What is your preferred quantity per order (denominated in the base asset, default is 1)? >>>` | This sets `order_amount` ([definition](#configuration-parameters)). |
| `Enter True for Buy order and False for Sell order (default is Buy Order) >>>` | This sets `is_buy` (see [definition](#configuration-parameters)). |
| `How much do you want to wait to place the order (Enter 10 to indicate 10 seconds. Default is 0)? >>> ` | This sets `time_delay` ([definition](#configuration-parameters)). |


### Limit Order Configuration

Limit orders allow you to specify the price at which you want to place the order and specify how long to wait before cancelling the order.

 | Prompt | Description |
|-----|-----|
| `What is the price of the limit order ? >>> ` | This sets `order_price` ([definition](#configuration-parameters)). |
| `How long do you want to wait before cancelling your limit order (in seconds). (Default is 60 seconds) ? >>> `: | This sets the `cancel_order_wait_time` ([definition](#configuration-parameters)). |

## Configuration parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_simple_trade_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **order_type**<br /> | Specify whether its a limit or Market order. <br/> Limit orders allow you to specify price in addition to the order amount & are placed on the orderbook. Market orders are executed immediately against existing limit orders in the orderbook. <br/>
| **order_amount**<br /> | The amount for the limit or market order. <br/> Ensure you have enough quote (or) base tokens to place the orders. The strategy will not place orders if you do not have sufficient balance for the order. <br/>
| **order_price**<br /> | The price for the limit order. <br/> Specify the price at which are you are willing to buy/sell the tokens <br/>
| **cancel_order_wait_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 60 seconds_. For limit orders, the orders (if still open) are cancelled after this time.
| **time_delay** | An amount in seconds, after which orders are executed from the start of the strategy. _Default value: 0 seconds_. Orders are placed immediately after strategy is initialized by default.
| **is_buy** | Specify as a buy or sell order (True: Buy order. False: Sell Order) <br/>
