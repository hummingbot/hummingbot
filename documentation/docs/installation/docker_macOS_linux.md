# Install from Docker (MacOS/Linux)

Using a pre-compiled version of `hummingbot` from Docker allows you to run `hummingbot` with a single line command.

Docker images of `hummingbot` are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

## Docker installation for MacOS/Linux

If you do not already have Docker on your system, you will need to download the installer from the following link: [Docker Installer Downloads](https://docs.docker.com/v17.12/install/#supported-platforms).

Run the installer, and restart your computer if necessary. You should now be able to run Docker from your terminal window.

## Create new instance of `hummingbot` (MacOS/Linux)

``` bash tab="Terminal: Start hummingbot with Docker"
# 1) Create a label for your container and specify which docker 
#    image of hummingbot to use
export NAME=myhummingbot && \
export TAG=latest

# 2) Specify the path to folders where you would like to save
#    your config and log files
export CONF_PATH=$(pwd)/hummingbot_conf && \
export LOGS_PATH=$(pwd)/hummingbot_logs

# 3) If the folders do not exist, create them:
mkdir $CONF_PATH && \
mkdir $LOGS_PATH

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
