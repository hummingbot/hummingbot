# Running Hummingbot with Docker

Using a pre-compiled version of `hummingbot` from Docker allows you to run `hummingbot` with a single line command.

Docker images of `hummingbot` are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

!!! note "Docker installation guides"
    The instructions below assume you already of Docker installed.  If you do not have Docker installed, you can follow the installation guides:

    - [Docker for Windows](/installation/docker_windows/)
    - [Docker for MacOS](/installation/docker_macOS/)
    - [Docker for Linux](/installation/docker_linux/)


---

## Docker commands for MacOSX/Linux

The commands below are the install, restart, and update commands for Docker in MacOSX or Linux.

!!! note "You can customize the following parameters in the commands below"
    - `my-instance-1`: name of your instance
    - `latest`: the image version, e.g. `latest`, `development`, or a specific version `0.8.1`
    - `hummingbot_conf`: path on your host machine for `conf/`
    - `hummingbot_logs`: path on your host machine for `logs/`

### Create new instance

The commands below (1) create a new `my-instance-1` folder for your instance and (2) `hummingbot_conf` and `hummingbot_logs` folders within that folder.

The third command creats and starts up the instance of Hummingbot.

```
# 1) Create folder for your new instance and navigate inside
mkdir my-instance-1 && cd my-instance-1

# 2) Create folders for log and config files
mkdir hummingbot_conf && mkdir hummingbot_logs

# 3) Launch new hummingbot instance hummingbot
docker run -it \
--name my-instance-1 \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

### Restart instance

The command below restarts and attaches to a previously created instance:

```
docker start my-instance-1 && docker attach my-instance-1
```

### Update Hummingbot version 

The command below updates the hummingbot image and re-creates the instance:

```
# 1) Navigate to your instance folder
cd my-instance-1

# 2) Delete instance and old hummingbot image
#    Re-create instance with latest hummingbot release
docker rm my-instance-1 && \
docker image rm coinalpha/hummingbot:latest && \
docker run -it \
--name my-instance-1 \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

----

## Docker commands for Windows

The commands below will create a new `my-instance-1` folder in `C:/users/YOUR_USER_NAME.`

The commands below are the install, restart, and update commands for Docker in Windows.

!!! note "You can customize the following parameters in the commands below"
    - `my-instance-1`: name of your instance
    - `latest`: the image version, e.g. `latest`, `development`, or a specific version `0.8.1`
    - `hummingbot_conf`: path on your host machine for `conf/`
    - `hummingbot_logs`: path on your host machine for `logs/`

### Create new instance

The commands below (1) create a new `my-instance-1` folder for your instance and (2) `hummingbot_conf` and `hummingbot_logs` folders within that folder.

The third command creats and starts up the instance of Hummingbot.

```
# 1) Create folder for your new instance and navigate inside
mkdir ~/my-instance-1 && cd ~/my-instance-1

# 2) Create folders for log and config files
mkdir hummingbot_conf && mkdir hummingbot_logs

# 3) Launch new hummingbot instance hummingbot
docker run -it \
--name my-instance-1 \
--mount "type=mount,source=~/my-instance-1/hummingbot_conf,destination=/conf/" \
--mount "type=mount,source=~/my-instance-1/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

### Restart instance

The command below restarts and attaches to a previously created instance:

```
docker start my-instance-1 && docker attach my-instance-1
```

### Update Hummingbot version

The command below updates the hummingbot image and re-creates the instance

```
# 1) Navigate to your instance folder
cd ~/my-instance-1

# 2) Delete instance and old hummingbot image
#    Re-create instance with latest hummingbot release
docker rm my-instance-1 && \
docker image rm coinalpha/hummingbot:latest && \
docker run -it \
--name my-instance-1 \
--mount "type=mount,source=~/my-instance-1/hummingbot_conf,destination=/conf/" \
--mount "type=mount,source=~/my-instance-1/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

---

## Config and log files

The above methodology requires you to explicitly specify the paths where you want to mount the `conf/` and `logs/` folders on your local machine.

The example commands above assume that you create three folders:

```
my-instance-1          # Top level folder for your instance
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
└── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
```

!!! info "`docker run` command from `my-instance-1` folder"
    - The `docker run` command (when creating a new instance or updating `hummingbot` version) must be run from inside of the `my-instance-1` folder.
    - You must create the folders prior to running the `docker run` command.
