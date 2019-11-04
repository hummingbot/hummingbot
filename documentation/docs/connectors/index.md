# Connectors

This section contains information about official connectors for individual exchanges and protocols, including:

* General information
* Setup and configuration
* Minimum order sizes, fees, etc.

## What are Connectors?

Connectors are packages of code that link Hummingbot's internal trading algorithms with live information from different cryptocurrency exchanges. They interact with a given exchange's API, such as by gathering order book data and sending and cancelling trades. See below for the list of exchanges which Hummingbot currently has connectors to.

## Hummingbot-Supported Connectors

### Centralized Exchanges

* [Binance](/connectors/binance)
* [Coinbase Pro](/connectors/coinbase)
* [Huobi Global](/connectors/huobi)
* [Bittrex International](/connectors/bittrex)

### Decentralized Exchanges

* [DDEX](/connectors/ddex)
* [IDEX](/connectors/IDEX)
* [Radar Relay](/connectors/radar-relay)
* [0x Relayers](/connectors/0x)

## Community-Contributed Exchange Connectors

| Exchange | Gitcoin Bounty | Github Contact | Support Contact | Last Version Tested | Last Updated | Status | Known Issues |
| --- |:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Bamboo Relay | NA | [Arctek](https://github.com/Arctek) | [Online Chat](https://bamboorelay.com/) | 0.18.0 | 0.17.1 | <span style="color:green">⬤</span> | [782](https://github.com/CoinAlpha/hummingbot/issues/782) |
| Dolomite | NA | [zrubenst](https://github.com/zrubenst) | [Telegram](https://t.me/dolomite_official) | [ TBD ] | 0.18.0 | <span style="color:yellow"> ⬤</span> | |

### Last Version Tested

Last reported Hummingbot version that the exchange connector maintainer has confirmed has been tested and is operational.

### Last Updated

Last Hummingbot release which included an update to the exchange connector code.

### Exchange Connector Specific Support

Please contact the support contact listed in the above table for support questions that are specific for that exchange.

### Reporting an Issue with a Community-Contributed Connector

1. Create a Github issue and tag the Github contact to inform them of the issue.
1. Report the issue to the exchange connector support contact.


## Coming Soon to Hummingbot

* Bitfinex
* Kraken
* Bitmex
* Binance DEX
