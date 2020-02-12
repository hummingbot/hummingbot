# Step 3: Run Hummingbot

Now that you've connected your exchanges, you're ready to start earning liquidity rewards!

Below, we show how to install the open source Hummingbot software client and configure a market making bot.

!!! tip "Third-party software"
    While Hummingbot is designed and optimized to earn Liquidity Mining rewards, you can also use other market making software to earn rewards. Since we use your read-only API keys to credit your earnings, you can use any market making software to continually maintain and adjust orders on the order book.

---

## 3a. Install Hummingbot

### For new users

We recommend downloading the Hummingbot installer from our website where available. For more information, please see the main [Installation](/installation/) section in the [User Manual](/manual/).

#### Windows
Download the Hummingbot installer from our [download page](https://hummingbot.io/download/). 

See the [Windows installation guide](/installation/from-binary/windows/) for assistance.

#### macOS
Download the Hummingbot installer from our [download page](https://hummingbot.io/download/). 

See the [macOS installation guide](/installation/from-binary/macOS/) for assistance.

#### Linux
We don't have a pre-compiled binary for Linux yet, so we recommend that new Linux users install the Docker below (see below).

### For advanced users

Once users are familiar with Hummingbot, we recommend installing and running Hummingbot on a cloud platform like AWS for 24/7, continual operation.

!!! tip "Cloud Platforms"
    See [Setting a Cloud Server](/installation/cloud/) for instructions on creating an instance on AWS, Google Cloud, and Microsoft Azure.

#### Docker

Using our custom Docker scripts is the simplest way to deploy Hummingbot in the cloud.

* [Docker installation instructions for Linux](/installation/via-docker/linux/)
* [Docker installation instructions for Windows](/installation/via-docker/windows/)
* [Docker installation instructions for macOS](/installation/via-docker/macOS/)

#### From source

Installing directly from the Hummingbot open source code hosted on Github offers the greatest flexibility for users who want to customize their strategies and modify the codebase.

* [Installing from source on Linux](/installation/from-source/linux/)
* [Installing from source on Windows](/installation/from-source/windows/)
* [Installing from source on macOS](/installation/from-source/macOS/)

---

## 3b. Run a market making bot

Of all of [strategies](/strategies/) available in Hummingbot, only the market making strategies (strategies that submit and maintain standing limit orders on order books) are eligible for earning liquidity mining rewards. 

Below, we link to documentation for the two market making strategies available in Hummingbot.

### Pure market making

This strategy maintains buy and sell orders in a market.

* [Strategy overview](/strategies/pure-market-making/)
* [Configuration walkthrough](/strategies/pure-market-making/#configuration-walkthrough)

### Cross-exchange market making

This strategy maintains buy and sell orders in a market, while hedging any filled orders in another market. It is more complex to set up, but may be less risky.

* [Strategy overview](/strategies/cross-exchange-market-making/)
* [Configuration walkthrough](/strategies/cross-exchange-market-making/#configuration-walkthrough)

---

## 3c. Start earning rewards!

Once you have set up Hummingbot, check out the markets available in Hummingbot Miners to see the returns available.

Run a market making bot for any active market and start earning rewards! 😎

---

# Next: [Step 4: Track earnings](4-track-earnings.md)