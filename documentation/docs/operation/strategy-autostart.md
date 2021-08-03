# Strategy Autostart

## Docker autostart

!!! warning
    This is a recently released experimental feature. Running any trading bots without manual supervision may incur additional risks. It is imperative that you thoroughly understand and test the strategy and parameters before deploying bots that can trade in an unattended manner.

Hummingbot can automatically start the execution of a previously configured trading strategy upon launch without needing user interaction when provided with pre-existing configuration files. This can be very useful if you wish to deploy already well-tested strategies and configurations to cloud services and have Hummingbot running automatically in the background.

### Prerequisites

- You have Hummingbot installed via Docker
- You have already connected exchanges by adding API keys
- You have at least one strategy configuration file that has been set up previously

### Locating config files

If you used the **Scripts** method via Docker, the configuration folder is the path printed at the `=> config files:` line, when you run `./create.sh`.

If you used the **Manual** method, the configuration folder is `$(pwd)/hummingbot_files/hummingbot_conf` at the time when you run `docker run`.

If your Hummingbot docker instance is already running, you can inspect the volume mount paths of your Hummingbot container with the following command:

```
docker inspect ${HUMMINGBOT_CONTAINER_NAME} --format='{{.Mounts}}'
```

The configuration folder is the mount path that corresponds to `/conf` in the volume mounts listing.

### How to autostart

An unattended Hummingbot installation is very similar to the Docker manual installation steps. The only differences are:

1.  You will copy the pre-existing configuration files to the `hummingbot_conf` directory.
2.  You will set some environment variables telling Hummingbot which strategy configuration to use and the password to decrypt your API keys and wallets.

```bash
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data
mkdir hummingbot_files/hummingbot_scripts
mkdir hummingbot_files/hummingbot_certs

# 3) Copy config files from pre-existing config folder
cp -a <existing config path>/*.yml <existing config path>/*.json hummingbot_files/hummingbot_conf/

# 4) Set environment variables specifying the strategy config file to use, and the decryption password
export STRATEGY=<strategy name>
export CONFIG_FILE_NAME=<strategy config file name>
export CONFIG_PASSWORD=<config password>

# 5) Launch unattended instance of Hummingbot
docker run -d \
  --name hummingbot-instance \
  --network host \
  --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
  --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
  --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
  --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_scripts,destination=/scripts/" \
  --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_certs,destination=/certs/" \
  -e STRATEGY -e CONFIG_FILE_NAME -e CONFIG_PASSWORD \
  coinalpha/hummingbot:latest

# 6) Clean up
unset STRATEGY CONFIG_FILE_NAME CONFIG_PASSWORD
```

The Hummingbot instance will be running in the background. You can bring it to foreground via

```
docker attach hummingbot-instance
```

You can then detach from the container and put it back to the background by pressing `CTRL-p` and then `CTRL-q`.

### Optional commands

Use Docker's restart policy to **always** restart the container if it exits.

```
docker run -it --restart=always \ ...
```

Adding the option `-d` or `--detach` will start the container without attaching.

```
docker run -itd \ ...
```

More information can be found in [Docker documentation](https://docs.docker.com/engine/reference/commandline/run/).

## Source autostart

### Prerequisites

- You have Hummingbot installed via Source.
- You have already connected exchanges by adding API keys
- You have at least one strategy configuration file that has been set up previously

### Locating config files

Whichever you used was it the **Scripts** or **Manual** method from Source, the configuration folder is located inside the `hummingbot` folder, the path is where you installed your Hummingbot.

### How to autostart

Running unattended Hummingbot is very similar to running hummingbot manually. The only differences are:

- You will read the pre-existing configuration files to the `conf` directory.
- You will pass some parameters telling Hummingbot which strategy configuration to use and the password to decrypt your API keys and wallets.

```
bin/hummingbot_quickstart.py -f CONFIG_FILE_NAME -p CONFIG_PASSWORD
```

Where  
`STRATEGY` is the strategy name  
`CONFIG_FILE_NAME` is the strategy config file name  
`CONFIG_PASSWORD` is the config password

- More information on strategy can be found in [Strategy](/strategies/overview).
- More information on configuration file name can be found in [Configuring Hummingbot](/operation/config-files).
- More information on password can be found in [Create a secure password](/operation/password).
