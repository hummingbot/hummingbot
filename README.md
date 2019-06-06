![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![CircleCI](https://circleci.com/gh/CoinAlpha/hummingbot.svg?style=svg&circle-token=c9c4825f21e34926ac8a406eeb260ddee0f726ff)](https://circleci.com/gh/CoinAlpha/hummingbot)
[![Jenkins](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-stable&subject=jenkins:stable)](https://jenkins-hb.coinalpha.com/job/hb_test-stable)
[![Discord](https://img.shields.io/discord/530578568154054663.svg?color=768AD4&label=discord&logo=https%3A%2F%2Fdiscordapp.com%2Fassets%2F8c9701b98ad4372b58f13fd9f65f966e.svg)](https://discord.hummingbot.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/CoinAlpha/hummingbot/blob/master/LICENSE)
[![Twitter Follow](https://img.shields.io/twitter/follow/hummingbot_io.svg?style=social&label=hummingbot)](https://twitter.com/hummingbot_io)

Hummingbot is an open-source project that integrates cryptocurrency trading on both **centralized exchanges** and **decentralized protocols**. It allows users to run a client that executes customized, automated trading strategies for cryptocurrencies.

We created hummingbot to promote **decentralized market-making**: enabling members of the community to contribute to the liquidity and trading efficiency in cryptocurrency markets. For more detailed information, please visit the [Hummingbot website](https://hummingbot.io) and read the [Hummingbot whitepaper](https://hummingbot.io/whitepaper.pdf).

- [Join our community](https://discord.coinalpha.com)
- [Documentation](https://docs.hummingbot.io)
- [Follow us on Twitter](https://twitter.com/hummingbot_io)
- [Read our blog](https://www.hummingbot.io/blog)

## Supported cryptocurrency exchanges

| logo | id | name | ver | doc|
|:---:|:---:|:---:|:---:|:---:|
| [![binance](https://i.ibb.co/m0YDQLd/Screen-Shot-2019-03-14-at-10-53-42-AM.png)](https://www.binance.com/?ref=10205187) | binance | [Binance](https://www.binance.com/) | * | [API](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-exchange_binance&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-exchange_binance/) |
| [![Radar Relay](https://i.ibb.co/7RW75mf/Screen-Shot-2019-03-14-at-10-47-07-AM.png)](https://radarrelay.com/) | radar_relay | [Radar Relay](https://radarrelay.com/) | 2 | [API](https://developers.radarrelay.com/api/trade-api) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-exchange_radar_relay&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-exchange_radar_relay/) |
| [![DDEX](https://i.ibb.co/Lrpps2G/Screen-Shot-2019-03-14-at-10-39-23-AM.png)](https://ddex.io/) | ddex | [DDEX](https://ddex.io/) | 3 | [API](https://docs.ddex.io/) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-exchange_ddex&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-exchange_ddex/) |
| [![COINBASE](https://i.ibb.co/h9JdGDW/cbp.jpg)](https://pro.coinbase.com/) | coinbase_pro | [Coinbase Pro](https://pro.coinbase.com/) | * | [API](https://docs.pro.coinbase.com/) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-exchange_coinbase&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-exchange_coinbase/) |

## Currently available strategies

| Strategy | Test |
|--|--|
| [Cross exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-strategy_xemm&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-strategy_xemm/) |
| [Arbitrage](https://docs.hummingbot.io/strategies/arbitrage/) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-strategy_arbitrage&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-strategy_arbitrage/) |
| [Discovery](https://docs.hummingbot.io/strategies/discovery/) | [![Build Status](https://jenkins-hb.coinalpha.com/buildStatus/icon?job=hb_test-strategy_discovery&subject=test)](https://jenkins-hb.coinalpha.com/job/hb_test-strategy_discovery/) |

## Project Breakdown
```
hummingbot/
    client/                         # CLI related files
    core/ 
        cpp/                        # high performance data types written in .cpp
        data_type/                  # key data 
        event/                      # defined events and event-tracking related files
        utils/                      # helper functions and bot plugins      
    data_feed/                      # price feeds such as CoinCap
    market/                         # connectors to individual exchanges
        <market_name>/
            *market                 # handles trade execution (buy/sell/cancel)
            *data_source            # initializes and maintains a websocket connect
            *order_book             # takes order book data and formats it with a standard API                 
            *order_book_tracker     # maintains a copy of the market's real-time order book    
            *active_order_tracker   # for DEXes that require keeping track of                  
            *user_stream_tracker    # tracker that process data specific to the user running the bot
    notifier/                       # connectors to services that sends notifications such as Telegram
    strategy/                       # high level strategies that works with every market
    wallet/                         # files that reads from and submit transactions to blockchains
        ethereum/                   # files that interact with the ethereum blockchain

```
## Install Hummingbot
See [Installation Guide](https://docs.hummingbot.io/installation/).

## Learn more
See [FAQs](https://docs.hummingbot.io/faq/).

## Contributing

We welcome code contributions (via [pull requests](./pulls)) as well as bug reports and feature requests through [github issues](./issues).

When doing so, please review the [contributing guidelines](CONTRIBUTING.md).

## Contact
Hummingbot was created and is maintained by [CoinAlpha](https://www.coinalpha.com). 

You can contact us at [dev@coinalpha.com](mailto:dev@coinalpha.com) or join our [Discord server](https://discord.coinalpha.com).

For business inquiries, please contact us at [partnerships@hummingbot.io](mailto:partnerships@hummingbot.io).

