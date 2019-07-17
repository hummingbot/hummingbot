# Bamboo Relay Connector

## About Bamboo Relay

[Bamboo Relay](https://bamboorelay.com/) is an exchange application specializing in ERC-20 tokens that uses the [0x Protocol](https://0x.org/). 
 Currently, Bamboo Relay allows any user to connect their wallet and trade between any coin pair combination. 

## Using the Connector

Because Bamboo Relay is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node in order to use Hummingbot. See below for information on how to create these:

* [Creating a crypto wallet](/installation/wallet)
* [Creating an ethereum node](/installation/node/node)

## Connector Operating Modes

The Bamboo Relay connector supports two modes of operation, [open order book](https://0x.org/wiki#Open-Orderbook) and [coordinated order book](https://github.com/0xProject/0x-protocol-specification/blob/master/v2/coordinator-specification.md).

Open order book mode allows for off-chain orders to be submitted and any taker to fill these orders on-chain.
Orders may only be cancelled by submitting a transaction and paying gas network costs.

The coordinated order book mode extends the open order book mode by adding the ability to soft-cancel orders and a selective delay on order fills, while preserving network and contract fillable liquidity.
This is achieved by the use of a coordinator server component and coordinator smart contracts.

## Pre-emptive Cancels

The Bamboo Relay front-end UI does not show orders that have less than 30 seconds expiry remaining. This is so that users should only attempt to fill orders that have a reasonable chance of succeeding.

When running the connector in coordinated mode it is advised to enable this setting so that orders are automatically refreshed when they have 30 seconds remaining.

## Miscellaneous Info

### DAI-WETH Pair

Currently the DAI-WETH pair is incompatible with WETH-DAI pairs across other exchanges. Exercise caution if using this pair within a strategy.

### Minimum Order Sizes

The minimum acceptable order size is 0.00000001 normalized units of price, amount or total, which ever of these is the lowest.

### Transaction Fees

Currently Bamboo Relay does not charge trading or withdrawal fees, and the only additional cost for transactions is the gas network costs. This may change in the future as the exchange develops a larger user base.
