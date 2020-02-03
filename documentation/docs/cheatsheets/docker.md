# Running Hummingbot via Docker

Using a pre-compiled version of Hummingbot from Docker allows you to run instances with a few simple commands.

Docker images of Hummingbot are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

## Automated Docker Scripts (Optional)

We have created helper scripts that simplify the process of installing and running Hummingbot with Docker:

* `create.sh`: Creates a new instance of Hummingbot
* `start.sh`: Starts Hummingbot
* `update.sh`: Updates Hummingbot

### What do the scripts do?

The scripts help you install an instance of Hummingbot and set up folders to house your logs and configuration files.

For more details, navigate to [Github: Hummingbot Docker scripts](https://github.com/CoinAlpha/hummingbot/tree/development/installation/docker-commands).

```
hummingbot_files       # Top level folder for hummingbot-related files
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
├── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
└── hummingbot_data    # Maps to hummingbot's data/ folder, which stores the SQLite database file
```

!!! warning
    When you update Hummingbot, use the `update.sh` helper script. Do not delete these folders; otherwise, your configuration info may be lost.

### How do I use the scripts?

Copy the commands below and paste into Terminal to download and enable the automated scripts.

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

```bash tab="Windows (Docker Toolbox)"
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

## Basic Docker Commands for Hummingbot

#### Create Hummingbot Instance

The following commands will (1) create folders for config and log files, and (2) create and start a new instance of Hummingbot:

```bash tab="Script"
./create.sh
```

```bash tab="Detailed Commands"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folder for config files
mkdir hummingbot_files/hummingbot_conf

# 3) Create folder for log files
mkdir hummingbot_files/hummingbot_logs

# 4) Create folder for data files
mkdir hummingbot_files/hummingbot_data

# 5) Launch a new instance of hummingbot
#    The command below names your new instance "hummingbot-instance" (line 18)
#    and uses the "latest" docker image (line 22).
#    Lines 19-21 specify the location for the folders created in steps 2, 3 and 4.
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
coinalpha/hummingbot:latest
```

#### Restarting Hummingbot after Shutdown or Closing the Window

If you have previously created an instance of Hummingbot, the following command connects to the instance:

```bash tab="Script"
./start.sh
```

```bash tab="Detailed Commands"
# 1) Start hummingbot instance
docker start hummingbot-instance

# 2) Connect to hummingbot instance
docker attach hummingbot-instance
```

#### Running bot in background

Press keys `ctrl+P` then `ctrl+Q` in sequence to detach from Docker (i.e. return to command line). This exits out of Hummingbot without shutting down the container instance.


## Hummingbot Setup

#### Docker Command Parameters

The instructions on this page assume the following default variable names and/or parameters.  You can customize these names.

Parameter | Description
---|---
`hummingbot_files` | Name of the folder where your config and log files will be saved
`hummingbot-instance` | Name of your instance
`latest` | Image version, e.g. `latest`, `development`, or a specific version such as `version-0.9.1`
`hummingbot_conf` | Folder in `hummingbot_files` where config files will be saved (mapped to `conf/` folder used by Hummingbot)
`hummingbot_logs` | Folder in `hummingbot_files` where logs files will be saved (mapped to `logs/` folder used by Hummingbot)
`hummingbot_data` | Folder in `hummingbot_files` where data files will be saved (mapped to `data/` folder used by Hummingbot)

#### Config, Log and Data Files

The above methodology requires you to explicitly specify the paths where you want to mount the `conf/`, `logs/` and `data/` folders on your local machine.

The example commands above assume that you create three folders:

```
hummingbot_files       # Top level folder for hummingbot-related files
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
├── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
└── hummingbot_data    # Maps to hummingbot's data/ folder, which stores the SQLite database file
```

!!! info "`docker run` command and the `hummingbot_files` folder"
    - The `docker run` command (when creating a new instance or updating Hummingbot version) must be run from the folder that contains the `hummingbot_files` folder. By default, this should be the root folder.
    - You must create all folders prior to using the `docker run` command.

## Reference: Useful Docker Commands

Command | Description
---|---
`docker ps` | List all running containers
`docker ps -a` | List all created containers (including stopped containers)
`docker attach hummingbot-instance` | Connect to a running Docker container
`docker start hummingbot-instance` | Start a stopped container
`docker inspect hummingbot-instance` | View details of a Docker container, including details of mounted folders
