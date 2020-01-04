# macOS Installation Using Docker

## Step 1. Install Docker

You can install Docker by [downloading an installer](https://docs.docker.com/v17.12/docker-for-mac/install/) from the official page. After you have downloaded and installed Docker, restart your system if necessary.

## Step 2. Install Hummingbot

You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
coinalpha/hummingbot:latest
```

## Install a previous Hummingbot version

A previous version can be installed when creating a Hummingbot instance.

```bash
# 1) Run the script to create a hummingbot instance
./create.sh 

# 2) Specify the version to be installed when prompted

** ✏️  Creating a new Hummingbot instance **

ℹ️  Press [enter] for default values.

➡️  Enter Hummingbot version: [latest|development] (default = "latest")

```

 For example, enter `version-0.16.0`. The versions are listed here in [Hummingbot Tags](https://hub.docker.com/r/coinalpha/hummingbot/tags).
