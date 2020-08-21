# Liquidity Mining Quickstart - Paper Trade

0. [Overview](index.md)
1. [Install Hummingbot](install.md)
2. [Configure a market making bot](configure.md)
3. [Run the bot in paper trading mode](run-bot.md)
4. [Participate in Liquidity Mining](participate.md)

---

## Overview

There are two phases of this quickstart, Hummingbot installation and Market Making bot configuration. The Hummingbot Miner is optional unless you want to participate in liquidity mining. See following flowchart:

![Liquidity Mining Quickstart Flowchart](/assets/img/LiquidityMiningQuickstartFlowchart.png)

This quickstart guide shows you how to install Hummingbot and start running a market making bot (paper trade) in approximately 12 minutes. You'll learn how to:

* Hummingbot Installation
    * Install the open source Hummingbot client (~3 minutes)
* Market Making Bot Configuration
    * Configure a market making bot (~5 minutes)
    * Run the bot in paper trading mode (~2 minutes)
* Hummingbot Miner app setup
    * Participate in liquidity mining (~2 minutes)


<!-- ### Inventory

Hummingbot is trading software that uses your own crypto assets. You will need inventory available on each exchange where you want to run a bot.

Remember that you need inventory of both the **base asset** (the asset that you are buying and selling) and the **quote asset** (the asset that you exchange for it). For example, if you are making a market in a `BTC/USDT` trading pair, you'll need some `BTC` and `USDT`. -->


## What you'll need

Prepare the following items before you start.

### System Requirements

If you are installing Hummingbot either locally or on a cloud server, here are the recommended minimum system requirements:

* Linux: Ubuntu 16.04 or later
* MacOS: macOS 10.12.6 (Sierra) or later
* Windows: Windows 10 or later

### API Keys for Hummingbot and Miner App

Since we'll be running the bot in *paper trading mode*, you don't need any crypto inventory. However, you will need an account with one of our [supported exchanges](/connectors) to create API keys.

Two set of API keys is needed: 

* Trade-enabled keys: needed for Hummingbot during the configration to trade your assets
* Read-only keys: needed for (Miner app) (https://miners.hummingbot.io/) to setup Liquidity Mining, and track your rewards and bot performance

![Figure 1: Liquidity mining relationship](/assets/img/liquidityminingrelationship.jpg)

For more information on how to get the API keys for each exchange, please see the individual exchange pages in [Connectors](/connectors).

---

**Ready to get started?** Proceed to the first step: [Install Hummingbot](install.md)
