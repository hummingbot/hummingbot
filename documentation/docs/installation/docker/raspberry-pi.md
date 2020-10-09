# Raspberry Pi Installation Using Docker

You can install Hummingbot with ***either*** of the following options:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

#### Step 1: Install Docker

Install Docker and change permissions.

```
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -a -G docker $USER
```

Start and automate docker.

```
sudo systemctl start docker && sudo systemctl enable docker
```

Exit terminal/shell to refresh shell.
```
Exit
```

!!! warning "Restart terminal"
    Close and restart your terminal window to enable the correct permissions for `docker` command before proceeding to [Step 2](#step-2-install-hummingbot).


#### Step 2: Install Hummingbot

Run the following commands:

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh

# 4) Pull Hummingbot ARM image when asked what version to use [ Enter Hummingbot version: [latest|development] (default = "latest")]
dev-0.31.0-arm_beta
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data
mkdir hummingbot_files/hummingbot_scripts

# 3) Launch a new instance of hummingbot
docker run -it \
--network host \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_scripts,destination=/scripts/" \
coinalpha/hummingbot:dev-0.31.0-arm_beta
```

!!! note
    This  image `dev-0.31.0-arm_beta` only works for Raspberry Pi, other branches of Hummingbot are not built for ARM architecture.


## Running Hummingbot in the background

Press keys `Ctrl+P` then `Ctrl+Q` in sequence to detach from Docker i.e. return to the command line. 

!!! note
    Detaching intance will leave your bot running but once pi shuts down, this will terminate your running instance.

## Starting Hummingbot running in the background

Use the start script by running the command `./start.sh` to attach to a Hummingbot instance running in the background.

## Install a previous Hummingbot version

A previous version can be installed when creating a Hummingbot instance.

```bash
# 1) Run the script to create a hummingbot instance
./create.sh 

# 2) Specify the version to be installed when prompted

** ✏️  Creating a new Hummingbot instance **

ℹ️  Press [enter] for default values.

➡️  Enter Hummingbot version: [latest|development] (default = "latest")
dev-0.30.0-arm_beta

```

 For example, enter `dev-0.30.0-arm_beta`. The versions are listed here in [Hummingbot Tags](https://hub.docker.com/r/coinalpha/hummingbot/tags?page=1&name=arm).