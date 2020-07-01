# The Hummingbot Client

Hummingbot uses a command-line interface (CLI) that helps users configure and run the bot, as well as generate logs of the trades performed.

## Starting Hummingbot

### Installed from Docker

Creating a new instance of Hummingbot with `docker run` will automatically start the Hummingbot client (see Docker installation guides for [Windows](/installation/docker/windows), [Linux](/installation/docker/linux) and [MacOS](/installation/docker/macOS)).

To run a previously created, stopped container where $NAME is the name of your instance of Hummingbot:

```sh
docker start $NAME && docker attach $NAME
```

For additional information on useful commands, see the [commands](/operation/commands) to running Hummingbot on Docker.

### Installed from Source

!!! note
    Make sure that you activate the Anaconda environment with `conda activate hummingbot` prior to running Hummingbot.

Open a Terminal window and go to the root of the directory that contains Hummingbot. From there, run:
```
bin/hummingbot.py
```


## User Interface

### Client Layout
![Hummingbot CLI](/assets/img/hummingbot-cli.png)

The CLI is divided into three panes:

* **Input pane (lower left)**: where users enter commands
* **Output pane (upper left)**: prints the output of the user's commands
* **Log pane (right)**: log messages


## Keyboard shortcuts
| Keyboard Combo | Command | Description |
|-------- | ----------- | ----------- |
| `Double CTRL + C` <img width="50"> | Exit <img width="100"> | Press `CTRL + C` twice to exit the bot.
| `CTRL + S` | Status | Show bot status
| `CTRL + F` | Search / <br/> Hide Search | Toggle search in log pane.
| `CTRL + X` | Exit Config | Exit from the current configuration question.
| `CTRL + A` | Select All | * Select all text
| `CTRL + Z` | Undo | * Undo action
| `Single CTRL + C` | Copy | * Copy text
| `CTRL + V` | Paste | * Paste text

_* Used for text edit in input pane only._

**Note about search:**

1. Press `CTRL + F` to trigger display the search field

2. Enter your search keyword (not case sensitive)

3. Hit `Enter` to jump to the next matching keyword (incremental search)

4. When you are done. Press `CTRL + F` again to go back to reset.
