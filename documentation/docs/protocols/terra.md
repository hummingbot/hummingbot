---
tags:
- protocol connector
---

# `terra`

!!! note
    This connector is currently being refactored as part of the [Gateway V2 redesign](/developers/gateway). The current V1 version is working, but may have usability issues that will be addressed in the redesign.

## 📁 Folders

* [Hummingbot - Connector](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/connector/terra)
* [Gateway - Routes](https://github.com/CoinAlpha/gateway-api/blob/master/src/routes/terra.ts)
* [Gateway - Service](https://github.com/CoinAlpha/gateway-api/blob/master/src/services/terra.ts)

## ℹ️ Protocol Info

**Terra** 
[Website](https://terra.money/) | [CoinMarketCap](https://coinmarketcap.com/currencies/terra-luna/) | [CoinGecko](https://www.coingecko.com/en/coins/terra-luna)

* Docs: https://docs.terra.money/
* Explorer: https://finder.terra.money/

## 👷 Maintenance

* Release added: [0.34.0](/release-notes/0.34.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

First, follow the instructions to install and run [Hummingbot Gateway](/protocols/gateway/).

![](/assets/img/terra_setup.png)

Afterwards, follow the steps below:

1. Run the command `connect terra` in the Hummingbot client
2. Enter your Terra wallet address
3. Enter your Terra wallet seed, including the spaces in between each word

![](/assets/img/connect-terra.gif)

If connection is successful:
```
You are now connected to terra.
```

## 💼 Wallet

![](/assets/img/terra-create-wallet.gif)

1. Download and install Terra Station wallet from their site https://terra.money/
2. Launch Terra Station and click the **Connect** button at the top
3. Select **New wallet** to create a new wallet
4. Fill out all forms and make sure to store your seed phrase in a secured place
5. Confirm your seed to complete
6. The Terra wallet address is located at the top

