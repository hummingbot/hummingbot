Hummingbot can automatically start the execution of a previously configured trading strategy upon launch without requiring the Hummingbot interface `config` and `start` commands.  Any parameters that are required for `config` can be passed into the Hummingbot launch command. Note, config-password (or wallet-password) is the password used for decrypting encrypted configuration and key files and must be supplied. 

## Docker launch commands

```bash tab="Docker command"
docker run -it \
-e STRATEGY=${STRATEGY} \
-e CONFIG_FILE_NAME=${CONFIG_FILENAME} \
-e WALLET=${WALLET} \
-e CONFIG_PASSWORD=${CONFIG_PASSWORD} \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

```bash tab="Sample entry"
docker run -it \
-e STRATEGY=pure_market_making \
-e CONFIG_FILE_NAME=conf_pure_market_making_strategy_0.yml \
-e WALLET=0xC20a16c2A01lkr8A9Dea8DCe49AFF9d3A3488bFa \
-e CONFIG_PASSWORD=mypassword123 \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

### Optional commands

Use Docker's restart policy of **always** to restart the container if it exits.

```
docker run -it --restart=always \ ...
```

Adding the option `-d` or `--detach` will start the container without attaching.

```
docker run -itd \ ...
```

More information can be found in [Docker documentation](https://docs.docker.com/engine/reference/commandline/run/).

## Source launch commands

```bash tab="Installed from source"
bin/hummingbot_quickstart.py \
--strategy ${STRATEGY} \
--config-file-name ${CONFIG_FILENAME} \
--config-password ${CONFIG-PASSWORD}
--wallet ${WALLET} \
```

```bash tab="Sample entry"
bin/hummingbot_quickstart.py \
--strategy pure_market_making \
--config-file-name conf_pure_market_making_strategy_0.yml \
--wallet 0xC20a16c2A01lkr8A9Dea8DCe49AFF9d3A3488bFa \
--config-password mypassword123 \
```