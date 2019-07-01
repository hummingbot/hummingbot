# Run a market making bot

Now that you have [registered](/bounties/tutorial/register) for liquidity bounties, you can run a market making bot and start to earn rewards!

First, run the `config` command to select and configure a strategy.

## Select a market making strategy

To participate in liquidity bounties, you should choose either **pure market making strategy** or **cross-exchange market making strategy** so that you can make markets and provide liquidity for designated tokens. Your rewards and rankings will be based on the total volume of your filled orders in a given period.

### [Pure market making](https://docs.hummingbot.io/strategies/pure-market-making/)

- Post buy and sell limit orders on a single exchange
- Automatically adjust the orders as market prices change

### [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)

- Also referred to as *mirroring* or *liquidity cloning*
- Post buy and sell limit orders on a less liquid exchange. Whenever you are filled, hedge your risk by buying/selling the same asset on a more liquid exchange
- This strategy is relatively safer but requires the asset to be traded on multiple exchanges

## Configuration

You can choose to `create` new settings or `import` previous config files. You can also directly edit the config files, which are located in the `conf/` folder.

Refer to the configuration walkthroughs and parameters for each strategy:

* [Pure market making](/strategies/pure-market-making/#configuration-walkthrough)
* [Cross-exchange market making](/strategies/cross-exchange-market-making/)

## Running your first bot

After configuration, you can start market making by running the `start` command. Be sure to use smaller order amounts and higher spreads initially until you gain familiarity with market making.

!!! tip
    You can see your Hummingbot open orders in real-time on the exchange website as you run Hummingbot. Generally, we recommend having the exchange website in a browser alongside the running Hummingbot command line interface.
