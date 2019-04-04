# Install from Docker

Using a pre-compiled version of `hummingbot` from Docker allows you to run `hummingbot` with a single line command.

Docker images of `hummingbot` are available on Docker Hub at [coinalpha/hummingbot](https://cloud.docker.com/u/coinalpha/repository/docker/coinalpha/hummingbot).

## Create new instance of `hummingbot`

``` bash tab="Terminal: Start hummingbot with Docker"
docker run -it \
--name $NAME \
-v "$PWD"/conf/:/conf/ \
-v "$PWD"/logs/:/logs/ \
coinalpha/hummingbot:$TAG
```

!!! note "Command Variables"
    Replace `$TAG` with the image version, such as `latest`, and `$NAME` with a label you choose, such as 'WETH-USDC'

---

## Config and log files

When creating the instance for the first time, the `docker run` command above will create two new folders on your computer and mount them to your instance:

- `conf/`: where configuration files will be stored
- `log/`: where logs will be stored

![docker setup](/assets/img/docker-file-setup.png "Docker file system setup")

!!! info "Mounting Existing `config` and `log` Folders"
    If you have existing `conf/` and `log/` folders, running the command above will mount the existing `conf/` and `log/` folders to the newly created docker container instance and allow you to continue using those files.

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