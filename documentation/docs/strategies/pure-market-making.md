# Pure market making

## How it works

In the pure market making strategy, the user keeps posting limit bid and ask offers on a market and expects other users to fill their orders. 
You have control over how far away from the mid price your posted bid and asks are, whats the order quantity and how often you want to cancel and replace them.  

!!! warning
    Please exercise caution while running this strategy and set appropriate stop loss limits. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications will likely lose money.

### Schematic

The diagram below illustrates how market making works.  Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites: Inventory

1. You will need to hold inventory of quote and base currencies on the exchange.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.
    
  | Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `pure_market_making`.<br/><br/>Currently available options: `cross_exchange_market_making` or `arbitrage` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your maker exchange name >>>`: | In the pure market making strategy, the *maker exchange* is the exchange where the bot will place bid and offer orders.<br/><br/>Currently available options: `binance` or `coinbase_pro` or `radar_relay` or `ddex` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [maker exchange name] >>>`: | Enter the token symbol for the *maker exchange*.<br/>Example input: `ZRX-WETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that the pair is a valid pair for the exchange, for example, use `WETH` instead of `ETH`.</td></tr></tbody></table> |
| `What is your preferred quantity per order (denominated in the base asset, default is 1)? >>>`: | This sets `order_amount` (see [definition](/strategies/pure-market-making/#configuration-parameters)). |
| `How far away from the mid price do you want to place the next bid (Enter 0.01 to indicate 1%)? >>>`: | This sets `bid_place_threshold` (see [definition](/strategies/pure-market-making/#configuration-parameters)). |
| `How far away from the mid price do you want to place the next ask (Enter 0.01 to indicate 1%)? >>>`: | This sets `ask_place_threshold` (see [definition](/strategies/pure-market-making/#configuration-parameters)). |
| `How often do you want to cancel and replace bids and asks (in seconds)? >>>`: | This sets the `cancel_order_wait_time` (see [definition](/strategies/pure-market-making/#configuration-parameters)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see [Installation: Setting up your Ethereum node](/installation/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |


## Configuration parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_pure_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **order_amount** | The order amount for the limit bid and ask orders. <br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place orders if you do not have sufficient balance for both sides of the order <br/>
| **bid_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%) <br/> The strategy will place the buy(bid) order 1% away from the mid price if set to 0.01 <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set bid_place_threshold to 0.1 which is 10%, it will place your buy order (bid) at 10% below mid price of 100 which is 90.*
| **ask_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%) <br/> The strategy will place the sell(ask) order 1% away from the mid price if set to 0.01 <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set ask_place_threshold to 0.1 which is 10%, it will place your sell order (ask) at 10% above mid price of 100 which is 110.*
| **cancel_order_wait_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 60 seconds_. <br/><br/> The limit bid and ask orders are cancelled and new bids and asks are placed according to the current mid price and settings at this interval.

