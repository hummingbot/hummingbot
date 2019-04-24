# Running Bots

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see [Installation](/installation) and [Client](/operation/client) if you need help to install and launch the CLI.

## Starting a bot

Use the `start` command to initialize a market making bot. 

If any configuration settings are missing, you will be prompted to add them (see: [Configuration](/operation/configuration/)). 

If you have previously configured Hummingbot using `config` but are in a new session of the CLI, you will need to run `config` again to unlock your Ethereum wallet.

## Automatic approvals

In order to trade on an Ethereum-based decentralized exchange (DEX), you may need to send an Ethereum transaction to approve your tokens for trading on the exchange if it is the first time that you are trading that token. Hummingbot checks if tokens are approved and automatically handles the approval transaction before it begins operation.

!!! note
    While Hummingbot automatically handles approvals, it does not automatically wrap ETH or unwrap WETH.

## Inventory requirements

Hummingbot uses your token balances to determine the size of each order. For decentralized exchanges like DDEX and Radar Relay, it uses the token balances in your Ethereum wallet. For centralized exchanges like Binance, it uses your token balances in the respective exchange. The trade size Hummingbot makes will be always less than the lowest asset balance on any side. 

![inventory1](/assets/img/inventory1.png)
![inventory2](/assets/img/inventory2.png)

For cross-exchange market making, we **recommend** that users start with roughly equivalent balances of the base asset and the quote asset on each exchange. Thus, there are four balances to track:

* Base asset on the maker exchange
* Quote asset on the maker exchange
* Base asset on the taker exchange
* Quote asset on the taker exchange

!!! Tip
    In the near future, we plan to add an auto-rebalancing module to automate the process of transferring and exchanging tokens. Currently, users need to rebalance between these accounts manually.

## Commands

Please see [Client: Commands](/operation/client#commands).

## Logs

Hummingbot's right pane contains a log of all actions taken by the bot, including approvals, canncellations, fills, etc. When the user exits Hummingbot, it saves a log file containing all of the section's activity to the `logs/` folder.

## Running multiple bots

To run multiple bots, you need to start Hummingbot in a new instance of bash/Terminal, or in a new container if you are using Docker. 

If you're using Docker, you still need separate folders to store your config files, and create your Docker container from each folder using the docker run command. To restart those containers, you use the command `docker start [name-of-your-container]` and `docker attach [name-of-your-container]`.
