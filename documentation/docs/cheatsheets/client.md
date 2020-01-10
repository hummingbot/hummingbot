# Client Interface Commands

## Client Commands

| Command | Function |
|---------|----------|
| `bounty` | Participate in Hummingbot's liquidity bounty program or get bounty status.
| `config` | Configures or, if a bot is already running, re-configures the bot.
| `exit`| Cancels all orders, saves the log, and exits Hummingbot.
| `exit -f`| Force quit without cancelling orders.
| `export_private_key` | Print your Ethereum wallet private key.
| `export_trades` | Export your trades to a csv file.
| `get_balance` | Get the balance of an exchange or wallet, or get the balance of a specific currency in an exchange or wallet.<br/><br/>*Example usage: `get_balance [-c WETH -w|-c ETH -e binance]` to show available WETH balance in the Ethereum wallet and ETH balance in Binance, respectively*.
| `help` | Prints a list of available commands. Adding a command after `help` will display available positional and optional arguments.<br/><br/>*Example: `help bounty` will show how to use the `bounty` command.
| `history`| Print bot's past trades and performance analytics. For an explanation of how Hummingbot calculates profitability, see our blog [here](https://hummingbot.io/blog/2019-07-measure-performance-crypto-trading/#tldr).
| `list` | List wallets, exchanges, configs, encrypted configs and completed trades.<br/><br/>*Example usage: `list [wallets|exchanges|configs|encrypted|trades]`*
| `paper_trade` | Enable or disable [paper trade mode](/utilities/paper-trade).
| `start` | Starts the bot. If any configuration settings are missing, it will automatically prompt you for them.
| `status` | Get a status report about the current bot status.
| `stop` | Cancels all outstanding orders and stops the bot.

## Bounty-Related Commands

| Command | Description |
|-------- | ----------- |
| `bounty --register` | Register to participate in for liquidity bounties
| `bounty --list` | See a list of active bounties.
| `bounty --restore-id` | If you lost your configuration file, this is the command to restore it.
| `bounty --status` | See your accumulated rewards.
| `bounty --terms` | See the terms & conditions.

## Keyboard shortcuts
| Keyboard Combo | Command | Description |
|-------- | ----------- | ----------- |
| `Double CTRL + C` | Exit | Press `CTRL + C` twice to exit the bot.
| `CTRL + S` | Status | Show bot status.
| `CTRL + F` | Search | Toggles search in log pane (see below for usage)
| `CTRL + A` | Select All | Select all text in input pane [used for text edit in Input pane only].
| `CTRL + Z` | Undo | Undo action in input pane [used for text edit in Input pane only].
| `Single CTRL + C` | Copy | Copy text [used for text edit in Input pane only].
| `CTRL + V` | Paste | Paste text [used for text edit in Input pane only].

!!! tip "Tip: How to use the Search feature"
    1. Press `CTRL + F` to trigger display the search field
    2. Enter your search keyword (not case sensitive)
    3. Hit `Enter` to jump to the next matching keyword (incremental search)
    4. When you are done. Press `CTRL + F` again to go back to reset.
