# Client Interface Commands

## Client Commands

| Command | Function |
|---------|----------|
| `config` | Create a new bot or import an existing configuration.
| `help` | List the commands and get help on each one.
| `start` | Start your currently configured bot.
| `stop` | Stop your currently configured bot.
| `status` | Get the status of a running bot.
| `history`| List your bot's past trades and analyze performance.
| `exit`| Exit and cancel all outstanding orders.
| `exit -f`| Force quit without cancelling orders.
| `list` | List global objects like exchanges and trades.
| `paper_trade` | Toggle [paper trade mode](/utilities/paper-trade).
| `export_trades` | Export your bot's trades to a CSV file.
| `export_private_key` | Export your Ethereum wallet private key.
| `get_balance` | Query your balance in an exchange or wallet.

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
