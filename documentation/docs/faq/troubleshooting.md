# Troubleshooting

Some of the common issues and error messages found when using Hummingbot and how to resolve them.

## Installation

### Permission denied after Docker installation

```
docker: Got permission denied while trying to connect to the Docker daemon socket at
unix:///var/run/docker.sock: Post
http://%2Fvar%2Frun%2Fdocker.sock/v1.39/containers/create?name=hummingbot_instance:
dial unix /var/run/docker.sock: connect: permission denied.
```

Exit from your virtual machine and restart.

### Package 'docker.io' has no installation candidate

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

### Conda command not found

```
$ conda
-bash: conda: command not found
```

If you have just installed conda, close terminal and reopen a new terminal to update the command line's program registry.

If you use `zshrc` or another shell other than `bash`, see the note at the bottom of this section: [install dependencies](/installation/source/macos/#part-1-install-dependencies).

### Syntax error invalid syntax

```
File "bin/hummingbot.py", line 40
  def detect_available_port(starting_port: int) -> int:
                                           ^
SyntaxError: invalid syntax
```

Make sure you have activated the conda environment: `conda activate hummingbot`.

### Module not found error

```
ModuleNotFoundError: No module named 'hummingbot.market.market_base'

root - ERROR - No module named
‘hummingbot.strategy.pure_market_making.inventory_skew_single_size_sizing_delegate’
(See log file for stack trace dump)
```

Solution 1: exit Hummingbot to compile and restart using these commands:

```bash
conda activate hummingbot
./compile
bin/hummingbot.py
```

Solution 2: make sure you have conda section in ~/.bashrc. Run `conda init` if it is not there. Explanation: if you have custom PATH defined in ~/.bashrc, supplied scripts (`./compile` etc) may pick wrong python binary, causing different errors.

## Configuration

### I can't copy and paste my API keys!

Copying and pasting your API keys into Hummingbot may be problematic, especially in Docker installations or for PuTTY users. See below for how to copy/paste in different environments.

### other ways to copy and paste

**COPY on Windows or Linux**
```
Ctrl + C 
Ctrl + Insert
Ctrl + Shift + C
```

**PASTE on Windows or Linux**
```
Ctrl + V
Shift + Insert
Ctrl + Shift + V
```

### paste items from clipboard in putty

You should be able to paste items from your clipboard by doing mouse right-click or `SHIFT + right-click`. If that doesn't work, follow the steps below.

1. If you are currently logged in a session, left-click on the upper left hand corner of the PuTTY window or a right-click anywhere on the title bar then select "Change Settings". If not, proceed to next step.
2. In PuTTY configuration under Window category go to "Selection". Select the "Window" radio button for action of mouse buttons.
3. You can now paste items from clipboard by doing a right-click to bring up the menu and select "Paste".

![](/assets/img/putty_copy_paste.gif)

### Where are my config and log files?

Hummingbot saves user data in the following directories:

* `conf`: strategy configuration files
* `log`: log files
* `data`: executed trades, saved in a sqlite database

Below are instructions on how to access these files in various environments.

**Windows**
1. Open File Explorer, select This PC and open local disc (C:\)
2. Browse to the Users folder, and open your profile folder.
3. Locate and open **AppData** folder
4. Open **Local** folder then **Hummingbot.io** folder. You may see another folder named **Hummingbot**, open it and you will see the data files folder.

!!! tip
    In case the AppData folder is not visible, on the menu bar found above your folder, go to **View** and tick the checkbox for Hidden items.
	 
**MacOS**
1. Open Finder
2. On the top menu bar, click **Go**
3. After clicking the **Go** menu, press the Option button on your keyboard.
4. Additional **Library** option should appear after that. 
5. Click **Library** 
6. Find and open **Application Support** folder and you will see **Hummingbot** folder.

!!! note
    Mac has multiple library folders, make sure that the library folder you're trying to open is the Library folder under your user profile.
 
**Docker**
1. Run the following command to view the details of your instance:
```bash
docker inspect $instance_name
```

2. Look for a field `Mounts`, which will describe where the folders are on your local machine:
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

3. Go to the folder locations listed under *Source*.

### How do I edit my config files from the command line?

If Hummingbot is installed on a virtual machine or a Linux cloud server, you can use the `vi` text editor (or any text editor of your choice). Run command `vi $filename`. See [this page](https://www.tipsandtricks-hq.com/unix-vi-commands-take-advantage-of-the-unix-vi-editor-374) for more information on how to use this text editor.

You can also use an FTP client software (e.g. WinSCP, FileZilla) to copy, move, files and folders from your virtual machine to your local machine and vice versa.

### I forgot my password. How do I reset it?

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

If Hummingbot is installed on MacOS, simply delete the encrypted files found in `~/Library/Application\ Support/Hummingbot/Conf`.

!!! warning
    Be careful when deleting the local wallet key file created through Hummingbot, i.e, a wallet that was not imported from Metamask; deleting the key file will result in a permanent loss of access to that wallet and any assets it may contain.

![delete_encrypted_files](/assets/img/ts_delete_encrypted.gif)

### How to reset global configs to default settings?

Editing `conf_global.yml` from text editor sometimes can cause error or corrupted configuration when running Hummingbot, its because of incorrect format, incorrect parameters, wrong spelling and unintentional added characters to the global config.

1. Run `exit` command to exit from the Hummingbot client.
2. Delete `conf_global.yml` from the `hummingbot_conf` folder.
3. Restart Hummingbot and a new generated `conf_global.yml` will be created, type `config` command to see the global configuration.

If using Linux, copy the commands below and run in your terminal to delete the file. You will be prompted to confirm before proceeding.

```bash tab="Docker build"
rm hummingbot_files/hummingbot_conf/conf_global.yml
```

```bash tab="Source build"
rm hummingbot/conf/conf_global.yml
```

If Hummingbot is installed on Windows, simply delete the `conf_global.yml` found in `%localappdata%\hummingbot.io\Hummingbot\conf`.

If Hummingbot is installed on MacOS, simply delete the `conf_global.yml` found in `~/Library/Application\ Support/Hummingbot/Conf`.

!!! Note
    If telegram is enabled make sure to backup your telegram token and chat id when deleting `conf_global.yml`.

### How do I adjust paper trade asset balances?

1. Stop the bot first if its running since parameter is part of the global settings
2. Type in `config paper_trade_account_balance`
3. Enter the token symbol and amount with the same format given on the input window. </br>
    ![cli_add_balance](/assets/img/cli_add_balance.gif)</br>
4. Press Enter to add and save the new token symbol.

!!! note
    1. Adding a new token balance should be done upon starting your bot (before importing or creating strategy) to avoid error.
    2. Default paper_trade tokens and amounts will be removed upon adding a new token pair. Don't forget to add all the tokens you need.

## Operation

### Why is my bot not placing orders?

Fetch your bot status by running `status` or `[Ctrl + S]`:
* Are there any warnings that may prevent the bot from starting?
* Is your `order_amount` parameter larger than the exchange minimum order size requirement?
* Check the available balance. If your available balance is lower than `order_amount`, Hummingbot will not place orders.
* Is your `inventory_skew_enabled` parameter enabled? Since this parameter adjusts order sizes, one side may be too low or too high.

### What parameter values should I set to make profitable trades?

The art of market making is identifying the optimal combination of strategy parameters, which may be different for each trading pair and in different market regime. As a general rule, Hummingbot does not advise users on parameter values.

### Where can I submit a feature/feedback request?
1. You can create a feature request through this [link](https://github.com/CoinAlpha/hummingbot/issues).
2. Select the green button **new issue**.
3. Choose **feature request** then fill it accordingly.

### No orders generated in paper trading mode

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

In this case, ZRX is not yet added to the list. See [this page](https://docs.hummingbot.io/operation/commands/paper-trade/#account-balance) on how to add balances.

### Unable to convert token

**Sample log error message**<br/>
`ValueError: Unable to convert XYZ to BTC. Aborting.`

Hummingbot uses external price feeds to convert one token to another, but certain symbols may be unavailable in the price feeds. Users can add them manually via the [Exchange Rate](/advanced/exchange-rates/) utility.

### [Binance] Timestamp for this request is outside of the recvWindow

**Sample log error message**<br/>
`binance.exceptions.BinanceAPIException: APIError(code=-1021): Timestamp for this request is outside of the recvWindow.`

Timestamp errors in logs happen when the Binance clock gets de-synced from time to time as they can drift apart for a number of reasons. Hummingbot should safely recover from this and continue running normally.

### [Binance] Too much request weight used; IP banned

**Sample log error message**<br/>
`binance.exceptions.BinanceAPIException: APIError(code=-1003): Way too much request weight used; IP banned until 1573987680818. Please use the websocket for live updates to avoid bans`

This error occurs when the Binance API rate limit is reached. Causes include:
* Using multiple order mode with 3+ orders per side
* High order refresh rate
* Running multiple instances of Hummingbot

Weight/Request error in logs happens when it encounters a warning or error and Hummingbot repeatedly sends the request (fetching status updates, placing/canceling orders, etc.) which resulted in getting banned. This should be lifted after a couple of hours or up to a maximum of 24 hours.

### [Kraken] 0 Balance error

**Sample log error message**<br/>
```
Failed connections:                                                                                      |
    kraken: {'error': {'error': []}}

10:12:24 - kraken_market - Error received from https://api.kraken.com/0/private/Balance. Response is {'error': []}.
```

This error occurs when Kraken account currently has no funds on the exchange. Fund your account to fix the error. For more info visit this [article](https://support.kraken.com/hc/en-us/articles/360001491786-API-Error-Codes).

### MAC mismatch error 

```
Hummingbot.core.utils.async_utils - ERROR - Unhandled error in background task: MAC mismatch Traceback (most recent call last):
File "/home/ubuntu/hummingbot/hummingbot/core/utils/async_utils.py", line 9, in safe_wrapper return await c
File "/home/ubuntu/hummingbot/hummingbot/core/utils/async_call_scheduler.py", line 128, in call_async return await self.schedule_async_call coro, timeout_seconds, app_warning_msg=app_warning_msg)
File "/home/ubuntu/hummingbot/hummingbot/core/utils/async_call_scheduler.py", line 117, in schedule_async_call return await fut
File "/home/ubuntu/hummingbot/hummingbot/core/utils/async_call_scheduler.py", line 80, in _coro_scheduler fut.set_result(await coro)
File "/home/ubuntu/miniconda3/envs/hummingbot/lib/python3.8/concurrent/futures/thread.py", line 57, in run result = self.fn(*self.args, **self.kwargs)
File "/home/ubuntu/hummingbot/hummingbot/client/config/security.py", line 88, in decrypt_all cls.decrypt_file(file)
File "/home/ubuntu/hummingbot/hummingbot/client/config/security.py", line 73, in decrypt_file cls._secure_configs[key_name] = decrypt_file(file_path, Security.password)
File "/home/ubuntu/hummingbot/hummingbot/client/config/config_crypt.py", line 67, in decrypt_file secured_value = Account.decrypt(encrypted, password)
File "/home/ubuntu/miniconda3/envs/hummingbot/lib/python3.8/site-packages/eth_account/account.py", line 134, in decrypt return HexBytes(decode_keyfile_json(keyfile, password_bytes))
File "/home/ubuntu/miniconda3/envs/hummingbot/lib/python3.8/site-packages/eth_keyfile/keyfile.py", line 49, in decode_keyfile_json return _decode_keyfile_json_v3(keyfile_json, password)
File "/home/ubuntu/miniconda3/envs/hummingbot/lib/python3.8/site-packages/eth_keyfile/keyfile.py", line 170, in _decode_keyfile_json_v3 raise ValueError("MAC mismatch") 
ValueError: MAC mismatch
```
This error is usually caused by having multiple encrypted keys with different passwords in the same config folder. For example:
```
Instance1                       Instance2
Password  : 1234                Password  : 5678 
API key/s : Binance             API key/s : Bittrex, Coinbase Pro, 
                                            Eterbase, Kraken, Huobi
```

Copying encrypted Binance key file from Instance1 to Instance2 will result to this error. To fix this:

1. Delete just the `encrypted_binance_api/secret_key.json` from Instance2's conf folder
2. Restart Hummingbot and password 5678 remains unchanged
3. Run `connect binance` and add the API keys - this will encrypt it with 5678 password and sync it with the rest of the API keys



## Miscellaneous

### How do I resize my Hummingbot window without jumbling the text?
When resizing the window of your Hummingbot, text becomes unclear or at the same location as the previous size of the window. To do a refresh to the new window size, while inside Hummingbot press `CTRL + L` and it will refresh Hummingbot window panes. These command applies to all Hummingbot build.

### How to change time or timezone of Hummingbot?

Hummingbot follows the same date/time and timezone on the machine where it is installed. Below are some steps you can follow to change the timezone depending on the operating system and installation type.

**Docker**

While docker `$instance_name` is running on background, type in command line.

```
docker exec -it $instance_name bash
dpkg-reconfigure tzdata
```

Configure geographic location and timezone by inputting the corresponding number, see example below:

![](/assets/img/docker-tz.png)

**Windows**

You can change the timezone on a Windows computer by doing the following:

1. Press **Win + R** shortcut to open the Run dialog box
2. Enter `timedate.cpl` to open Date and Time settings
3. Click **Change time zone**

![](/assets/img/windows-tz.png)

Alternatively, you can also follow these steps in Windows Support article: [How to set your time and time zone](https://support.microsoft.com/en-ph/help/4026213/windows-how-to-set-your-time-and-time-zone)

### How to Connect Metamask using Brave browser

Normally, Brave browser should ask which crypto wallet to use when connecting to the miners app. However, this sometimes does not appear on the browser.

Here are the steps to set your Brave browser to always use Metamask when connecting your crypto wallet with Hummingbots miners app. 
1. Click the "three horizontal line" icon on the top right of the Brave Browser
2. Select **Settings**
3. Click on **Extensions**
4. Click the dropdown for **Web3 provider for using Dapps** and select **Metamask** 

![](/assets/img/brave_with_metamask.gif)

