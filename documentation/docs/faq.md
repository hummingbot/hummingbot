# FAQ

Below is a summary of frequently asked questions regarding Hummingbot.  If you have additional questions or need support, please join the official [Hummingbot Discord server](https://discord.hummingbot.io) or email us at [contact@hummingbot.io](mailto:contact@hummingbot.io). 

## General

### What is Hummingbot?

Hummingbot is open-source trading software developed by [CoinAlpha, Inc.](https://coinalpha.com) that allows users to run a local client that implements market-making trading strategies for cryptocurrencies.

For more detailed information, please read the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf).

### How can I keep up to date on Hummingbot?

You can sign up for our [mailing list](https://hummingbot.io) or join the official [Hummingbot Discord server](https://discord.hummingbot.io).
 
### Why are you making Hummingbot available to the general public rather than just running it in-house?

- **Mission alignment**: We founded CoinAlpha, the company behind Hummingbot, because we believe that blockchain technology empowers individuals to compete on a level playing field with large financial institutions. Releasing Hummingbot as open source software available to the general public furthers this mission.

- **Decentralized market making**: There are hundreds of fragmented digital asset exchanges in need of liquidity that are underserved by the relatively scarce number of dedicated, professional market makers. At the same time, market making requires dedicated inventory held in reserve on each market served. Given near-infinite combinations of markets, it would be impossible for a single market maker to serve the entire market. A decentralized, community-driven approach allows each market maker to serve the markets where they have comparative advantage. This is a more optimal long-term solution to the crypto industry's [liquidity problem](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

- **Regulatory limitations**: Regulations on cryptocurrencies are still evolving and unclear, which creates particular challenges for trading on an institutional/company basis.  As a technology company, we want to focus on building technology and not spend our time on navigating and monitoring the ever-changing regulations.  

### Why are you making Hummingbot open source?

- **Transparency**: In order to use Hummingbot, users must provide their private keys and exchange API keys.  In a similar way as wallet software, we want users to know how this sensitive information is being used and give them comfort when using Hummingbot; aka, open kimono.

- **Community**: Decentralization, blockchain technology, and cryptocurrencies are built on the idea of community by passionate technologists.  We welcome developers to study the code, suggest improvements, add cool new features, or help identify bugs or any other problems.

### What open source license does Hummingbot use?

Hummingbot is licensed under [Apache 2.0](https://github.com/CoinAlpha/hummingbot/blob/master/LICENSE).

### How much cryptocurrency do I need to get started?

While there is no minimum amount of assets to use Hummingbot, users should pay heed to exchange-specific minimum order sizes. In our [exchange connectors](/connectors) documentation, we include links to the exchange's minimum order size page where available.

We would recommend initially starting with smaller amounts of assets while you are getting familiar with the bot.

### Are my private keys and API keys secure?

Since Hummingbot is a local client, your private keys and API keys are as secure as the computer you are running them on.  The keys are used to create authorized instructions locally on the local machine, and only the instructions which have already been signed or authorized are sent out from the client.

Always use caution and make sure the computer you are running Hummingbot on is safe, secure, and free from unauthorized access.

### Do I need an Ethereum node to run Hummingbot?

You can use Hummingbot to create bots that trade on a centralized exchange, a decentralized exchange (DEX), or both. For Ethereum-based DEXs, you need access to an Ethereum node. 

We describe [various ways](/installation/node) that you can get access to a node.

### What does it cost for me to run Hummingbot?

Hummingbot is a free software, so you can download, install, and run it for free.

Transactions from Hummingbot are normal transactions conducted on exchanges; therefore when operating Hummingbot, you would be subject to each exchange’s fees (e.g. maker, taker, and withdrawal fees), as you would if you were trading on that exchange normally (i.e. without Hummingbot).

## Data collection

### What data do you collect when I use Hummingbot?

Users have full control over how much data they choose to send us. Depending on what users select, this may include:

- Ethereum wallet address
- Aggregate, anonymized trade and order volume
- Commands entered in the client interface
- Log entries for errors, notifications, and trade events

!!! note
    Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

### Why would I want to send you my usage data?

- **Get better support**: Granting access to your logs and client commands enables us to diagnose your issue more quickly and provide better support.

- **Participate in partner incentive programs**: Some of our exchange partners will compensate us based on aggregate volume. We plan to share this with participating users.

- **Help us improve the product**: We are committed to making Hummingbot the best open source software for crypto algorithmic trading. Understanding how users use the product will help us improve it more rapidly.

We only utilize user data for the purposes listed above. CoinAlpha and our employees are strictly prohibited from utilizing any user data for trading-related purposes.

### Can I opt-out of sharing my usage data?

Absolutely - the logger configuration file is fully editable. In addition, we maintain [templates](https://github.com/coinalpha/hummingbot/blob/master/hummingbot/templates) that users can use to override the default configuration settings. 

