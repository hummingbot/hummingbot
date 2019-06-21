# Windows Installation from Docker

Using a pre-compiled version of `hummingbot` from Docker allows you to run `hummingbot` with a single line command.

Docker images of `hummingbot` are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

## Installing Hummingbot via the Docker Toolbox

For Windows users without Windows-Pro or Windows-Enterprise, you will need to install the Docker Toolbox, as Windows-Home is not supported by the standard Docker application. Below, we list instructions for running Hummingbot using the Docker Toolbox.

### 1. Install Docker Toolbox

Download the latest version Docker Toolbox .exe file at the following link: [Docker Toolbox Releases](https://github.com/docker/toolbox/releases/).

![Docker Download](/assets/img/docker_toolbox_download.PNG)

Locate the installer in the downloads folder and run a full installation with included VirtualBox and Git for Windows. (Git is the default shell used by Docker)

![Docker Installation](/assets/img/docker_toolbox_install.PNG)

By default, a shortcut to the Docker Quickstart terminal will be created on your desktop. You can open Docker Toolbox using this shortcut.

![Docker Startup](/assets/img/docker_toolbox_startup.PNG)

### 2. Create new instance of `hummingbot`

Open Docker Toolbox using the Quickstart shortcut. It may take a few minutes to initialize. Proceed to the next step when you reach the following screen.

![Docker Ready](/assets/img/docker_toolbox_cmdline.PNG)

Once Docker is ready, enter the following commands into the command line:

* Create directories for your configurations and log files. These will be located in C:/users/YOUR_USER_NAME.

```
mkdir ~/hummingbot_conf && \
mkdir ~/hummingbot_logs
```
* Set these paths as temporary variables so that Docker is given a path into your system directory.

```
export CONF_PATH=~/hummingbot_conf && \
export LOGS_PATH=~/hummingbot_logs
```

* Finally, download, extract, and run Hummingbot by using the following commands, which choose the container name, mount the `conf` and `log` paths, and specify the image link.

```
docker run -it \
--name myhummingbot \
--mount "type=bind,source=$CONF_PATH,destination=/conf/" \
--mount "type=bind,source=$LOGS_PATH,destination=/logs/" \
coinalpha/hummingbot:latest
```

After Docker has finishing downloading, extracting, and compiling the image, you should see the Hummingbot main screen. You're ready to start market making!

![Hummingbot CLI](/assets/img/hummingbot-cli.png)

!!! info "Mounting Existing `config` and `log` Folders"
    If you have existing `hummingbot_conf/` and `hummingbot_logs/` folders, you can replace the default paths provided here with the paths to your own. You can also skip making new directories.

### 3. Restarting Hummingbot

After you exit the Hummingbot image, Docker will automatically stop running the container. This means you need to restart it before you can access Hummingbot again. This requires the following two commands:

* `docker start myhummingbot` - This restarts the container and makes the image usable.
* `docker attach myhummingbot`- This connects to the image after you have started it.

!!! note "Running multiple bots at once"
    Currently Hummingbot does not support running multiple bots from a single image. In order to run multiple bots at the same time, you will need to download and run multiple images. While these can reuse the same `conf` and `log` files, you will need to provide a unique name for each container.

## Reference: Useful Docker commands

Command | Description
---|---
`docker ps` | List existing, running containers
`docker images` | List existing, running images
`docker start $NAME` | Start an existing, previously created container
`docker attach $NAME` | Connect to an existing, running container
`docker --help` | See the full list of docker options and commands

## Updating your Hummingbot version

The series of commands below will update an existing instance of `hummingbot` with the latest publicly available release.

```
# Remove the old version
docker rm myhummingbot && \
docker image rm coinalpha/hummingbot:latest

# Reset the conf and log paths
export CONF_PATH=~/hummingbot_conf && \
export LOGS_PATH=~/hummingbot_logs

# Install the new version
docker run -it \
--name myhummingbot \
--mount "type=bind,source=$CONF_PATH,destination=/conf/" \
--mount "type=bind,source=$LOGS_PATH,destination=/logs/" \
coinalpha/hummingbot:latest
```

---
