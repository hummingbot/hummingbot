# Troubleshooting

Some of the common error messages found when using Hummingbot and how to resolve.


## Running Hummingbot

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

## Binance Errors

Common errors found in logs when running Hummingbot on Binance connector.

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).

These are known issues from the Binance API and Hummingbot will attempt to reconnect afterwards.

```
hummingbot.market.binance.binance_market - NETWORK - Unexpected error while fetching account updates.

AttributeError: 'ConnectionError' object has no attribute 'code'
AttributeError: 'TimeoutError' object has no attribute 'code'

hummingbot.core.utils.async_call_scheduler - WARNING - API call error:
('Connection aborted.', OSError("(104, 'ECONNRESET')",))

hummingbot.market.binance.binance_market - NETWORK - Error fetching trades update for the order
[BASE][QUOTE]: ('Connection aborted.', OSError("(104, 'ECONNRESET')",)).
```


### APIError (code=-1021)

Timestap errors in logs happen when the Binance clock gets de-synced from time to time as they can drift apart for a number of reasons. Hummingbot should safely recover from this and continue running normally.

```
binance.exceptions.BinanceAPIException: APIError(code=-1021): Timestamp for this request is outside of the recvWindow.
```

### APIError (code=-1003)

Weight/Request error in logs happens when it encountered a warning or error and Hummingbot repeatedly sends the request (fetching status updates, placing/canceling orders, etc.) which resulted to getting banned. This should be lifted after a couple of hours or up to a maximum of 24 hours.

* Too many requests queued.
* Too much request weight used; please use the websocket for live updates to avoid polling the API.
* Too much request weight used; current limit is %s request weight per %s %s. Please use the websocket for live updates to avoid polling the API.
* Way too much request weight used; IP banned until %s. Please use the websocket for live updates to avoid bans.

```
binance.exceptions.BinanceAPIException: APIError(code=-1003): Way too much request weight used; IP banned until 1573987680818. Please use the websocket for live updates to avoid bans
```

For more information visit the Binance API documentation for [Error Codes](https://binance-docs.github.io/apidocs/spot/en/#error-codes-2).
	
### HTTP status 429 and 418 return codes

The [HTTP return codes](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#http-return-codes) in Binance official API docs includes information on each code.

We recommend to refrain from running multiple Hummingbot instances trading on Binance in one server or IP address. Otherwise, it may result to these errors especially if using multiple orders mode with pure market making strategy.

If you use the endpoint https://api.binance.com/api/v3/exchangeInfo you can see their limitation on API trading.

```
"timezone": "UTC",
"serverTime": 1578374813914,
"rateLimits": [
    {
        "rateLimitType": "REQUEST_WEIGHT",
        "interval": "MINUTE",
        "intervalNum": 1,
        "limit": 1200
    },
    {
        "rateLimitType": "ORDERS",
        "interval": "SECOND",
        "intervalNum": 10,
        "limit": 100
    },
    {
        "rateLimitType": "ORDERS",
        "interval": "DAY",
        "intervalNum": 1,
        "limit": 200000
    }
```

Exceeding the 1,200 total request weight per limit will result in an IP ban. The order limits of 100 per second or 200,000 will be dependent on account.


## Dolomite Errors

This error below indicates that an account on Dolomite must be created.

```
... WARNING - No Dolomite account for <wallet_address>.
```

Follow the instructions in [Dolomite - Using the Connector](https://docs.hummingbot.io/connectors/dolomite/#using-the-connector).