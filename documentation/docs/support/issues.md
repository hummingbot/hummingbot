# Known Issues

Hummingbot is experimental, beta software that we are continually improving. Below, we list commonly reported issues and their resolution status.

While we try to keep this list up to date, it may not contain the latest issues reported in our [Github repository](https://github.com/CoinAlpha/hummingbot/issues).

## Outstanding

### [Coinbase Pro] USDC trading pairs may not work

Hummingbot's **arbitrage** and **cross-exchange market making** strategies rely on the ability to place market orders. Certain Coinbase Pro trading pairs may be moved to limit-only mode, as described in this <a href="https://status.pro.coinbase.com/incidents/hyfyg5zsqk1w" target="_blank">incident report</a>. This prevents market orders from being placed in these markets.

Currently, market orders for USDC trading pairs on Coinbase Pro may be impacted by this. This means that these pairs should not be used with the **arbitrage** strategy, nor as the `taker_market` in the **cross-exchange market making strategy**. Since USDC market orders will fail, the Coinbase Pro leg of the trade will not be executed.

### [Radar Relay] Phantom filled orders 

We are tracking a bug in which expired orders on Radar Relay may change to the **filled** state despited no Ethereum transaction taking place. When this happens in a bot running the [cross-exchange market making](/strategies/cross-exchange-market-making) strategy, the bot may execute hedging trades on the `taker_market` against these phantom filled orders.

### [DDEX] Duplicate and untracked filled orders

Users have reported seeing duplicate orders placed by Hummingbot on DDEX, as well as filled orders on DDEX that are not tracked by Hummingbot. We are currently triaging this issue with the help of the DDEX team.

### Errors related to network downtime and exchange API errors

Currently, network downtime or exchange API errors may cause a bot to stop running, creating many error-related messages in the log file. We are currently working on a fix to improve Hummingbot's resilience against these types of errors.

### Trades may not be profitable at lower min_profitability values

Hummingbot does not yet take into account exchange fees and gas costs. In addition, for trading strategies that trade on two different markets, order book shifts may cause one or more legs of the trade to execute at a worse price that anticipated.

We are working on a feature that will bake fee/gas calculations in Hummingbot and enable users to more easily diagnose trade performance.

### Maker order size must be greater than 0
Users running Hummingbot reported seeing the following error in the log messages:
```
ValueError: Maker order size (0.0) must be greater than 0.
```
**Possible Resolution:** In the [cross-exchange market making](/strategies/cross-exchange-market-making) and [arbitrage](/strategies/arbitrage) strategies, Hummingbot automatically sets a trade size equal to 1/6 of the total portfolio value across both exchanges. When the user's balance in one account is too small or imbalanced, this may result in trade sizes which are lower than the exchange's minimum order size. We recommend that users either:

* utilize the `trade_size_override` setting in the strategy configuration file to manually set the trade size, denominated in the quote asset, or;
* add a sufficient quantity of assets so that asset inventory across exchanges is roughly equal (see [Running bots: Inventory requirements](/operation/running-bots/#inventory-requirements) for more detail).

### Incompatible dependency messages during installation
Users who installed Hummingbot from source may see the following warning messages when running `./install`:
```
0x-web3 4.8.2.1 has requirement web3==4.8.2, but you'll have web3 4.8.3 which is incompatible.
aiokafka 0.5.0 has requirement kafka-python==1.4.3, but you'll have kafka-python 1.4.4 which is incompatible.
```
As these warnings do not impact operation of Hummingbot, you can safely ignore them. 

### Warnings when starting Hummingbot
Users may see the following warning messages when starting Humminbot:
```
Warning: local config not found. You need to define the API keys in config_local.py.
Warning: web3 wallet secret not found. You need to define the web3 wallet secret in web3_wallet_secret.py
Warning: binance secret not found. You need to define the binance secret in binance_secret.py
Warning: coinbase pro secret not found. You need to define the coinbase pro secret in coinbase_pro_secrets.py
```
These warnings are a legacy artifact of our prior, proprietary code base. As they do not impact operation of Hummingbot, you can safely ignore them.

## Resolved

### Missing file: hummingbot_logs.yml
Users who installed Hummingbot from source saw the following error upon starting Hummingbot:
```
FileNotFoundError: [Errno 2] No such file or directory: '/home/user_name/hummingbot/conf/hummingbot_logs.yml'
```
**Resolution:** Fixed in v0.5.0. Users who installed an earlier version can solve this issue by creating a file called `hummingbot_logs.yml` in Hummingbot's `conf` directory and populating its contents with one of the templates in the [log_templates](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/templates/log_templates) directory.

### No module named `eth_account`

**Resolution**: There are a couple reasons why you may see this error:

* **Anaconda environment not activated:** If you installed Hummingbot from source, check that you have run `conda activate hummingbot` before running Hummingbot. You will see a `(hummingbot)` prefix in the command line if the environment is active,
* **Installation/compilation errors:** There may have been errors during the installation or compilation process that prevented installation of certain library dependencies. Uninstall Hummingbot by running `./uninstall` and install from source again. If you still see the error, create an Github issue and include the output of the `./install` and `./compile` commands.

### Order book is empty
A user who run Hummingbot reported seeing the following error message in the log messages:
```
OSError: Order book is empty - no price quote is available
```
**Resolution:** This error is displayed when the order book is thinner than a certain threshold. We suggest that you double check the token symbols you entered in the strategy configuration file. If the symbol of the pair doesn’t exist on certain exchanges, this error will also be displayed.

### No module named `zero_ex`

Users who installed Hummingbot from source on Ubuntu saw the following error upon starting Hummingbot:
```
ModuleNotFoundError: No module named `zero_ex`
```
**Resolution:** Fixed in [v0.4.0](/release-notes/0.4.0); the cause was missing libraries in `setup/environment-linux.yml`

### No module named `wings.web3_wallet`

Users reported the following error upon starting Hummingbot:
```
ModuleNotFoundError: No module named 'wings.web3_wallet' 
```
**Resolution:** Make sure that you are in the root hummingbot directory when compiling or starting Hummingbot.

### Pip subprocess error: failed building wheel for...

Users who install Hummingbot from source on Ubuntu saw the following error upon running `./compile`:
```
Pip subprocess error:
  Failed building wheel for cytoolz
  Failed building wheel for lru-dict
  Failed building wheel for regex
  Failed building wheel for twisted
```
**Resolution:** Hummingbot uses `gcc` and `make` to correctly install dependencies. We recommend installing the `build-essential` package:
```
sudo apt-get update
sudo apt-get install build-essential
```

### Trading pair selection

Hummingbot throws an error if the trading pair entered by the user isn't available on the exchange. However, each exchange may have different syntax for their trading pairs, and different trading pairs, by convention, may switch the base asset and the quote asset.

**Resolution:** In [v0.2.0](/release-notes/0.2.0), we added tab autocomplete and dropdown menus to trading pair selection in the `config` process.