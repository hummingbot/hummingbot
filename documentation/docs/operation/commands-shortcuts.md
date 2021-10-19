# Commands and Shortcuts

## Hummingbot commands

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

## Docker commands

These are the commonly used docker commands when using Hummingbot.

| Command                       | Function                      |
| ----------------------------- | ----------------------------- |
| `docker ps -a`                | List containers               |
| `docker rm [container name]`  | Remove one or more containers |
| `docker rmi [image name]`    | Remove one or more images     |
| `docker rm $(docker ps -a q)` | Remove all containers         |

To view more docker commands, go to [Docker Command Line Reference](https://docs.docker.com/engine/reference/commandline/docker/).

## Linux commands

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


## Keyboard shortcuts

| Keyboard Combo    | Command                    | Description                                  |
| ----------------- | -------------------------- | -------------------------------------------- |
| `Double CTRL + C` | Exit                       | Press `CTRL + C` twice to exit the bot       |
| `CTRL + S`        | Status                     | Show bot status                              |
| `CTRL + F`        | Search / <br/> Hide Search | Toggle search in log pane                    |
| `CTRL + X`        | Exit Config                | Exit from the current configuration question |
| `CTRL + A`        | Select All                 | \* Select all text                           |
| `CTRL + Z`        | Undo                       | \* Undo action                               |
| `Single CTRL + C` | Copy                       | \* Copy text                                 |
| `CTRL + V`        | Paste                      | \* Paste text                                |

_\* Used for text edit in input pane only._

**Note about search:**

1. Press `CTRL + F` to trigger display the search field
2. Enter your search keyword (not case sensitive)
3. Hit `Enter` to jump to the next matching keyword (incremental search)
4. When you are done, press `CTRL + F` again to go back to reset

**Linux**

| Keyboard Combo                   | Command |
| -------------------------------- | ------- |
| CTRL + C                         | Copy    |
| SHIFT + RMB (right-mouse button) | Paste   |

To highlight, hold `SHIFT + LMB` (left mouse button) and drag across the text you want to select.

**Mac**

| Keyboard Combo | Command |
| -------------- | ------- |
| ⌘ + C          | Copy    |
| ⌘ + V          | Paste   |

!!! note
    To select text on macOS, you may need to enable the **Allow Mouse Reporting** option by pressing `⌘ + R` or selecting **View > Allow Mouse Reporting** in the menu bar.

![allowmouse](/assets/img/allow_mouse_reporting.png)

Then you should be able to select text by holding `LMB` (left mouse button) and drag. You can also hold down `⌥ + shift` to select specific lines like the image below.

![highlightmacos](/assets/img/highlight_macos.png)

When accessing Hummingbot on a Linux cloud server through `ssh` using a macOS terminal, hold down the `Option ⌥` key or `⌥ + ⌘` to highlight text.

**Windows**

| Keyboard Combo   | Command |
| ---------------- | ------- |
| CTRL + SHIFT + C | Copy    |
| CTRL + SHIFT + V | Paste   |

To use this shortcut, check this box by doing a right-click on the title bar at the top of the Hummingbot window, then select **Properties**.

![](/assets/img/properties_windows.png)
