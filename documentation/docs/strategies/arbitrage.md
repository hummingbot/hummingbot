# Arbitrage

## How it Works

Arbitrage is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/whitepaper.pdf).

### Schematic

The diagram below illustrates how arbitrage works.  The transaction involves two exchanges: **Exchange A** and a **Exchange B**. Hummingbot monitors the prices on both exchanges and transacts when a profit opportunity arises.

An opportunity arises when Hummingbot can buy on one exchange at a lower price and sell on the other exchange at a higher price.

<small><center>***Figure 1: Hummingbot completes an arbitrage trade***</center></small>

![Figure 1: Hummingbot completes an arbitrage trade](/assets/img/arbitrage.png)

## Prerequisites: Inventory

1. Similar to cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>` | Enter `arbitrage`. |
| `Import previous configs or create a new config file? (import/create) >>>` | When running the bot for the first time, enter `create`. If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your primary exchange name >>>` | Enter an exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid` *(case sensitive)* |
| `Enter your secondary exchange name >>>` | Enter another exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [primary exchange name] >>>` | Enter the token symbol for the *primary exchange*. |
| `Enter the token symbol you would like to trade on [secondary exchange name] >>>` | Enter the token symbol for the *secondary exchange*. |
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>` | This sets `min_profitability` ([definition](/strategies/arbitrage/#configuration-parameters)). |


## Configuration Parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arbitrage_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **min_profitability** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%).<br/>Minimum required profitability in order for Hummingbot to place an order on the maker exchange. <br/><br/>*Example: Assuming a minimum profitability threshold of `0.01` and a token symbol that has a bid price of 100 on the taker exchange (binance), Hummingbot will place a bid order on the maker exchange (ddex) of 99 (or lower) to ensure a 1% (or better) profit; Hummingbot only places this order if that order is the best bid on the maker exchange.*
| **trade_size_override** | An amount expressed in quote currency of maximum allowable order size.  If not set, the default value is 1/6 of the aggregate value of quote and base currency balances across the maker and taker exchanges.<br/><br/>*Example: Assuming a trade size override of `100` and a token symbol of ETH/DAI, the maximum allowable order size is one that has a value of 100 DAI.*
