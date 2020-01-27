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

Each trading pair has a unique minimum order size denominated in the *base currency*.  You can access the minimum order size for a specific token pair using the following public API:

```
https://api.ddex.io/v3/markets
```

You can also add the trading pair at the end of the URL to make it more specific.

```
https://api.ddex.io/v3/markets/WETH-USDT
```

For example, trading pair `WETH-USDT` minimum order size is 0.01 WETH.

```
"status": 0,
"desc": "success",
"data": {
    "market": {
        "id": "WETH-USDT",
        "baseToken": "WETH",
        "baseTokenProjectUrl": "https://weth.io/",
        "baseTokenName": "Wrapped Ether",
        "baseTokenDecimals": 18,
        "baseTokenAddress": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
        "baseTokenDisplaySymbol": null,
        "quoteToken": "USDT",
        "quoteTokenDecimals": 6,
        "quoteTokenAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "quoteTokenDisplaySymbol": null,
        "minOrderSize": "0.010000000000000000",
        "pricePrecision": 5,
        "priceDecimals": 2,
        "amountDecimals": 2,
        "asMakerFeeRate": "0.00100",
        "asTakerFeeRate": "0.00300",
        "gasFeeAmount": "0.25795607384814000349",
        "supportedOrderTypes": [
            "limit"
        ],
        "marketOrderMaxSlippage": "0.10000"
    }
}
```

!!! tip
    See troubleshooting section on how to [Get REST API data using Postman](/support/how-to/#get-rest-api-data-using-postman).

In this example, the minimum order size is 0.5 WETH.

### Transaction Fees

The standard charge for transactions on DDEX is 0.1% for market makers and 0.3% for market takers. However, high volume market makers and hydro protocol token holders can receive discounted trading fees. More details can be on the DDEX [trading fees page](https://ddex.zendesk.com/hc/en-us/articles/115004535333-DDEX-1-0-Fees-Update).
