# Client Interface Commands

## Client Commands

| Command | Function |
|---------|----------|
| `help` | Prints a list of available commands.
| `start` | Starts the bot. If any configuration settings are missing, it will automatically prompt you for them.
| `config` | Configures or, if a bot is already running, re-configures the bot.
| `status` | Get a status report about the current bot status.
| `list` | List wallets, exchanges, configs, and completed trades.<br/><br/>*Example usage: `list [wallets|exchanges|configs|trades]`*
| `get_balance` | Get the balance of an exchange or wallet, or get the balance of a specific currency in an exchange or wallet.<br/><br/>*Example usage: `get_balance [-c WETH -w|-c ETH -e binance]` to show available WETH balance in the Ethereum wallet and ETH balance in Binance, respectively*.
| `exit`| Cancels all orders, saves the log, and exits Hummingbot.
|`exit -f`| Force quit without cancelling orders.
| `stop` | Cancels all outstanding orders and stops the bot.
|`export_private_key`| Print your ethereum wallet private key.
|`history`| Print bot's past trades and performance analytics. For an explanation of how Hummingbot calculates profitability, see our blog [here](https://hummingbot.io/blog/2019-07-measure-performance-crypto-trading/#tldr).
|`export_trades`| Export your trades to a csv file.

## Bounty-Related Commands

| Command | Description |
|-------- | ----------- |
| `bounty --register` | Register to participate in for liquidity bounties
| `bounty --status` | See your accumulated rewards
| `bounty --terms` | See the terms & conditions
