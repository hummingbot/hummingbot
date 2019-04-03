---
type: "docs"
title: "Technical"
category: "1-FAQs"
category_order: 1
---
# Technology FAQs Related to Operating Hummingbot

## What do I need to do to start using Hummingbot?

Hummingbot currently supports Binance, Radar Relay, and DDEX.  Some of the instructions below are specific for these exchanges.

1. **Hummingbot client**: to run the software, you will need to download Hummingbot from [github](https://github.com/coinalpha/hummingbot) or [docker](https://cloud.docker.com/u/coinalpha/repository/docker/coinalpha/hummingbot) and follow these [installation and getting started instruction](/installation).

2. **Binance account and trading API key**: in order to trade on [Binance](https://binance.com), you need an account and need to [create an Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API).  For the Binance API key, “Enable Trading” must be selected.

3. **Ethereum wallet**: for trading on Radar Relay and DDEX, you will need an Ethereum Wallet address and its private key.

4. **Ethereum**: you will need some Ethereum in your Ethereum Wallet to pay gas for any Ethereum blockchain function calls associated with any DEX transactions.

5. **Crypto asset Inventory**: you will need to have some inventory of both base currency and quote currency on both exchanges you are using Hummingbot to trade on.

6. **Ethereum node**: lastly, you will need access to an Ethereum node.  You can either run your own locally or use a publicly available service such as [Alchemy Insights](https://alchemyinsights.io/hummingbot) or [Infura](https://infura.io/).

## Do I need an Ethereum node?

Yes, for strategies that involve interacting with decentralized exchanges on the Ethereum blockchain, such as Radar Relay and DDEX.

## How do I get access to an Ethereum node?

The best and most reliable way, not to mention in the spirit of decentralization, is to run your own Ethereum node!

### Option 1. Run your own local node

Running your own node may require dedicated storage and compute, as well as some technical skills. These are the two most widely used Ethereum clients:
- [go-ethereum (geth)](https://github.com/ethereum/go-ethereum/wiki/Building-Ethereum)
- [parity](https://github.com/paritytech/parity-ethereum)

!!! note
    These may require several hours to days to sync and may require some troubleshooting when first running.

### Option 2. Third-party providers
1. [Alchemy Insights](https://alchemyinsights.io/) provides professional grade Ethereum nodes. We have partnered with Alchemy to provide a free trial for Hummingbot users - please contact us for more information.
2. [Quiknode](https://quiknode.io)
3. [Infura](https://infura.io/) provides free and the most widely used Ethereum nodes.

!!! warning
    Third party providers may have limited functionality; the Hummingbot team continues to evaluate and test node providers.

### Option 3. Dedicated Blockchain Hardware
Get dedicated hardware for your Ethereum node.  Ethereum nodes are meant to run constantly 24/7 and use up a material amount of computational resources (CPU, RAM, and storage).  For more serious users, it may make sense to use dedicated hardware.

#### Software
- [DAppNode](https://dappnode.io/) is software that automates the installation and operation of Ethereum (as well as other blockchains) on dedicated hardware.it easier to start and operate an Ethereum node and can run other blockchains.

#### Hardware
- [IntelⓇ NUC mini PC](https://www.intel.com/content/www/us/en/products/boards-kits/nuc.html): DIY, customize and configure your own hardware.
- [Avado](https://ava.do/): purpose built hardware that is pre-loaded with DAppNode.

## Why does Hummingbot need my Ethereum wallet private key?

Strategies that transact on Decentralized Exchanges (such as Radar Relay and DDEX) are direct interactions with that exchange’s smart contracts on the Ethereum blockchain.  Therefore, transactions must be signed and authorized, which requires your private key.

## Are my private keys and API keys secure?

Since Hummingbot is a local client, your private keys and API keys are as secure as the computer you are running them on.  The keys are used to create authorized instructions locally on the local machine, and only the instructions which have already been signed or authorized are sent out from the client.

Always use caution and make sure the computer you are running Hummingbot on is safe, secure, and free from unauthorized access.


### What does it cost for me to run Hummingbot?

Hummingbot is a free software, so you can download, install, and run it for free.

Transactions from Hummingbot are normal transactions conducted on exchanges; therefore when operating Hummingbot, you would be subject to each exchange’s fees (e.g. maker, taker, and withdrawal fees), as you would if you were trading on that exchange normally (i.e. without Hummingbot).
