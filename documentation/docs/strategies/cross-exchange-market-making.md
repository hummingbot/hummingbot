# Cross exchange market making

## How it works

Cross exchange market making is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/whitepaper.pdf).

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

## Prerequisites: Inventory

1. For cross-exchange market making, you will need to hold inventory on two exchanges, one where the bot will make a market (the **maker exchange**) and another where the bot will source liquidity and hedge any filled orders (the **taker exchange**).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

Initially, we assume that the maker exchange is an Ethereum-based decentralized exchange and that the taker exchange is Binance.

## Configuration walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `cross_exchange_market_making`.<br/><br/>Currently available options: `cross_exchange_market_making` or `arbitrage` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your maker exchange name >>>`: | In the cross-exchange market making strategy, the *maker exchange* is the exchange where the bot will place maker orders.<br/><br/>Currently available options: `radar_relay` or `ddex` *(case sensitive)* |
| `Enter your taker exchange name >>>`: | In the cross-exchange market making strategy, the *taker exchange* is the exchange where the bot will place taker orders.<br/><br/>Currently available option: `binance` *(case sensitive)*|
| `Enter the token symbol you would like to trade on [maker exchange name] >>>`: | Enter the token symbol for the *maker exchange*.<br/>Example input: `ZRX-WETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that the pair is a valid pair for the exchange, for example, use `WETH` instead of `ETH`.</td></tr></tbody></table> |
| `Enter the token symbol you would like to trade on [taker exchange name] >>>`: | Enter the token symbol for the *taker exchange*.<br/>Example input: `ZRX-ETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that (1) the pair corresponds with the token symbol entered for the maker exchange, and that (2) is a valid pair for the exchange.  *Note in the example, the use of `ETH` instead of `WETH`*.</td></tr></tbody></table>|
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>`: | This sets `min_profitability` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `Do you want to actively adjust/cancel orders (Default True) >>>`: | This sets `active_order_canceling` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is the minimum profitability to actively cancel orders? (Default to 0.0, only specify when active_order_cancelling is disabled, value can be negative) >>>`: | This sets the `cancel_order_threshold` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is the minimum limit order expiration in seconds? (Default to 130 seconds) >>>`: | This sets the `limit_order_min_expiration` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see [Installation: Setting up your Ethereum node](/installation/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |

## Configuration parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_cross_exchange_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **min_profitability** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%).<br/>Minimum required profitability in order for Hummingbot to place an order on the maker exchange. <br/><br/>*Example: assuming a minimum profitability threshold of `0.01` and a token symbol that has a bid price of 100 on the taker exchange (binance), Hummingbot will place a bid order on the maker exchange (ddex) of 99 (or lower) to ensure a 1% (or better) profit; Hummingbot only places this order if that order is the best bid on the maker exchange.*
| **active_order_canceling** | `True` or `False`<br/>If enabled (parameter set to `True`), Hummingbot will cancel that become unprofitable based on the `min_profitability` threshold.  If this is set to `False`, Hummingbot will allow any outstanding orders to expire, unless `cancel_order_threshold` is reached.
| **cancel_order_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which can be 0 or negative.<br/>When active order canceling is set to `False`, if the profitability of an order falls below this threshold, Hummingbot will cancel an existing order and place a new one, if possible.  This allows the bot to cancel orders when paying gas to cancel (if applicable) is a better than incurring the potential loss of the trade.
| **limit_order_min_expiration** | An amount in seconds, which is the minimum duration for any placed limit orders. _Default value: 130 seconds_.
| **top_depth_tolerance** | An amount expressed in quote currency of maximum aggregate amount of orders at a better price than Hummingbot's order that are allowed before Hummingbot modifies its order.<br/><br/>*Example: assuming a top depth tolerance of `100` and a Hummingbot bid price of 20, if there exist an aggregate amount of orders of more than 100 at a better (higher) price than Hummingbot's bid, Hummingbot will cancel its order at 20 and re-evaluate the next opportunity to place a new bid.*
| **trade_size_override** | An amount expressed in quote currency of maximum allowable order size.  If not set, the default value is 1/6 of the aggregate value of quote and base currency balances across the maker and taker exchanges.<br/><br/>*Example: assuming a trade size override of `100` and a token symbol of ETH/DAI, the maximum allowable order size is one that has a value of 100 DAI.*

