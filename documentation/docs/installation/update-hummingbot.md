# Update Version

## Update via binary

Uninstall Hummingbot locally from your computer, then download and install the latest version from the website https://hummingbot.io/download/

## Update via Docker

Hummingbot is regularly updated each month (see [Release Notes](/release-notes/overview)) and recommends users to periodically update their installations to get the latest version of the software.

Updating to the latest docker image (e.g. `coinalpha/hummingbot:latest`)

!!! note
    Make sure to stop all the containers using the same image first  before running the `./update.sh` script.

Scripts

```Script
# 1) Remove old script
rm -rf update.sh

# 2) Download update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 3) Enable script permissions
chmod a+x update.sh

# 4) Run script to update hummingbot
./update.sh
```

Manual

```Manual
# 1) Delete instance
docker rm hummingbot-instance

# 2) Delete old hummingbot image
docker image rm coinalpha/hummingbot:latest

# 3) Re-create instance with latest hummingbot release
docker run -it \
--network host \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
coinalpha/hummingbot:latest
```

## Update from source

Download the latest code from GitHub:

```bash
# From the hummingbot root folder:
git pull origin master

# Recompile the code:
conda deactivate
./uninstall
./clean
./install
conda activate hummingbot
./compile
bin/hummingbot.py
```

Alternatively, use our automated script:

```bash
# 1) Download update script to the *root* folder
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/update.sh

# 2) Enable script permissions
chmod a+x update.sh

# 3) Run script to update hummingbot
./update.sh
```
