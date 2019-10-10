# DDEX Connector

## About DDEX

[DDEX](https://ddex.io) is a popular decentralized exchange that uses the [Hydro Protocol](https://hydroprotocol.io/). Known for being user-friendly, it specializes in trading Ethereum and ERC-20 tokens.

## Using the Connector

Because DDEX is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node in order to use Hummingbot. See below for information on how to create these:

* [Creating a crypto wallet](/installation/wallet)
* [Creating an ethereum node](/installation/node/node)

## Miscellaneous Info

### Minimum Order Size

Minimum order sizes on DDEX typically range between $15 to $20.

Each trading pair has a unique minimum order size denominated in the *base currency*.  You can access the minimum order size for a specific token pair using the following URL:

```
https://api.ddex.io/v3/markets/:marketId
```

For example, for `WETH-DAI`, navigate to: [https://api.ddex.io/v3/markets/**`WETH-DAI`**](https://api.ddex.io/v3/markets/WETH-DAI).

Sample output:

```
{
  "status": 0,
  "desc": "success",
  "data": {
    "market": {
      "id": "WETH-DAI",
      "baseToken": "WETH",
      "baseTokenProjectUrl": "https://weth.io/",
      "baseTokenName": "Wrapped Ether",
      "baseTokenDecimals": 18,
      "baseTokenAddress": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
      "baseTokenDisplaySymbol": null,
      "quoteToken": "DAI",
      "quoteTokenDecimals": 18,
      "quoteTokenAddress": "0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359",
      "quoteTokenDisplaySymbol": null,
      "minOrderSize": "0.050000000000000000", <== ** MINIMUM ORDER SIZE **
      "pricePrecision": 5,
      "priceDecimals": 2,
      "amountDecimals": 2,
      "asMakerFeeRate": "0.00100",
      "asTakerFeeRate": "0.00300",
      "gasFeeAmount": "0.3295179490594733939",
      "supportedOrderTypes": ["limit", "market"],
      "marketOrderMaxSlippage": "0.10000"
    }
  }
}
```

In this example, the minimum order size is 0.5 WETH.

### Transaction Fees

The standard charge for transactions on DDEX is 0.1% for market makers and 0.3% for market takers. However, high volume market makers and hydro protocol token holders can receive discounted trading fees. More details can be on the DDEX [trading fees page](https://ddex.zendesk.com/hc/en-us/articles/115004535333-DDEX-1-0-Fees-Update).
