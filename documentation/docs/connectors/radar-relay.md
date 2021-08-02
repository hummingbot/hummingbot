# Radar Relay

[Radar Relay](https://radarrelay.com/) is an exchange application specializing in ERC-20 tokens that uses the [0x Protocol](https://0x.org/). Founded in 2017, it is a newer exchange that has rapidly gained users and features continuous trading with its off-chain order book.

## Using the connector

Because Radar Relay is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node in order to use Hummingbot. See below for information on how to create these:

- [Creating a crypto wallet](/operation/connect-exchange/#wallets)
- [Creating an ethereum node](/operation/connect-exchange/#setup-ethereum-nodes)

## Miscellaneous info

### Minimum Order size

Each trading pair has a unique minimum order size denominated in the _base currency_. You can access the minimum order size for a specific token pair using Radar Relay's API **(Broken Link as of June 01,2021)**, at the following URL:

```
https://api.radarrelay.com/v3/markets/{marketId}
```

For example, for `ZRX-WETH`, navigate to: [https://api.radarrelay.com/v3/markets/**`ZRX-WETH`**](https://api.radarrelay.com/v3/markets/ZRX-WETH).

Sample output:

```
{
  "id": "ZRX-WETH",
  "displayName": "ZRX/WETH",
  "baseTokenAddress": "0xe41d2489571d322189246dafa5ebde1f4699f498",
  "quoteTokenAddress": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
  "baseTokenDecimals": 18,
  "quoteTokenDecimals": 18,
  "quoteIncrement": 8,
  "minOrderSize": "0.04568281", <== ** MINIMUM ORDER SIZE **
  "maxOrderSize": "1000000000",
  "score": 66.7,
  "active": 1
}
```

In this example, the minimum order size is 0.04568281 ZRX.

For additional information, see [this page](https://support.radarrelay.com/en/support/solutions/articles/42000022036-do-you-have-a-minimum-or-maximum-order-size-). For the most part, the smallest order size allowed is about the equivalent of \$1.

> > > > > > > 647191f9e2011a278bfb792cfb96f5dbd26eeec2:content/spot-connectors/radar-relay.mdx

### Transaction fees

Presently, Radar Relay does [not charge](https://support.radarrelay.com/en/support/solutions/articles/42000022033-what-are-your-fees-) trading or withdrawal fees, and the only additional cost for transactions is the gas network costs. This may change in the future as the exchange develops a larger user base.
