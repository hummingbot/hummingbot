# Connectors

This section contains information about official connectors for individual exchanges and protocols, including:

* General information
* Setup and configuration
* Minimum order sizes, fees, etc.

## What are Connectors?

Connectors are packages of code that link Hummingbot's internal trading algorithms with live information from different cryptocurrency exchanges. They interact with a given exchange's API, such as by gathering order book data and sending and cancelling trades. See below for the list of exchanges which Hummingbot currently has connectors to.

## Hummingbot-Supported Connectors

* [Binance](/connectors/binance)
* [Bittrex Global](/connectors/bittrex)
* [Coinbase Pro](/connectors/coinbase)
* [Eterbase](/connectors/eterbase)
* [Huobi Global](/connectors/huobi)
* [Kraken](/connectors/kraken)
* [KuCoin](/connectors/kucoin)
* [Liquid](/connectors/liquid)
* [Radar Relay](/connectors/radar-relay)

## Community-Contributed Exchange Connectors

| Exchange | Github Contact | Support Contact | Last Version Tested | Last Updated | Status | Known Issues |
| --- |:---:|:---:|:---:|:---:|:---:|:---:|
| Bamboo Relay | [Arctek](https://github.com/Arctek) | [Online Chat](https://bamboorelay.com/) | 0.21.0 | 0.21.0 | <span style="color:green; font-size:25px">⬤</span> |  |
| Dolomite | [zrubenst](https://github.com/zrubenst) | [Telegram](https://t.me/dolomite_official) | 0.20.0 | 0.21.0 | <span style="color:green; font-size:25px"> ⬤</span> |  |

* Last Version Tested - Last reported Hummingbot version that the exchange connector maintainer has confirmed has been tested and is operational.
* Last Updated - Last Hummingbot release which included an update to the exchange connector code.

### Exchange Connector Specific Support

Please contact the support contact listed in the above table for support questions that are specific for that exchange.

### Reporting an Issue with a Community-Contributed Connector

1. Create a Github issue and tag the Github contact to inform them of the issue.
1. Report the issue to the exchange connector support contact.
1. Send a message through Discord in [#community-connectors](https://discordapp.com/channels/530578568154054663/642099307922718730) channel.


## Coming Soon to Hummingbot

* Bitfinex
* HitBTC
