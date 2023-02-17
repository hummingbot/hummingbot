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
wget https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

#### MacOS
```
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

#### Windows (Docker Toolbox)
```
cd ~
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/hummingbot/hummingbot/development/installation/docker-commands/update.sh -o update.sh
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
