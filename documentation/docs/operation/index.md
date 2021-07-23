# Using Hummingbot

Hummingbot uses a command-line interface (CLI) that helps users configure and run the bot, as well as generate logs of the trades performed.

Start hummingbot quickly and efficiently with these references:

- [Launch and Exit Hummingbot](/operation/launch-exit)
- [Create and Delete Password](/operationpassword)
- [Connecting to an Exchange](/operation/connect-exchange)
- [Checking Balances](/operation/balances)
- [Start and Stop Strategy](/operation/start-stop)
- [Check bot and Market Status](/operation/checking-status)
- [Performance History](/operation/performance-history)
- [Override Fees](/operation/override-fees)

## Hummingbot Commands

Below are the available commands in the current Hummingbot release.

| Command           | Function                                                      |
| ----------------- | ------------------------------------------------------------- |
| `connect`         | List available exchanges and add API keys to them             |
| `create`          | Create a new bot                                              |
| `import`          | Import an existing bot by loading the configuration file      |
| `help`            | List available commands                                       |
| `balance`         | Display your asset balances across all connected exchanges    |
| `config`          | Display the current bot's configuration                       |
| `start`           | Start the current bot                                         |
| `stop`            | Stop the current bot                                          |
| `open_orders`     | Show all active open orders                                   |
| `trades`          | Show trades                                                   |
| `pnl`             | Show profit and losses                                        |
| `status`          | Get the market status of the current bot                      |
| `history`         | See the past performance of the current bot                   |
| `generate_certs`  | Create SSL certifications for Gateway communication.          |
| `exit`            | Exit and cancel all outstanding orders                        |
| `paper_trade`     | Toggle paper trading mode                                     |
| `export`          | Export your bot's trades or private keys                      |
| `order_book`      | Displays the top 5 bid/ask prices and volume                  |
| `ticker`          | Show market ticker of current order book                      |
| `autofill_import` | Choose between `start` and `config` when importing a strategy |

## Docker Commands

These are the commonly used docker commands when using Hummingbot.

| Command                        | Function                      |
| ------------------------------ | ----------------------------- |
| `docker ps -a`                 | List containers               |
| `docker rm [container name]`   | Remove one or more containers |
| ``docker rmi [image name]`     | Remove one or more images     |
| `docker rm \$(docker ps -a q)` | Remove all containers         |

To view more docker commands, go to [Docker Command Line Reference](https://docs.docker.com/engine/reference/commandline/docker/).

## Linux Commands

These are the basic commands used to navigate Linux commonly used with Hummingbot.

| Command | Function                                             |
| ------- | ---------------------------------------------------- |
| `ls`    | Lists all files and folders in the current directory |
| `cd`    | Change directory / move to another folder location   |
| `mv`    | Moves or renames a file or directory                 |
| `cp`    | To copy files or group of files or directory         |
| `rm`    | Remove / delete files and folders                    |
| `top`   | Details on all active processes                      |
| `htop`  | Monitor the system processes in real time            |

For more information about basic Linux commands, check out [The Linux command line for beginners](https://ubuntu.com/tutorials/command-line-for-beginners#1-overview).
