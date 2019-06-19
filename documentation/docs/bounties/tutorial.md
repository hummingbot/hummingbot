This tutorial aims to provide a quick comprehensive guide on how to install and run Hummingbot. 

### Table of content
- [Prereqisites](#prerequisites)
- [Installing hummingbot](#installing-hummingbot)
- [Running hummingbot](#running-hummingbot)
- [Configuration](#configuration)
- [More resources](#more-resources)

## Prerequisites
Below, we list all the preparation you need before you install and run Hummingbot. 

### System requirement and Anaconda
Make sure that your computer environment is up to date:
- (Linux) Ubuntu 16.04 or later
- (Mac) macOS 10.12.6 (Sierra) or later
- (Windows) Windows 10 or later

Since Hummingbot requires Python, you need to install <a href="https://www.anaconda.com/distribution/" target="_blank">Anaconda</a> if you want to install hummingbot from source and run locally.

### Token inventory
You need to have enough inventory of the token pairs you want to trade. Be aware of the minimum order size requirements on different exchanges.

### Centralized exchange account and API 
In order to trade on a centralized exchange such as Binance, you will need to import its API key related credentials to Hummingbot. 

Instructions for how to find the API key for each exchange are below:
- [Binance](https://docs.hummingbot.io/connectors/binance/)
- [Coinbase Pro](https://docs.hummingbot.io/connectors/coinbase/)

### Ethereum wallet 
Decentralized exchanges require transactions that directly interact with smart contracts on the Ethereum blockchain. Follow the link [here](https://docs.hummingbot.io/installation/wallet/#creating-your-wallet) to create or import your wallet in Hummingbot.

In addition, Hummingbot liquidity bounties will need your ethereum wallet’s public address for reward payouts.

!!! note "Note: Ethereum node"
    To trade on decentralized exchanges, you need to set up an Ethereum node in order to communicate with the blockchain. Read the instructions on [Ethereum node](https://docs.hummingbot.io/installation/node/).


## Installing hummingbot
Below are a few options for installing Hummingbot depending on your computer system and preference. In general, we recommend you install hummingbot from Docker. This is the easiest and quickest way to install hummingbot, which takes a few minutes. 

### Installing hummingbot from Docker (Linux/Mac)
With a pre-compiled version of `hummingbot` from Docker, you can easily [install Hummingbot](https://docs.hummingbot.io/installation/docker/) with just a few commands in Terminal. In general, installing hummingbot from Docker takes less time than doing it from source. 

First, you need to <a href="https://docs.docker.com/v17.12/install/#supported-platforms" target="_blank">download Docker</a>. It takes about one minute to download. Docker supports multiple operating platforms, cloud, and on-premises. 

After you've downloaded docker successfully, head over to Terminal and watch the step-by-step instruction video <a href="https://www.youtube.com/watch?v=eCfMKfS9HsM" target="_blank">here</a>.

### Installing hummingbot from Docker (Windows)
Similar to the steps above for installing from Linux/Mac, first, <a href="https://github.com/docker/toolbox/releases/"  target="_blank">download Docker</a> for Windows. Run the installation and restart if prompted. 

Open Docker using the Quickstart Terminal and create default configurations. 

Watch the step-by-step instruction video <a href="https://www.youtube.com/watch?v=K67qN4nmSnw&list=PLDwlNkL_4MMczSzZiomX5wFFuF40z-KLl&index=5" target="_blank">here</a>.

### Installing hummingbot from Source (Linux/Mac)
Hummingbot is open source on Github. Head over and <a href="https://github.com/coinalpha/hummingbot" target="_blank">clone or download the folder</a>. After you saved the folder on your computer, open Terminal to [run install script](https://docs.hummingbot.io/installation/source/#3-run-install-script) and [activate the environment](https://docs.hummingbot.io/installation/source/#4-activate-environment). 

For a step-by-step instructions, <a href="https://www.youtube.com/watch?v=LX57Q26LZcw&t=27s" target="_blank">click here</a> to watch a tutorial video.

### Other installation methods
You can also install Hummingbot in different cloud platforms. [Click here](https://docs.hummingbot.io/installation/cloud/#setup-a-new-vm-instance-on-google-cloud-platform) for more details, or watch our tutorial videos <a href="https://www.youtube.com/watch?v=LX57Q26LZcw&list=PLDwlNkL_4MMczSzZiomX5wFFuF40z-KLl" target="_blank">here</a>.


## Running hummingbot
After all the installations are complete, you are now ready to configure your hummingbot and run it! The command line-based user interface should look something like the below image. 
![](https://www.hummingbot.io/blog/2019-04-announcing-hummingbot/hummingbot-cli.png)

The left bottom pane is where you enter [commands](https://docs.hummingbot.io/operation/client/#commands) to run the bot. The upper left pane prints the output of your commands and the right pane logs messages in real time. 


## Configuration
Every time you start running Hummingbot, you need to configure the settings. You can choose to `create` new settings or `import` previous config files. They can be [edited directly](https://docs.hummingbot.io/operation/configuration/) or accessed later in the `conf/` folder that hummingbot automactially creates when you first configure it. 

Check out the configuration walkthroughs for current trading strategies available on hummingbot:

- [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)	
    - Also referred to as liquidity mirroring or exchange remarketing
    - For this strategy, Hummingbot makes markets on smaller or less liquid exchanges and does the opposite, back-to-back transaction any filled trades on a more liquid exchange
    - This strategy has relatively lower risk and complexity as compared to other market making strategies, which we thought would be a good starting point for initial users

- [Arbitrage](https://docs.hummingbot.io/strategies/arbitrage/)
    - Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other)

- [Pure market making](https://docs.hummingbot.io/strategies/pure-market-making/)
    - Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory
    - This strategy has a relatively higher risk and complexity as compared to other strategies and we ask users to exercise caution and completely before running it

- [Discovery](https://docs.hummingbot.io/strategies/discovery/)
    - This is a meta strategy that helps users find profitable arbitrage opportunities between two different exchanges. 
    - Users can run “Discovery” before they run arbitrage strategies using real capital. 


## More resources
- [Documentation](https://docs.hummingbot.io/) 
- [Whitepaper](https://www.hummingbot.io/whitepaper.pdf) 
- [Chinese guide](https://github.com/coinalpha/hummingbot_chinese)
- [Chat room](http://discord.hummingbot.io) 