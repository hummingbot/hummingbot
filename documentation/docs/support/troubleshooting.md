# Troubleshooting

Some of the common error messages found when using Hummingbot and how to resolve.

## Installed via Docker

#### Permission denied after installation

```
docker: Got permission denied while trying to connect to the Docker daemon socket at
unix:///var/run/docker.sock: Post
http://%2Fvar%2Frun%2Fdocker.sock/v1.39/containers/create?name=hummingbot_instance:
dial unix /var/run/docker.sock: connect: permission denied.
```

Exit from your virtual machine and restart.

#### Package 'docker.io' has no installation candidate

![](/assets/img/package-docker-io.png)

Install Docker using get.docker.com script as an alternative. Install `curl` tool then download and run get.docker.com script.

```bash
apt-get install curl
curl -sSL https://get.docker.com/ | sh
```

Allow docker commands without requiring `sudo` prefix (optional).

```bash
sudo usermod -a -G docker $USER
```

Exit and restart terminal.

## Installed from source

#### Conda command not found

```
$ conda
-bash: conda: command not found
```

If you have just installed conda, close terminal and reopen a new terminal to update the command line's program registry.

If you use `zshrc` or another shell other than `bash`, see the note at the bottom of this section: [install dependencies](/installation/from-source/macos/#part-1-install-dependencies).

#### Syntax error invalid syntax

```
File "bin/hummingbot.py", line 40
  def detect_available_port(starting_port: int) -> int:
                                           ^
SyntaxError: invalid syntax
```

Make sure you have activated the conda environment: `conda activate hummingbot`.

#### Module not found error

```
ModuleNotFoundError: No module named 'hummingbot.market.market_base'

root - ERROR - No module named
‘hummingbot.strategy.pure_market_making.inventory_skew_single_size_sizing_delegate’
(See log file for stack trace dump)
```

Exit Hummingbot to compile and restart using these commands:

```bash
conda activate hummingbot
./compile
bin/hummingbot.py
```

## Installed in Windows (Docker Toolbox)

Windows users may encounter the following error when running the Docker Toolbox for Windows:

```
C:\Program Files\Docker Toolbox\docker.exe:
Error response from daemon: Get https://registry-1.docker.io/v2/:net/http: request canceled while waiting for connection
(Client.Timeout exceeded while awaiting headers).
See 'C:\Program Files\Docker Toolbox\docker.exe run --help'.
```

This appears to be an environment configuration problem. The solution is to refresh the environment settings and restart the environment which can be done with the following commands:

```bash
# Restart the environment
docker-machine restart default

# Refresh your environment settings
eval $(docker-machine env default)
```

## Running Hummingbot

#### Binance errors in logs

These are known issues from the Binance API and Hummingbot will attempt to reconnect afterwards.

```
hummingbot.market.binance.binance_market - NETWORK - Unexpected error while fetching account updates.

AttributeError: 'ConnectionError' object has no attribute 'code'
AttributeError: 'TimeoutError' object has no attribute 'code'

hummingbot.core.utils.async_call_scheduler - WARNING - API call error:
('Connection aborted.', OSError("(104, 'ECONNRESET')",))

hummingbot.market.binance.binance_market - NETWORK - Error fetching trades update for the order
[BASE]USDT: ('Connection aborted.', OSError("(104, 'ECONNRESET')",)).
```

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).


#### IDEX errors in logs

You may see any of these errors in logs when trading on IDEX market. These are server-side issues on IDEX's end.

```
OSError: Error fetching data from https://api.idex.market/order.

HTTP status is 400 - {'error': "Cannot destructure property `tier` of 'undefined' or 'null'."}
HTTP status is 400 - {'error': 'Unauthorized'}
HTTP status is 400 - {'error': 'Nonce too low. Please refresh and try again.'}
HTTP status is 500 - {'error': 'Something went wrong. Try again in a moment.'}
```

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).


#### No orders generated in paper trading mode

Errors will appear if any of the tokens in `maker_market_symbol` and/or `taker_market_symbol` has no balance in the paper trade account.

```
hummingbot.strategy.pure_market_making.pure_market_making_v2 - ERROR - Unknown error while generating order proposals.
Traceback (most recent call last):
  File "pure_market_making_v2.pyx", line 284, in hummingbot.strategy.pure_market_making.pure_market_making_v2.PureMarketMakingStrategyV2.c_tick
  File "pure_market_making_v2.pyx", line 384, in hummingbot.strategy.pure_market_making.pure_market_making_v2.PureMarketMakingStrategyV2.c_get_orders_proposal_for_market_info
  File "inventory_skew_multiple_size_sizing_delegate.pyx", line 58, in hummingbot.strategy.pure_market_making.inventory_skew_multiple_size_sizing_delegate.InventorySkewMultipleSizeSizingDelegate.c_get_order_size_proposal
  File "paper_trade_market.pyx", line 806, in hummingbot.market.paper_trade.paper_trade_market.PaperTradeMarket.c_get_available_balance
KeyError: 'ZRX'

hummingbot.core.clock - ERROR - Unexpected error running clock tick.
Traceback (most recent call last):
  File "clock.pyx", line 119, in hummingbot.core.clock.Clock.run_til
  File "pure_market_making_v2.pyx", line 292, in hummingbot.strategy.pure_market_making.pure_market_making_v2.PureMarketMakingStrategyV2.c_tick
  File "pass_through_filter_delegate.pyx", line 22, in hummingbot.strategy.pure_market_making.pass_through_filter_delegate.PassThroughFilterDelegate.c_filter_orders_proposal
AttributeError: 'NoneType' object has no attribute 'actions'
```

In this case, ZRX is not yet added to the list. See [this page](/utilities/paper-trade/#account-balance) on how to add balances.

#### Cross-Exchange Market Making error in logs

Errors will appear if the token value is unable to convert `{from_currency}` to `{to_currency}` are not listed on the exchange rate class.

```
2019-09-30 05:42:42,000 - hummingbot.core.clock - ERROR - Unexpected error running clock tick.
Traceback (most recent call last):
  File "clock.pyx", line 119, in hummingbot.core.clock.Clock.run_til
  File "cross_exchange_market_making.pyx", line 302, in hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making.CrossExchangeMarketMakingStrategy.c_tick
  File "cross_exchange_market_making.pyx", line 387, in hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making.CrossExchangeMarketMakingStrategy.c_process_market_pair
  File "cross_exchange_market_making.pyx", line 1088, in hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making.CrossExchangeMarketMakingStrategy.c_check_and_create_new_orders
  File "cross_exchange_market_making.pyx", line 781, in hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making.CrossExchangeMarketMakingStrategy.c_get_market_making_price
  File "/hummingbot/core/utils/exchange_rate_conversion.py", line 190, in convert_token_value
    raise ValueError(f"Unable to convert '{from_currency}' to '{to_currency}'. Aborting.")
ValueError: Unable to convert 'BTC' to 'BTC'. Aborting.
```

In this case, BTC is not yet added to the list of exchange rate class. See [this page](/utilities/exchange-rates/#exchange-rate-class) the correct format on adding exchange rate.
