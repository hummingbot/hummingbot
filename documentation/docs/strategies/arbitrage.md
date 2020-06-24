# Arbitrage

## How it Works

Arbitrage is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/hummingbot.pdf).

### Schematic

The diagram below illustrates how arbitrage works.  The transaction involves two exchanges: **Exchange A** and a **Exchange B**. Hummingbot monitors the prices on both exchanges and transacts when a profit opportunity arises.

An opportunity arises when Hummingbot can buy on one exchange at a lower price and sell on the other exchange at a higher price.

<small><center>***Figure 1: Hummingbot completes an arbitrage trade***</center></small>

![Figure 1: Hummingbot completes an arbitrage trade](/assets/img/arbitrage.png)

## Prerequisites: Inventory

1. Similar to cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration Parameters and Walkthrough

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/arb_[#].yml`).

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **primary_market** | `Enter your primary exchange name` | Enter an exchange you would like to trade on. |
| **secondary_market** | `Enter your secondary exchange name` | Enter another exchange you would like to trade on. |
| **primary_market_trading_pair** | `Enter the token trading pair you would like to trade on [primary_market]` | Enter the token trading pair for the primary exchange. |
| **secondary_market_trading_pair** | `Enter the token trading pair you would like to trade on [secondary_market]` | Enter the token trading pair for the secondary exchange. |
| **min_profitability** | `What is the minimum profitability for you to make a trade?` | Minimum profitability target required to execute trades. |
<br/>
!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.
