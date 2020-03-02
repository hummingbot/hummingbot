# Running Bots

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see [Installation](/installation) and [Client](/operation/client) if you need help to install and launch the client.

## Starting a Bot

Use the `start` command from the client to initialize a market making bot.

If any configuration settings are missing, you will be prompted to add them (see: [Configuration](/operation/configuration/)).

If you have previously configured Hummingbot using `config` but are in a new session of the CLI, you will need to run `config` again to unlock your Ethereum wallet.

## Automatic Approvals

In order to trade on an Ethereum-based decentralized exchange (DEX), you may need to send an Ethereum transaction to approve your tokens for trading on the exchange if it is the first time that you are trading that token. Hummingbot checks if tokens are approved and automatically handles the approval transaction before it begins operation.

!!! note
    While Hummingbot automatically handles approvals, it does not automatically wrap ETH or unwrap WETH.

## Inventory Requirements

Hummingbot uses your token balances to determine the size of each order. For decentralized exchanges like Radar Relay, it uses the token balances in your Ethereum wallet. For centralized exchanges like Binance, it uses your token balances in the respective exchange. The trade size Hummingbot makes will be always less than the lowest asset balance on any side.

![inventory1](/assets/img/inventory1.png)
![inventory2](/assets/img/inventory2.png)

For cross-exchange market making, we **recommend** that users start with roughly equivalent balances of the base asset and the quote asset on each exchange. Thus, there are four balances to track:

* Base asset on the maker exchange
* Quote asset on the maker exchange
* Base asset on the taker exchange
* Quote asset on the taker exchange

!!! Tip
    In the near future, we plan to add an auto-rebalancing module to automate the process of transferring and exchanging tokens. Currently, users need to rebalance between these accounts manually.

## Using Commands

Please see [Client: Commands](/operation/client#client-commands) for a comprehensive list of Hummingbot's commands and their descriptions.

## Understanding Logs

Hummingbot's right pane contains a log of all actions taken by the bot, including approvals, canncellations, fills, etc. When the user exits Hummingbot, it saves a log file containing all of the section's activity to the `logs/` folder. (For more info, see: [Logs and Logging](/utilities/logging))
