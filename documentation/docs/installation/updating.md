# How to update Hummingbot

## Update via Docker

We regularly update Hummingbot (see [Release Notes](/release-notes/)) and recommend users to regularly update their installations to get the latest version of the software.  

Updating to the latest docker image (e.g. `coinalpha/hummingbot:latest`) requires users to (1) delete any instances of Hummingbot using that image, (2) delete the old image, and (3) recreate the Hummingbot instance:

```bash tab="Script"
# 1) Download update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x update.sh

# 3) Run script to update hummingbot
./update.sh
```

```bash tab="Detailed Commands"
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
