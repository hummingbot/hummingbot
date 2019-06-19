This tutorial aims to provide a quick comprehensive guide on how to install and run Hummingbot. 

## Table of content
- [Prerequisites](#prerequisites)
- [Installing hummingbot](#installing-hummingbot)
- [Running hummingbot](#running-hummingbot)
- [Configuration](#configuration)
- [More resources](#more-resources)

## Prerequisites
Below, we list all the preparation you need before you install and run Hummingbot. 

### System requirements
Make sure that your computer environment is up to date:

- (Linux) Ubuntu 16.04 or later
- (Mac) macOS 10.12.6 (Sierra) or later
- (Windows) Windows 10 or later

If you want to install hummingbot from source and run locally, you need to install <a href="https://www.anaconda.com/distribution/" target="_blank">Anaconda</a> since Hummingbot requires Python.

###💰 Token inventory 
You need to have enough inventory of the token pairs you want to trade. Be aware of the minimum order size requirements on different exchanges.

### Centralized exchange account and API 
In order to trade on a centralized exchange such as Binance, you will need to import its API key related credentials to Hummingbot. 

Instructions for how to find the API key for each exchange are below:

- [Binance](https://docs.hummingbot.io/connectors/binance/)
- [Coinbase Pro](https://docs.hummingbot.io/connectors/coinbase/)

### Ethereum wallet 

Hummingbot liquidity bounties will need your ethereum wallet’s public address for reward payouts. Also, users need to maintain 0.1 ETH in their wallet in order to prevent spam attacks. 

Follow the link [here](https://docs.hummingbot.io/installation/wallet/#creating-your-wallet) to create or import your wallet in Hummingbot.

!!! note "Note: Ethereum node"
    To trade on decentralized exchanges, you need to set up an Ethereum node in order to communicate with the blockchain. Read the instructions on [Ethereum node](https://docs.hummingbot.io/installation/node/).


## Installing hummingbot
Below are a few options for installing Hummingbot depending on your computer system and preference. In general, we recommend you install hummingbot in the cloud or from Docker. 

### Mac/Linux

With a pre-compiled version of `hummingbot` from Docker, you can easily [install Hummingbot](https://docs.hummingbot.io/installation/docker/) with just a few commands. In general, installing hummingbot from Docker takes less time than doing it from source. 

First, you need to <a href="https://docs.docker.com/v17.12/install/#supported-platforms" target="_blank">download Docker</a>. It takes about one minute to download. Docker supports multiple operating platforms, cloud, and on-premises. 

- Watch the <a href="https://www.youtube.com/watch?v=eCfMKfS9HsM" target="_blank">step-by-step instruction video</a>
- Read [documentation](/installation/docker_macOS_linux) 

If you want to install hummingbot from source, here's how to -
- Watch the <a href="https://www.youtube.com/watch?v=LX57Q26LZcw&t=27s" target="_blank">step-by-step instruction video</a>
- Read [documentation](/installation/source/) 

### Windows

First, <a href="https://github.com/docker/toolbox/releases/"  target="_blank">download Docker</a> for Windows. Run the installation and restart if prompted. Open Docker using the **Quickstart Terminal** and create default configurations. 

- Watch the <a href="https://www.youtube.com/watch?v=K67qN4nmSnw&list=PLDwlNkL_4MMczSzZiomX5wFFuF40z-KLl&index=5" target="_blank">step-by-step instruction video</a>
- Read [documentation](/installation/docker_windows) 


### Cloud
We highly recommend you unstall hummingbot in cloud platforms. Running hummingbot in the cloud saves your local computing power, memory, and storage, provides a stable and seamless connection that can keep the bot running 24/7, and increases the speed of transactions by operating on servers that are geographically closer to the exchanges. 

- Watch <a href="https://www.youtube.com/watch?v=rdUshjOlP-8&list=PLDwlNkL_4MMczSzZiomX5wFFuF40z-KLl&index=5" target="_blank">instruction videos</a> for the cloud platform of your choice  
- Read [documentation](/installation/cloud/)


## Running hummingbot
After all the installations are complete, you are now ready to configure your hummingbot and run it! The command line-based user interface should look something like the below image. 
![](https://www.hummingbot.io/blog/2019-04-announcing-hummingbot/hummingbot-cli.png)

The left bottom pane is where you enter [commands](https://docs.hummingbot.io/operation/client/#commands) to run the bot. The upper left pane prints the output of your commands and the right pane logs messages in real time. 


## Configuration
Every time you start running Hummingbot, you need to configure the settings. You can choose to `create` new settings or `import` previous config files. They can be [edited directly](https://docs.hummingbot.io/operation/configuration/) or accessed later in the `conf/` folder that hummingbot automactially creates when you first configure it. 

To participate in liquidity bounties, you should choose either **pure market making** strategy or **cross-exchange market making** startegy so that you can make market for designated tokens. The bounty rewards will be paid out based on the volume of your filled limit maker orders. 

### [Pure market making](https://docs.hummingbot.io/strategies/pure-market-making/)

- Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory
- This strategy has a relatively higher risk and complexity as compared to the cross-exchange market making strategy and we ask users to exercise with caution

!!! note 
    To qualify for Harmony $ONE Makers at this moment, please choose **pure market making strategy** on **Binance** for any available $ONE token pairs.   

    **Learn how to configure your bot in order to be qualified for $ONE Makers, click [here](/bounties/tutorial/config).**

### [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)	
    
- Also referred to as liquidity mirroring or exchange remarketing
- For this strategy, Hummingbot makes markets on smaller or less liquid exchanges and does the opposite, back-to-back transaction any filled trades on a more liquid exchange
- This strategy has relatively lower risk and complexity as compared to other market making strategies


## More resources
- [Documentation](https://docs.hummingbot.io/) 
- [Whitepaper](https://www.hummingbot.io/whitepaper.pdf) 
- [Chinese guide](https://github.com/coinalpha/hummingbot_chinese)
- [Chat room](http://discord.hummingbot.io) 