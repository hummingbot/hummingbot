# Running Hummingbot via Docker

Using a pre-compiled version of Hummingbot from Docker allows you to run instances with a few simple commands.

Docker images of Hummingbot are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

!!! warning
    The instructions below assume you already have Docker installed.  If you do not have it installed, you can follow the appropriate installation guide for your system: <br/><br/><ul><li>[Docker for Windows](/installation/docker_windows)</li><li>[Docker for MacOS](/installation/docker_macOS)</li><li>[Docker for Linux](/installation/docker_linux)</li></ul>

## Installing Hummingbot

In order to make Hummingbot as easy to use as possible, we recommend creating a directory for all related files and running the instance using that directory as the base. This can be done by following the commands below:

!!! note
    For Windows users, you must enter the following command **first** in order to get your directory to the right place: `cd ~`

```
# 1) Create folder for your new instance and navigate inside
mkdir myhummingbot && cd myhummingbot

# 2) Create folders for log and config files
mkdir hummingbot_conf && mkdir hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name myhummingbot \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

!!! note "You can customize the parameters above"
    - `myhummingbot`: the name of your instance
    - `latest`: the image version, e.g. `latest`, `development`, or a specific version such as `0.9.1`
    - `hummingbot_conf`: path on your host machine for `conf/`
    - `hummingbot_logs`: path on your host machine for `logs/`

### Config and Log Files

The above methodology requires you to explicitly specify the paths where you want to mount the `conf/` and `logs/` folders on your local machine.

The example commands above assume that you create three folders:

```
myhummingbot           # Top level folder for your instance
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
└── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
```

!!! info "`docker run` command from `myhummingbot` folder"
    - The `docker run` command (when creating a new instance or updating Hummingbot version) must be run from inside of the `myhummingbot` folder.
    - You must create all folders prior to using the `docker run` command.

## Restarting Hummingbot

For users unfamiliar with Docker, it may not be clear how to restart Hummingbot given the immediate start after the initial download. Doing so, however, is very simple with the right command.

```
# 1) Restart and connect to your Hummingbot image
docker start myhummingbot && docker attach myhummingbot
```

## Updating Hummingbot

Hummingbot does not currently have a way of updating existing releases. Instead, users must delete the old image and re-install the newer version. See below for the required commands:

```
# 1) Navigate to your instance folder
cd myhummingbot

# 2) Delete instance and old hummingbot image
docker rm myhummingbot && \
docker image rm coinalpha/hummingbot:latest

# 3) Re-create instance with latest hummingbot release
docker run -it \
--name myhummingbot \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Enabling Copy and Paste in Docker Toolbox

By default, the Docker Toolbox has copy and paste disabled within the command line. This can make it difficult to port long API and wallet keys to Hummingbot. However, there is a simple fix which can be enabled as follows:

* Open up the Docker Toolbox via the Quickstart Terminal

![](/assets/img/docker_toolbox_startup.PNG)

* Right-click on the title bar of Toolbox and select "Properties"

![](/assets/img/docker_toolbox_properties.png)

* Check the box under the "Options" tab to enable "Ctrl Key Shortcuts"

![](/assets/img/docker_toolbox_enable.png)

Close any warnings, and you're done! Just hit enter to move onto the next line and you should be able to copy and paste text using **Ctrl+Shift+C** and **Ctrl+Shift+V**.

## Handling Common Errors

Windows users may encounter the following error when running the Docker Toolbox for Windows:

```
C:\Program Files\Docker Toolbox\docker.exe: Error response from daemon: Get https://registry-1.docker.io/v2/: net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers).
See 'C:\Program Files\Docker Toolbox\docker.exe run --help'.
```

This appears to be an environment configuration problem. The solution is to refresh the environment settings and restart the environment which can be done with the following commands:

```
docker-machine restart default      # Restart the environment
eval $(docker-machine env default)  # Refresh your environment settings
```
