# Docker Commands

## Download all scipts

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

## Create an instance of Hummingbot

The `create.sh` script will create the folders needed to run Hummingbot and then install Hummingbot.

```
./create.sh
```

## Starting a previously created instance of Hummingbot

The `start.sh` script will start and connect to a previously created instance of Hummingbot.

```
./start.sh
```

## Updating Hummingbot version

The `update.sh` script will update your instance to the latest version of Hummingbot.

```
./update.sh
```