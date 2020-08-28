# Celo Arbitrage (`celo-arb`)

**Updated as of v0.28.1**

## How it Works

The `celo-arb` strategy is a special case of the normal [arbitrage](/strategies/arbitrage/) strategy that arbitrages between the automated market maker (AMM) exchange on the Celo blockchain and other markets supported by Hummingbot. This strategy allows users to earn arbitrage profits while contributing to the stability of the Celo cUSD price peg.

For more information, please see this [blog post](https://hummingbot.io/blog/2020-06-celo-arbitrage/).

## Quickstart guide

We have created a [Quickstart guide](./quickstart) for `celo-arb` that walks through the steps of how to install and run Hummingbot along with the Celo ultra-light node on the free tier of an AWS instance.

## Prerequisites

Since Celo is a blockchain protocol, in addition to the normal inventory requirements, you will need access to a Celo node and the `celo-cli` command line tool in the same machine in which you are running the Hummingbot client.

### Inventory of CELO or cUSD

1. Similar to the **arbitrage** strategy, you will need to hold inventory of Celo tokens (i.e. Celo Gold (CELO) or cUSD) in a Celo wallet and on a **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You may also need some CELO tokens in your Celo wallet in order to pay for transaction fees on the Celo blockchain.

### Access to a Celo Node

Celo nodes allow the Hummingbot client to interact with the Celo blockchain by connecting to peers, sending transactions, and fetching chain state. Since the client just needs access to the chain and recent blocks, you can run either a Celo full node or an ultra-light node.

Follow the [Celo documentation](https://docs.celo.org/getting-started/mainnet/running-a-full-node-in-mainnet) to install and run a full node. Note that the node must be synced in order for the `celo-arb` strategy to run. 

!!! tip "Ultra-light sync mode"
    The `celo-arb` strategy works with Celo node running in "ultra-light" mode, which is much faster to sync. See our [Quickstart](./quickstart) for instructions on how to start a node in ultra-light mode.

### `celo-cli` CLI tool

To interact with the Celo node, the Hummingbot client depends upon the `celo-cli` command line tool. Please install `celo-cli` by following these instructions in the Celo documentation.

## Configuration Parameters

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/celo_arb_[#].yml`).

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **secondary_market** | `Enter your secondary exchange name` | Enter another exchange you would like to trade on. |
| **secondary_market_trading_pair** | `Enter the token trading pair you would like to trade on [secondary_market]` | Enter the token trading pair for the secondary exchange. |
| **min_profitability** | `What is the minimum profitability for you to make a trade?` | Minimum profitability target required to execute trades. |
| **order_amount** | `What is the amount of [base_asset] per order?` | Order amount for each leg of the arbitrage trade. |
| **celo_slippage_buffer** | `How much buffer do you want to add to the Celo price to account for slippage (Enter 1 for 1%)?` | Percent buffer added to the Celo exchange price to account for price movement before trade execution |

