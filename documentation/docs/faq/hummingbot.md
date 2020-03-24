# Hummingbot FAQs

Below is a summary of frequently asked questions regarding Hummingbot.  If you have additional questions or need support, please join the official [Hummingbot Discord server](https://discord.hummingbot.io) or email us at [support@hummingbot.io](mailto:support@hummingbot.io).

### What is Hummingbot?

[Hummingbot](http://hummingbot.io) is open source software that helps you build and run market making bots. For more detailed information, please read the [Hummingbot whitepaper](https://www.hummingbot.io/hummingbot.pdf).

### Why are you making Hummingbot available to the general public rather than just running it in-house?

We make money by administering [Liquidity Mining](/liquidity-mining) programs, which allow token projects to source liquidity from a decentralized network rather than from a single firm. Hummingbot is a free tool that anyone can use to participate in liquidity mining.

### Why are you making Hummingbot open source?

- **Trust and Transparency**: In order to use crypto trading bots, users must provide their private keys and exchange API keys. An open source codebase enables anyone to inspect and audit the code.

### How much cryptocurrency do I need to get started?

There is no minimum amount of assets to use Hummingbot, but users should pay heed to exchange-specific minimum order sizes. In our [exchange connectors](/connectors) documentation, we include links to the exchange's minimum order size page where available.

### Are my private keys and API keys secure?

Since Hummingbot is a local client, your private keys and API keys are as secure as the computer you are running them on.  The keys are used to create authorized instructions locally on the local machine, and only the instructions which have already been signed or authorized are sent out from the client.

Always use caution and make sure the computer you are running Hummingbot on is safe, secure, and free from unauthorized access.

### What does it cost for me to run Hummingbot?

Hummingbot is a free software, so you can download, install, and run it for free.

Transactions from Hummingbot are normal transactions conducted on exchanges; therefore when operating Hummingbot, you would be subject to each exchange’s fees (e.g. maker, taker, and withdrawal fees), as you would if you were trading on that exchange normally (i.e. without Hummingbot).

### What data do you collect when I use Hummingbot?

Hummingbot has the ability to send error logs to us.

!!! note 
      Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

### Why would I want to send you my usage data?
- **Get better support**: Granting access to your logs and client commands enables us to diagnose your issue more quickly and provide better support.

- **Help us improve the product**: We are committed to making Hummingbot the best open source software for crypto algorithmic trading. Understanding how users use the product will help us improve it more rapidly.

We only utilize user data for the purposes listed above. CoinAlpha and our employees are strictly prohibited from utilizing any user data for trading-related purposes.

### How do I opt-in to or opt-out of data sharing?

When configuring Hummingbot, you are asked the following question:

```
Would you like to send error logs to hummingbot? (Yes/No) >>>
```

Enter `Yes` to opt-in; enter `No` to opt-out.
