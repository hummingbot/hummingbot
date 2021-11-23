# Scripts
Snippets of Python code that let users customize a strategy.

!!! warning
    Scripts were an early experiment to let users customize strategies, but a script's functionality is limited because it runs in a separate process. Going forward, we plan to make strategies easier to create and customize, so scripts will be deprecated.

## Available strategies
- [Pure Market Making](/strategies/pure-market-making)

## How it works

After configured, the script will start automatically once a strategy starts and it stops when the strategy stops.
The script is run on a new dedicated process, in case where the script fails or has a bug, your main Hummingbot
application can still function.

## Create your own script

1. Create a new script file, you can see examples in the Examples section below, and save it into `scripts` folder
2. Configure your Hummingbot
   1. Inside Hummingbot run command `config script_enabled` and/or `config script_file_path`.
   2. Editing `conf_global.yml` file using a text editor.
   ```json
   script_enabled: true
   script_file_path: spreads_adjusted_on_volatility_script.py
   ```
3. Start running a strategy

The following examples can be found in `/scripts` folder.

### hello_world_script.py

The most basic example only a few lines of code.

### ping_pong_script.py

Replicates our current ping pong strategy using script.

### price_band_script.py

Replicates our current price band strategy using script.

### dynamic_price_band_script.py

Demonstrates how to set the band around mid price moving average, the band moves as the average moves.

### spreads_adjusted_on_volatility_script.py

Demonstrates how to adjust bid and ask spreads dynamically based on price volatility.

### script_template.py

Provides you a base template to start using the scripts functions.

## Script base class

See [this article](script-base) for a description of the methods in the Script Base class.


## Updating your scripts

We sometimes add/remove/edit commands in the helper scripts along with certain new features like the [Scripts](/release-notes/0.29.0) we released in version 0.29.0, and you would need to update your scripts.

Copy the commands below and paste them into the shell or terminal to delete the old scripts and download the most recently updated ones.

### Linux

```Linux
rm -rf create.sh start.sh update.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

### MacOS

```MacOS
rm -rf create.sh start.sh update.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```
