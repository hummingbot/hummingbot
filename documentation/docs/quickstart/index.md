# Quickstart - Overview

0. Overview
1. [Install Hummingbot](install.md)
2. [Configure a market making bot](configure.md)
3. [Run the bot in paper trading mode](run-bot.md)

---

## Overview

This guide shows you how to install Hummingbot and start running a market making bot (initially in paper trade) in approximately 10 minutes. You'll learn how to:

* Install the open source Hummingbot client (~3 minutes)
* Configure a market making bot (~5 minutes)
* Run the bot in paper trading mode (~2 minutes)

<b>Important:</b> Once you are satisfied that the bot is running properly and you want to proceed with liquidity mining (go live). Ensure your [Miner App](https://miners.hummingbot.io/) is setup with the exchange APIs.

## What you'll need

Since we'll be running the bot in *paper trading mode*, you don't need any crypto inventory. However, you will need an account with one of our [supported exchanges](/connectors) to create API keys.

### System Requirements

If you are installing Hummingbot either locally or on a cloud server, here are the recommended minimum system requirements:

* Linux: Ubuntu 16.04 or later
* MacOS: macOS 10.12.6 (Sierra) or later
* Windows: Windows 10 or later

<!-- ### Inventory

Hummingbot is trading software that uses your own crypto assets. You will need inventory available on each exchange where you want to run a bot.

Remember that you need inventory of both the **base asset** (the asset that you are buying and selling) and the **quote asset** (the asset that you exchange for it). For example, if you are making a market in a `BTC/USDT` trading pair, you'll need some `BTC` and `USDT`. -->

### API Keys

In order to authorize Hummingbot to trade your assets, you will need to enter trade-enabled exchange API keys during the Hummingbot configuration process.  Separately, if you would like to participate in Liquidity mining, you will need to provide **read-only** API keys in the [Miner App](https://miners.hummingbot.io/)

For more information on how to get the API keys for each exchange, please see the individual exchange pages in [Connectors](/connectors).

---

**Ready to get started?** Proceed to the first step: [Install Hummingbot](install.md)
