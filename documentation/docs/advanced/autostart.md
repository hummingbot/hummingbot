# Docker Autostart

**Updated in v0.27.0**

!!! warning
    This is a recently released experimental feature. Running any trading bots without manual supervision may incur additional risks. It is imperative that you thoroughly understand and test the strategy and parameters before deploying bots that can trade in an unattended manner.

Hummingbot can automatically start the execution of a previously configured trading strategy upon launch, without needing user interaction, when provided with pre-existing configuration files. This can be very useful if you wish to deploy already well-tested strategies and configurations to cloud services, and have Hummingbot running automatically in the background.


## Pre-requisites

1. You have Hummingbot installed via [Docker](/installation/docker/linux)
2. You have already connected exchanges by adding API keys
3. You have at least one strategy configuration file that has been set up previously

## Locating config files

If you used the **Easy Install** method on the [Docker installation page](/installation/docker/linux), the configuration folder is the path printed at the `=> config files:` line, when you run `./create.sh`.

If you used the **Manual Installation** method, the configuration folder is `$(pwd)/hummingbot_files/hummingbot_conf` at the time when you run `docker run`.

If your Hummingbot docker instance is already running, you can inspect the volume mount paths of your Hummingbot container with the following command:

```bash
docker inspect ${HUMMINGBOT_CONTAINER_NAME} --format='{{.Mounts}}'
```

The configuration folder is the mount path that corresponds to `/conf` in the volume mounts listing.


## How to autostart

An unattended Hummingbot installation is very similar to the Docker manual installation steps. The only differences are:

 1. You will copy the pre-existing configuration files to the `hummingbot_conf` directory.
 2. You will set some environment variables telling Hummingbot which strategy configuration to use, and the password to decrypt your API keys and wallets.

```bash
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data

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
  -e STRATEGY -e CONFIG_FILE_NAME -e CONFIG_PASSWORD \
  coinalpha/hummingbot:latest
  
# 6) Clean up
unset STRATEGY CONFIG_FILE_NAME CONFIG_PASSWORD
```

The Hummingbot instance will be running in the background. You can bring it to foreground via

```bash
docker attach hummingbot-instance
```

You can then detach from the container and put it back to the background by pressing `CTRL-p` and then `CTRL-q`.

## Optional commands

Use Docker's restart policy to **always** restart the container if it exits.

```
docker run -it --restart=always \ ...
```

Adding the option `-d` or `--detach` will start the container without attaching.

```
docker run -itd \ ...
```

More information can be found in [Docker documentation](https://docs.docker.com/engine/reference/commandline/run/).
