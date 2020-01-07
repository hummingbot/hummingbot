# [Quickstart] Setup

This guide walks you through how to install Hummingbot and run your first trading bot.

Below, we list what you'll need before you install and run Hummingbot.

## System Requirements

**Why this is needed**: If you are installing Hummingbot either locally or on a cloud server, here are the recommended minimum system requirements:

- (Linux) Ubuntu 16.04 or later
- (Mac) macOS 10.12.6 (Sierra) or later
- (Windows) Windows 10 or later

For more information, view [minimum system requirements](/installation/#minimum-system-requirements).

## Crypto Inventory

**Why this is needed**: In order to run trading bot, you'll need some inventory of crypto assets available on the exchange, or in your Ethereum wallet (for Ethereum-based decentralized exchanges).

Remember that you need inventory of both the **base asset** (the asset that you are buying and selling) and the **quote asset** (the asset that you exchange for it). For example, if you are making a market in a `BTC/USDT` trading pair, you'll need some `BTC` and `USDT`.

In addition, be aware of the minimum order size requirements on different exchanges. For more information, please see [Connectors](/connectors).

## API Keys

**Why this is needed**: In order to run a bot on a centralized exchange like Binance, you will need to enter the exchange API keys during the Hummingbot configuration process.

For more information on how to get the API keys for each exchange, please see [API Keys](/installation/api-keys).

## Ethereum Wallet

**Why this is needed**: In order to earn rewards from Liquidity Bounties, you need an Ethereum wallet. In addition, you'll need to import an Ethereum wallet when you run a trading bot on an Ethereum-based decentralized exchange.

For more information on creating or importing an Ethereum wallet, see [Ethereum wallet](/installation/wallet).

## Ethereum Node (DEX only)
**Why this is needed**: When you run a trading bot on a Ethereum-based decentralized exchange, your wallet sends signed transactions to the blockchain via an Ethereum node.

For more information, see [Ethereum node](/installation/node/node). To get a free node, see [Get a Free Ethereum Node](/installation/node/infura/).

## Cloud Server (Optional)

We recommend that users run trading bots in the cloud, since bots require a stable network connection and can run 24/7.

Follow the guide to [set up a cloud server](/installation/cloud) on your preferred cloud platform. Hummingbot is not resource-intensive so the lowest/free tiers should work.

!!! tip
    Don't know which cloud platform to use? Read our [blog post](https://www.hummingbot.io/blog/2019-06-cloud-providers/) that compares and contrasts the different providers.

If you just want to test out Hummingbot, you can skip this and install locally.

---
# Next: [Install Hummingbot](/quickstart/2-install)
