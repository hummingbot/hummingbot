## Docker commands

| Command | Description |
|---------|----------|
| `docker ps` | List all running containers
| `docker ps -a` | List all created containers (including stopped containers)
| `docker attach [instance_name]` | Connect to a running Docker container
| `docker start [instance_name]` | Start a stopped container
| `docker inspect [instance_name]` | View details of a Docker container, including details of mounted folders

More commands can be found in [Docker Documentation](https://docs.docker.com/engine/reference/commandline/docker/).


## Docker scripts

These commands execute the helper scripts for running Hummingbot and are performed from the terminal or shell. Ensure that the scripts are located in your current directory before running these commands.

| Command | Function |
|---------|----------|
| `./create.sh` | Creates a new instance of Hummingbot
| `./start.sh` | Connect to a running instance or restart an exited Hummingbot instance
| `./update.sh` | Update Hummingbot version

!!! tip
    Run the command `ls -l` to check the files in your current working directory.

### Updating your scripts

Copy the commands below and paste into the shell or terminal to download and enable the automated scripts.

```bash tab="Linux"
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

```bash tab="MacOS"
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

```bash tab="Windows via Docker Toolbox"
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```