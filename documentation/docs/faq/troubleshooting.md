# Troubleshooting

Some of the common issues and error messages found when using Hummingbot and how to resolve them.

## Common Support Questions

Frequently asked questions and problems that may arise when using Hummingbot.


### I’m running on pure market making strategy. Why is it only placing buy orders and not sell orders? (or vice-versa)

Check the balance in your inventory. If you don't have enough balance on one side, it will only place orders on the side that it can. This is fine and expected behavior for the strategy.


### What settings or parameter values should I use to make profitable trades?

Hummingbot does not advise on parameter values. As a market maker, testing different parameters and seeing how they perform is really the art or science of market making.


### Where can I submit a feature/feedback request?
1. You can create a feature request through this [link](https://github.com/CoinAlpha/hummingbot/issues).
2. Select the green button **new issue**.
3. Choose **feature request** then fill it accordingly.


### Where are the config and log files on Hummingbot installed via Docker?

Run the following command to view the details of your instance:

```bash
docker inspect $instance_name
```

Look for a field `Mounts`, which will describe where the folders are on you local machine:

```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_data",
        "Destination": "/data",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_conf",
        "Destination": "/conf",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_logs",
        "Destination": "/logs",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    }
],
```

!!! note
    Read through [Log File Management](https://docs.hummingbot.io/utilities/logging/) for more information.


### How to edit the conf files or access the log files used by my docker instance?

If Hummingbot is installed on a virtual machine or a Linux cloud server, you can use the `vi` text editor (or any text editor of your choice). Run command `vi $filename`. See [this page](https://www.tipsandtricks-hq.com/unix-vi-commands-take-advantage-of-the-unix-vi-editor-374) for more information how to use this text editor.

You can also use an FTP client software (e.g. WinSCP, FileZila) to copy, move, files and folders from your virtual machine to your local machine and vice versa.


### Paste items from clipboard in PuTTY

You should be able to paste items from your clipboard by doing mouse right-click or `SHIFT + right-click`. If that doesn't work, follow the steps below.

1. If you are currently logged in a session, left-click on the upper left hand corner of the PuTTY window or a right-click anywhere on the title bar then select "Change Settings". If not, proceed to next step.
2. In PuTTY configuration under Window category go to "Selection". Select the "Window" radio button for action of mouse buttons.
3. You can now paste items from clipboard by doing a right-click to bring up the menu and select "Paste".

![](/assets/img/putty_copy_paste.gif)


### Other ways to copy and paste

Copying to clipboard on Windows or Linux:

```
Ctrl + C 
Ctrl + Insert
Ctrl + Shift + C
```

Pasting items from clipboard on Windows or Linux:

```
Ctrl + V
Shift + Insert
Ctrl + Shift + V
```


### Locate data folder or hummingbot_trades.sqlite when running Hummingbot via Docker

1. Find ID of your running container.
```
# Display list of containers
docker container ps -a

# Start a docker container
docker container start <PID>
```
2. Evaluate containers file system.
```
run docker exec -t -i <name of your container> /bin/bash
```
3. Show list using `ls` command.
4. Switch to `data` folder and use `ls` command to display content.
5. If you would like to remove the sqlite database, use `rm <database_name>` command.

In version 0.22.0 release, we updated the Docker scripts to map the `data` folder when creating and updating an instance.

1. Delete the old scripts.
```
rm create.sh update.sh
```
2. Download the updated scripts.
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
```
3. Enable script permissions.
```
chmod a+x *.sh
```
4. Command `./create.sh` creates a new Hummingbot instance.
5. Command `./update.sh` updates an existing Hummingbot instance.


### Get REST API data using Postman

Some information related to an exchange can be retrieved through their public API such as minimum order sizes. You can download a program called [Postman](https://www.getpostman.com/) and follow the instructions in [Get Started with Postman](https://learning.getpostman.com/getting-started/).

![](/assets/img/postman.png)


### How to reset in case of forgotten password

For security reasons, Hummingbot does not store your password anywhere so there's no way to recover it. The only solution is to create a new password and re-enter your API keys upon restarting Hummingbot after deleting or moving the encrypted files.

1. Run `exit` command to exit from the Hummingbot client.
2. Delete the encrypted files and wallet key file (if applicable) from the `hummingbot_conf` folder.
3. Restart Hummingbot and run `config` command.

If using Linux, copy the commands below and run in your terminal to delete the files. You will be prompted to confirm before proceeding.

```bash tab="Docker build"
rm hummingbot_files/hummingbot_conf/encrypted* hummingbot_files/hummingbot_conf/key_file*
```

```bash tab="Source build"
rm hummingbot/conf/encrypted* hummingbot/conf/key_file*
```

If Hummingbot is installed on Windows, simply delete the encrypted files found in `%localappdata%\hummingbot.io\Hummingbot\conf`.

!!! warning
    Be careful when deleting the local wallet key file created through Hummingbot, i.e, a wallet that was not imported from Metamask; deleting the key file will result in a permanent loss of access to that wallet and any assets it may contain.

![delete_encrypted_files](/assets/img/ts_delete_encrypted.gif)


### Transfer files from/to Windows Subsystem for Linux and local computer
1. Execute command `explorer.exe .` (make sure to include the dot) in WSL to launch a file explorer window of your current directory. Then you will be able to move, copy and delete files like you normally would on a Windows computer.
2. If command `explorer.exe .` fails to open your hummingbot directory, you need to [disable and enable WSL using powershell](https://www.tenforums.com/tutorials/46769-enable-disable-windows-subsystem-linux-wsl-windows-10-a.html)


### Download a previous version of Hummingbot in Windows

1. Go to `https://hummingbot-distribution.s3.amazonaws.com/`. It will show an XML file with all the Hummingbot versions listed.</br></br>
    ![binary_distribution](/assets/img/ts_binary_distribution.png)</br></br>
2. To download a previous version, add the version inside `<Key>` after the URL.

For example, enter the URL</br>
https://hummingbot-distribution.s3.amazonaws.com/hummingbot_v0.20.0_setup.exe
</br>on your web browser to start downloading the installer for Hummingbot version 0.20.0.


### Alternate method to locate Hummingbot data files if you use a binary installer

#### Windows Computer

1. Open File Explorer, select This PC and open local disc (C:\)
2. Browse to the Users folder, and open your profile folder.
3. Locate and open **AppData** folder
4. Open **Local** folder then **Hummingbot.io** folder. You may see another folder named **Hummingbot**, open it and you will see the data files folder.

!!! tip
    In case the AppData folder is not visible, on the menu bar found above your folder, go to **View** and tick the checkbox for Hidden items.
	 
#### Mac Computer

1. Open Finder
2. On the top menu bar, click **Go**
3. After clicking the **Go** menu, press the Option button on your keyboard.
4. Additional **Library** option should appear after that. 
5. Click **Library** 
6. Find and open **Application Support** folder and you will see **Hummingbot** folder.

!!! note
    Mac has multiple library folders, make sure that the library folder you're trying to open is the Library folder under your user profile.
 

### How to check the status of multiple bot simultaneously?
1. As of the moment, you can only check the status of each bot one at a time. 
2. A workaround is to integrate telegram on all your hummingbot instances and use a single telegram_chat_ID.

!!! note
    Read through [Telegram integration](https://docs.hummingbot.io/utilities/telegram/) for more information.


### How to add paper trade balance settings inside Hummingbot CLI?
1. Stop the bot first if its running since parameter is part of the global settings
2. Type in `config paper_trade_account_balance`
3. Enter the token symbol and amount with the same format given on the input window. </br>
    ![cli_add_balance](/assets/img/cli_add_balance.gif)</br>
4. Press Enter to add and save the new token symbol.

!!! note
    1. Adding a new token balance should be done upon starting your bot (before importing or creating strategy) to avoid error.
    2. Default paper_trade tokens and amounts will be removed upon adding a new token pair. Don't forget to add all the tokens you need.


### How to refresh Hummingbot Window Panes?
When resizing the window of your Hummingbot, text becomes unclear or at the same location as the previous size of the window. To do a refresh to the new window size, while inside Hummingbot press `CTRL + L` and it will refresh Hummingbot window panes. These command applies to all Hummingbot build.

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