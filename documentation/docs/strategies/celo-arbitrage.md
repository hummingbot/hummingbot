# Celo Arbitrage

**Updated as of v0.28.1**

!!! warning
    The Celo Arbitrage Strategy could not be used on Binary Installers since it would need a [gateway](/installation/gateway/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

## Prerequisites

Since Celo is a blockchain protocol, in addition to the normal inventory requirements, you will need access to a Celo node and the `celo-cli` command line tool in the same machine in which you are running the Hummingbot client.

See [Celo](/protocol-connectors/celo) for more information.

## Configuration parameters

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/celo_arb_[#].yml`).

### `secondary_market`

Enter another exchange you would like to trade on.

** Prompt: **

```json
Enter your secondary exchange name
>>>
```

### `secondary_market_trading_pair`

Enter the token trading pair for the secondary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on [secondary_market]
>>>
```

### `min_profitability`

Minimum profitability target required to execute trades.

** Prompt: **

```json
What is the minimum profitability for you to make a trade?
>>>
```

### `order_amount`

Order amount for each leg of the arbitrage trade.

** Prompt: **

```json
What is the amount of [base_asset] per order?
>>>
```

### `celo_slippage_buffer`

Percent buffer added to the Celo exchange price to account for price movement before trade execution

** Prompt: **

```json
How much buffer do you want to add to the Celo price to account for slippage (Enter 1 for 1%)?
>>> 1
```
