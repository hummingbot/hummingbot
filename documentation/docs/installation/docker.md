# Running Hummingbot via Docker

Using a pre-compiled version of Hummingbot from Docker allows you to run instances with a few simple commands.

Docker images of Hummingbot are available on Docker Hub at [coinalpha/hummingbot](https://hub.docker.com/r/coinalpha/hummingbot).

!!! warning
    The instructions below assume you already have Docker installed.  If you do not have Docker installed, you can follow the appropriate installation guide for your system: 
    
    - [Docker for Linux](/installation/linux)
    - [Docker for MacOS](/installation/macOS)
    - [Docker for Windows](/installation/windows)

## Automated Docker Scripts (Optional)

We have created Docker command install scripts (for additional details, navigate to [Github: Hummingbot Docker scripts](https://github.com/CoinAlpha/hummingbot/tree/development/installation/docker-commands)).

Copy the commands below and paste into Terminal to download and enable the automated scripts.

```bash tab="Linux"
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/connect.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
chmod a+x *.sh
```

```bash tab="MacOS"
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/connect.sh -o connect.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh
chmod a+x *.sh
```

## Installing Hummingbot

In order to make Hummingbot as easy to use as possible, we recommend creating a directory for all related files and running the instance using that directory as the base. This can be done by following the commands below:

!!! note "Note for Windows Users"
    You must first enter `cd ~` in order to navigate to the appropriate directory prior to running any of the commands below.

```bash tab="Summary Commands"
# 1) Create folder for your new instance and navigate inside
mkdir hummingbot_files && cd hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_conf && mkdir hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

```bash tab="Detailed Commands"
# 1) Create folder for your new instance
#    You can choose to name this folder something other than "hummingbot_files"
mkdir hummingbot_files

# 2) Navigate to the folder
cd hummingbot_files

# 3) Create folder for config files
mkdir hummingbot_conf

# 4) Create folder for log files
mkdir hummingbot_logs

# 5) Launch a new instance of hummingbot
#    The command below names your new instance "hummingbot-instance" (line 19)
#    and uses the "latest" docker image (line 22).
#    Lines 20-21 specify the location for the folders created in steps 3 and 4.
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Connecting to a Running Hummingbot Instance

If you exited terminal (e.g. closed window) and left Hummingbot running, the following command will reconnect to your Hummingbot instance:

```
docker attach hummingbot-instance
```

## Restarting Hummingbot after Shutdown

If you have previously created an instance of Hummingbot which you shut down (e.g. by command `exit`), the following command restarts the intance and connects to it:

```bash tab="Concise Command"
docker start hummingbot-instance && docker attach hummingbot-instance
```

```bash tab="Detailed Commands"
# 1) Start hummingbot instance
docker start hummingbot-instance

# 2) Connect to hummingbot instance
docker attach hummingbot-instance
```

## Updating Hummingbot

We regularly update Hummingbot (see: [releases](/release-notes/)) and recommend users to regularly update their installations to get the latest version of the software.  

Updating to the latest docker image (e.g. `coinalpha/hummingbot:latest`) requires users to (1) delete any instances of Hummingbot using that image, (2) delete the old image, and (3) recreate the Hummingbot instance:

```bash tab="Concise Commands"
# 1) Navigate to your instance folder
cd hummingbot_files

# 2) Delete instance and old hummingbot image
docker rm hummingbot-instance && \
docker image rm coinalpha/hummingbot:latest

# 3) Re-create instance with latest hummingbot release
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

```bash tab="Detailed Commands"
# 1) Navigate to your instance folder
cd hummingbot_files

# 2) Delete instance
docker rm hummingbot-instance

# 3) Delete old hummingbot image
docker image rm coinalpha/hummingbot:latest

# 4) Re-create instance with latest hummingbot release
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Enabling Copy and Paste in Docker Toolbox (Windows)

By default, the Docker Toolbox has copy and paste disabled within the command line. This can make it difficult to port long API and wallet keys to Hummingbot. However, there is a simple fix which can be enabled as follows:

* Open up the Docker Toolbox via the Quickstart Terminal

![](/assets/img/docker_toolbox_startup.PNG)

* Right-click on the title bar of Toolbox and select "Properties"

![](/assets/img/docker_toolbox_properties.png)

* Check the box under the "Options" tab to enable "Ctrl Key Shortcuts"

![](/assets/img/docker_toolbox_enable.png)

Close any warnings, and you're done! Just hit enter to move onto the next line and you should be able to copy and paste text using **Ctrl+Shift+C** and **Ctrl+Shift+V**.

## Hummingbot Setup

#### Docker Command Parameters

The instructions on this page assume the following variable names and/or parameters.  You can customize these names.

Parameter | Description
---|---
`hummingbot_files` | Name of the folder where your config and log files will be saved
`hummingbot-instance` | Name of your instance
`latest` | Image version, e.g. `latest`, `development`, or a specific version such as `0.9.1`
`hummingbot_conf` | Folder in `hummingbot_files` where config files will be saved (mapped to `conf/` folder used by Hummingbot)
`hummingbot_logs` | Folder in `hummingbot_files` where logs files will be saved (mapped to `logs/` folder used by Hummingbot)

#### Config and Log Files

The above methodology requires you to explicitly specify the paths where you want to mount the `conf/` and `logs/` folders on your local machine.

The example commands above assume that you create three folders:

```
hummingbot_files       # Top level folder for your instance
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
└── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
```

!!! info "`docker run` command and the `hummingbot_files` folder"
    - The `docker run` command (when creating a new instance or updating Hummingbot version) must be run from the folder that contains the `hummingbot_files` folder. By default, this should be the root folder.
    - You must create all folders prior to using the `docker run` command.

## FAQs / Troubleshooting for Docker

#### How do I find out the name of my hummingbot instance?

Run the following command to list all docker instances you have created:

```
docker ps -a
```

#### How do I list all the containers I have created?

```
docker ps -a
```

#### How do I check that my Hummingbot instance is running?

The following command will list all currently running docker containers:

```
docker ps
```

#### How do I find out where the config and log files are on my local computer?

Run the following command to view the details of your instance:

```
docker inspect hummingbot-instance
```

Look for a field `Mounts`, which will describe where the folders are on you local machine:

```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_conf",
        "Destination": "/conf",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_logs",
        "Destination": "/logs",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    }
],
```

#### How do I connect to my Hummingbot instance?

```
docker attach hummingbot-instance
```

#### How do I edit the conf files or access the log files used by my docker instance?

You can access the files from your local file system, in the `hummingbot_conf` and `hummingbot_logs` folders on your machine.  The docker instance reads from/writes to these local files.

#### Common Errors with Windows + Docker

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