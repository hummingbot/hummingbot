# Docker Commands

> The followings scripts require Docker to already be installed.  If you do not have Docker installed, please go to [Install with Docker](./install-with-docker).

## Setup: enabling user permissions

The scripts below assume that the user has `docker` permissions without requiring `sudo`.

If you do not have `docker` permissions:

1. Enter the following command:

  ```
  sudo usermod -a -G docker $USER
  ```

2. Log out and log back into the terminal to enable.

## Download all scipts

#### Linux
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create-web3.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update-web3.sh
chmod a+x *.sh
```

#### MacOS
```
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create-web3.sh -o create-web3.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update-web3.sh -o update-web3.sh
chmod a+x *.sh
```

#### Windows (Docker Toolbox)
```
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create-web3.sh -o create-web3.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update-web3.sh -o update-web3.sh
chmod a+x *.sh
```

## Create an instance of Hummingbot

The `create.sh` script will create the folders needed to run Hummingbot and then install Hummingbot.

```
./create.sh
```

## Start up / connect to an instance of Hummingbot

The `start.sh` script will connect to a running instance of Hummingbot.

```
./start.sh
```

## Updating Hummingbot version

The `update.sh` script will update your instance to the latest version of Hummingbot.

```
./update.sh
```

## Create an instance of Hummingbot which connects to a local node at http://localhost:8545
### Requires ethereum full node

This `web3` version of scripts allows a user to connect to an Ethereum node running on the Docker host.

The `create-web3.sh` is similar to the `create.sh` script; the difference is that it makes the `localhost` (127.0.0.1) available to the docker container by appending the `--network="host"` to the `docker run` command.

```
./create-web3.sh
```

## Updating Hummingbot version which connects to a local node at http:localhost:8545
### Requires ethereum full node

The `update-web3.sh` script will update your instance to the latest version of Hummingbot.

```
./update-web3.sh
```
