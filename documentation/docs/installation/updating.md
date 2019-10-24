# How to update Hummingbot

## Update via Docker

We regularly update Hummingbot (see [Releases](/release-notes/)) and recommend users to regularly update their installations to get the latest version of the software.  

Updating to the latest docker image (e.g. `coinalpha/hummingbot:latest`) requires users to (1) delete any instances of Hummingbot using that image, (2) delete the old image, and (3) recreate the Hummingbot instance:

```bash tab="Script"
./update.sh
```

```bash tab="Detailed Commands"
# 1) Delete instance
docker rm hummingbot-instance

# 2) Delete old hummingbot image
docker image rm coinalpha/hummingbot:latest

# 3) Re-create instance with latest hummingbot release
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```


## Update from source

Download the latest code from GitHub:

```
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

```
# From the *root* folder:
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/update.sh
chmod a+x update.sh
./update.sh
```


## Installing from specific version via Docker
`$TAG` = Hummingbot version e.g. `version-0.16.0` For more information, visit the list of versions of [Hummingbot tags](https://hub.docker.com/r/coinalpha/hummingbot/tags).

```
$ ./create.sh 

** ✏️  Creating a new Hummingbot instance **

ℹ️  Press [enter] for default values.

➡️  Enter Hummingbot version: [latest|development] (default = "latest")
$TAG
```
