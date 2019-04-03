---
type: "docs"
title: "General"
category: "1-FAQs"
category_order: 0
---
# General and Business FAQs

Below is a summary of frequently asked questions regarding Hummingbot.  If you have additional questions or need support, please join the official [Hummingbot Discord server](https://discord.hummingbot.io) or email us at [contact@hummingbot.io](mailto:contact@hummingbot.io). 

## What is Hummingbot?

Hummingbot is open-source trading software developed by [CoinAlpha, Inc.](https://coinalpha.com) that allows users to run a local client that implements market-making trading strategies for cryptocurrencies.

For more detailed information, please read the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf).

## When will Hummingbot be available?

We are launching the Hummingbot Alpha Tester program at the end of February and planning on the general public release for the end of March.

## How can I keep up to date on Hummingbot?

You can sign up for our [mailing list](https://hummingbot.io) or join the official [Hummingbot Discord server](https://discord.hummingbot.io).
 
## Why are you making Hummingbot available to the general public rather than just running it in-house?

- **Mission alignment**: We founded CoinAlpha, the company behind Hummingbot, because we believe that blockchain technology empowers individuals to compete on a level playing field with large financial institutions. Releasing Hummingbot as open source software available to the general public furthers this mission.

- **Decentralized market making**: There are hundreds of fragmented digital asset exchanges in need of liquidity that are underserved by the relatively scarce number of dedicated, professional market makers. At the same time, market making requires dedicated inventory held in reserve on each market served. Given near-infinite combinations of markets, it would be impossible for a single market maker to serve the entire market. A decentralized, community-driven approach allows each market maker to serve the markets where they have comparative advantage. This is a more optimal long-term solution to the crypto industry's [liquidity problem](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

- **Regulatory limitations**: Regulations on cryptocurrencies are still evolving and unclear, which creates particular challenges for trading on an institutional/company basis.  As a technology company, we want to focus on building technology and not spend our time on navigating and monitoring the ever-changing regulations.  

## Why are you making Hummingbot open source?

- **Transparency**: In order to use Hummingbot, users must provide their private keys and exchange API keys.  In a similar way as wallet software, we want users to know how this sensitive information is being used and give them comfort when using Hummingbot; aka, open kimono.

- **Community**: Decentralization, blockchain technology, and cryptocurrencies are built on the idea of community by passionate technologists.  We welcome developers to study the code, suggest improvements, add cool new features, or help identify bugs or any other problems.

## What market making strategy does Hummingbot use?

The current release of Hummingbot comes with two strategies:

| Strategy | Description |
|----|----|
| **Cross exchange market making** | Also referred to as *liquidity mirroring* or *exchange remarketing*.  In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction any filled trades on a more liquid exchange.  <br/><br/>*This strategy has relatively lower risk and complexity as compared to other market making strategies, which we thought would be a good starting point for initial users.* |
| **Arbitrage** | Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other). |

The [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) provides more details about these strategies, as well as additional strategies that we are working on for future versions of Hummingbot.

## What exchanges does Hummingbot support?

Currently we support Binance, Radar Relay, and DDEX.  We are continuing to work on integrating other exchanges and will be continually rolling out additional capabilities once complete.

## How much cryptocurrency do I need to get started?

There is no minimum amount of assets to use Hummingbot.  We would recommend initially starting with smaller amounts of assets while you are getting familiar with the bot.
