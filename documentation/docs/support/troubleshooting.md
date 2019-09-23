# Troubleshooting

## **Common errors with Hummingbot installed via Docker**

#### Permission denied after installation

```
docker: Got permission denied while trying to connect to the Docker daemon socket at
unix:///var/run/docker.sock: Post
http://%2Fvar%2Frun%2Fdocker.sock/v1.39/containers/create?name=hummingbot_instance:
dial unix /var/run/docker.sock: connect: permission denied.
```

Exit from your virtual machine and restart.


## **Common errors with Hummingbot installed from source**

#### Conda command not found

```
$ conda
-bash: conda: command not found
```

If you have just installed conda, close terminal and reopen a new terminal to update the command line's program registry.

If you use `zshrc` or another shell other than `bash`, see the note at the bottom of this section: [install dependencies](/installation/from-source/macos/#part-1-install-dependencies).

#### Cannot start Hummingbot

##### Syntax error invalid syntax

```
File "bin/hummingbot.py", line 40
  def detect_available_port(starting_port: int) -> int:
                                           ^
SyntaxError: invalid syntax
```

Make sure you have activated the conda environment: `conda activate hummingbot`.

##### Module not found error

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

## **Common Errors with Windows + Docker Toolbox**

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

## **Errors while running Hummingbot**

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
