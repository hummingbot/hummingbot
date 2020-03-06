
## Hummingbot commands

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
| `paper_trade` | Toggle [paper trading mode](/operation/paper-trade).
| `export_trades` | Export your bot's trades to a CSV file.
| `export_private_key` | Export your Ethereum wallet private key.
| `get_balance` | Query your balance in an exchange or wallet.

## Hummingbot keyboard shortcuts

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

## Docker scripts

These commands execute the helper scripts for running Hummingbot and are performed from the terminal or shell. Ensure that the scripts are located in your current directory before running these commands.

| Command | Function |
|---------|----------|
| `./create.sh` | Creates a new instance of Hummingbot
| `./start.sh` | Connect to a running instance or restart an exited Hummingbot instance
| `./update.sh` | Update Hummingbot version

!!! tip
    Run the command `ls -l` to check the files in your current working directory.

### Updating your scripts

Copy the commands below and paste into the shell or terminal to download and enable the automated scripts.

```bash tab="Linux"
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

```bash tab="MacOS"
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

```bash tab="Windows via Docker Toolbox"
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

## Docker commands

| Command | Description |
|---------|----------|
| `docker ps` | List all running containers
| `docker ps -a` | List all created containers (including stopped containers)
| `docker attach [instance_name]` | Connect to a running Docker container
| `docker start [instance_name]` | Start a stopped container
| `docker inspect [instance_name]` | View details of a Docker container, including details of mounted folders

More commands can be found in [Docker Documentation](https://docs.docker.com/engine/reference/commandline/docker/).