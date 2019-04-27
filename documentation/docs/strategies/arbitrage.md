# Arbitrage

## How it works

Arbitrage is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/whitepaper.pdf).

### Schematic

The diagram below illustrates how arbitrage works.  The transaction involves two exchanges: **Exchange A** and a **Exchange B**. Hummingbot monitors the prices on both exchanges and transacts when a profit opportunity arises.

An opportunity arises when Hummingbot can buy on one exchange at a lower price and sell on the other exchange at a higher price.

<small><center>***Figure 1: Hummingbot completes an arbitrage trade***</center></small>

![Figure 1: Hummingbot completes an arbitrage trade](/assets/img/arbitrage.png)

## Prerequisites: Inventory

1. Similar to cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `arbitrage`.<br/><br/>Currently available options: `cross_exchange_market_making` or `arbitrage` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your primary exchange name >>>`: | Enter an exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay` or `ddex` *(case sensitive)* |
| `Enter your secondary exchange name >>>`: | Enter another exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay` or `ddex` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [primary exchange name] >>>`: | Enter the token symbol for the *primary exchange*. |
| `Enter the token symbol you would like to trade on [secondary exchange name] >>>`: | Enter the token symbol for the *secondary exchange*. |
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>`: | This sets `min_profitability` (see [definition](/strategies/arbitrage/#configuration-parameters)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see [Installation: Setting up your Ethereum node](/installation/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |

## Configuration parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arbitrage_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **min_profitability** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%).<br/>Minimum required profitability in order for Hummingbot to place an order on the maker exchange. <br/><br/>*Example: assuming a minimum profitability threshold of `0.01` and a token symbol that has a bid price of 100 on the taker exchange (binance), Hummingbot will place a bid order on the maker exchange (ddex) of 99 (or lower) to ensure a 1% (or better) profit; Hummingbot only places this order if that order is the best bid on the maker exchange.*
| **trade_size_override** | An amount expressed in quote currency of maximum allowable order size.  If not set, the default value is 1/6 of the aggregate value of quote and base currency balances across the maker and taker exchanges.<br/><br/>*Example: assuming a trade size override of `100` and a token symbol of ETH/DAI, the maximum allowable order size is one that has a value of 100 DAI.*


