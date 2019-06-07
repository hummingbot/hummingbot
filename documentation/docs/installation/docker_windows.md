# Install from Docker

Using a pre-compiled version of `hummingbot` from Docker allows you to run `hummingbot` with a single line command.

Docker images of `hummingbot` are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

## Docker installation for Windows

For Windows users without Windows-Pro or Windows-Enterprise, you will need to install the Docker Toolbox. Download the latest version Toolbox .exe file at the following link: [Docker Toolbox Releases](https://github.com/docker/toolbox/releases/).

Install Toolbox from the .exe file, including VirtualBox and Git if you do not have those on your computer. Otherwise, maintain default settings and restart after installation.

You can now open Docker via the Quickstart Terminal. On the first start-up, give the Toolbox a few minutes to initialize.

## Create new instance of `hummingbot` (Windows)

``` bash tab="Terminal: Start hummingbot with Docker"
# 1) Create a label for your container and specify which docker 
#    image of hummingbot to use
export NAME=myhummingbot && \
export TAG=latest

# 2) Specify the path to folders where you would like to save
#    your config and log files
export CONF_PATH=~/hummingbot_conf && \
export LOGS_PATH=~/hummingbot_logs

# 3) If the folders do not exist, create them:
mkdir ~/hummingbot_conf && \
mkdir ~/hummingbot_logs

# 4) Launch hummingbot with the parameters you specified
docker run -it \
--name $NAME \
--mount "type=bind,source=$CONF_PATH,destination=/conf/" \
--mount "type=bind,source=$LOGS_PATH,destination=/logs/" \
coinalpha/hummingbot:$TAG
```

!!! note "Command Variables"
    - In the four `export` commands, replace the values with your custom values.  
    - `NAME`: name of your container, such as `myhummingbot`
    - `TAG`: with the image version, e.g. `latest`, `development`, or a specific version `0.7.0`
    - `CONF_PATH`: path on your host machine for `conf/`
    - `LOGS_PATH`: path on your host machine for `logs/`

---

## Config and log files

The above methodology requires you to explicitly specify the paths where you want to mount the `conf/` and `logs/` folders on your local machine.

Note: you must create the folders prior to running the `docker run` command.

The folders required on your computer are:

- `hummingbot_conf/`: maps to `conf/` folder in the container, where configuration files will be stored
- `hummingbot_log/`: maps to `logs` folder in the container, where logs will be stored

![docker setup](/assets/img/docker-file-setup.png "Docker file system setup")

!!! info "Mounting Existing `config` and `log` Folders"
    If you have existing `hummingbot_conf/` and `hummingbot_logs/` folders, running the command above will mount the existing `hummingbot_conf/` and `hummingbot_logs/` folders to the newly created docker container instance and allow you to continue using those files.

## Reference: Useful Docker commands

Command | Description
---|---
`docker ps` | List existing, running containers
`docker start $NAME` | Start an existing, previously created container
`docker attach $NAME` | Connect to an existing, running container

## Update Hummingbot version

The following command will update an existing instance of `hummingbot` with a new, specified version:

```bash
docker rm $NAME && \
docker image rm coinalpha/hummingbot:$OLD_TAG && \
docker run -it \
--name $NAME \
-v "$PWD"/conf/:/conf/ \
-v "$PWD"/logs/:/logs/ \
coinalpha/hummingbot:$NEW_TAG
```

---
