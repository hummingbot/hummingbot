# KuCoin

KuCoin is a centralized exchange based in Hong Kong that opened for cryptocurrency trading in September 2017. Nicknamed the "People's Exchange"​, Kucoin is claimed to be easy to use for novice investors while being in-depth enough for crypto enthusiasts.

KuCoin claims to have one of the world’s most impressive trading pair selections, a wide range of altcoins with more than 300 trading pairs and regularly adding new pairs. The exchange also has its cryptocurrency, [KuCoin Tokens (KCS)](https://coinmarketcap.com/currencies/kucoin-token/).

## Using the Connector

Because [KuCoin](https://www.kucoin.com/) is a centralized exchange, you will need to generate and provide your API keys to trade using Hummingbot.

```
Enter your KuCoin API key >>>
Enter your KuCoin secret key >>>
Enter your KuCoin passphrase >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support section.

### Creating KuCoin API keys

This FAQ article below in their documentation shows step-by-step instructions on how to create API keys in the KuCoin exchange.

- [How to create an API](https://kucoin.zendesk.com/hc/en-us/articles/360015102174-How-to-Create-an-API)

!!! warning
    For API key permissions, we recommend using #general#, and #trade# enabled API keys; enabling #withdraw, transfer or the equivalent is unnecessary# for current Hummingbot strategies.

![](/assets/img/kucoin_api.png)

## Miscellaneous info

### Main account to trading account

Transfer desired assets to use for trading in Kucoin and for the assets to reflect when running the `balance` command in hummingbot client.

![](/assets/img/main_to_trading.gif)

### Minimum order sizes

Minimum order size varies per market. All minimum trade quantities can be found in the following public API:

```
https://api.kucoin.com/api/v1/symbols
```

The size must be greater than the `baseMinSize` for the symbol and no larger than the `baseMaxSize`. For example, trading pair ETH-USDT minimum order size is 0.0001 ETH.

```
"symbol": "ETH-USDT",
"quoteMaxSize": "999999999",
"enableTrading": true,
"priceIncrement": "0.01",
"feeCurrency": "USDT",
"baseMaxSize": "10000000000",
"baseCurrency": "ETH",
"quoteCurrency": "USDT",
"market": "USDS",
"quoteIncrement": "0.000001",
"baseMinSize": "0.0001",
"quoteMinSize": "0.01",
"name": "ETH-USDT",
"baseIncrement": "0.0000001",
"isMarginEnabled": true
```

### Transaction fees

Generally, KuCoin charges 0.10% on both maker and taker, while a user can get a 20% discount on trading fees if paid in KCS. However, users who trade high volumes and own substantial amounts of KuCoin Shares can receive more discounts.

Read through their articles below related to trading fees and rebates.

- [VIP Level](https://www.kucoin.com/vip/level)
- [Pay Fees via KCS & Enjoy 20% Off](https://kucoin.zendesk.com/hc/en-us/articles/360037007974-Pay-Fees-via-KCS-Enjoy-20-Off)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
