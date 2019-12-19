# Bitcoin.com Exchange Connector

## About Bitcoin.com Exchange

Bitcoin.com Exchange is a platform that was recently launched in early September 2019.

It provides trading options with a wide range of [digital assets](https://markets.bitcoin.com/) and have markets denominated in base currencies like Bitcoin (BTC), Bitcoin Cash (BCH), Ethereum (ETH), and Tether (USDT). It aims to offer a user-friendly trading service with high-liquidity and will soon be supporting SLP tokens.


## Using the Connector

Centralized exchanges like [Bitcoin.com](https://exchange.bitcoin.com/) requires your API keys in order to trade using Hummingbot.

```
Enter your bitcoin_com API key >>>
Enter your bitcoin_com secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.


### Creating Bitcoin.com Exchange API keys

1. Log in to https://exchange.bitcoin.com/ or sign up for an account in [this page](https://exchange.bitcoin.com/signupapp) and go to **Settings** which is the gear icon in the upper-right.<br><br>
![bce_settings](/assets/img/bce_settings.png)
2. Under API keys tab click **New API key** to generate your API and secret key.<br><br>
![bce_new_api_key](/assets/img/bce_new_api_key.png)
3. For access rights, make sure to tick the checkboxes as shown in the image above. You will be prompted to enter your 2FA code for each box.

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.


## Miscellaneous Info

### Minimum Order Sizes

An order size of at least 0.001 BTC in value is required to trade on this exchange.


## Transaction Fees

Generally, trading fees are 0.20% for taker and 0.10% for maker orders. You can check this through REST API reference.

```
https://api.exchange.bitcoin.com/api/2/public/symbol
```

The trading pair symbol can also be added to the URL to be more specific.

For example, `GET /api.exchange.bitcoin.com/api/2/public/symbol/ETHBCH` returns JSON structured like this:

```
{
    "id": "ETHBCH",
    "baseCurrency": "ETH",
    "quoteCurrency": "BCH",
    "quantityIncrement": "0.0001",
    "tickSize": "0.00001",
    "takeLiquidityRate": "0.002",
    "provideLiquidityRate": "0.001",
    "feeCurrency": "BCH"
}
```

`takeLiquidityRate` is the taker fee while `provideLiquidityRate` is the maker fee in `feeCurrency` value.