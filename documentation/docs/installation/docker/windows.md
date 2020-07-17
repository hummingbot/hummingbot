# Windows Installation Using Docker

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

* Install in [the cloud](/installation/cloud) and use a native Linux virtual machine.
* Install using Docker version: [Docker Toolbox](https://docs.docker.com/toolbox/toolbox_install_windows/) recommended.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

## Installing Hummingbot via the Docker Toolbox

For Windows users without Windows-Pro or Windows-Enterprise, you will need to install the Docker Toolbox, as Windows-Home is not supported by the standard Docker application. Below, we list instructions for running Hummingbot using the Docker Toolbox.

### Step 1. Install Docker Toolbox

Download the latest version Docker Toolbox .exe file at the following link: [Docker Toolbox Releases](https://github.com/docker/toolbox/releases/).

![Docker Download](/assets/img/docker_toolbox_download.PNG)

Locate the installer in the downloads folder and run a full installation with included VirtualBox and Git for Windows. (Git is the default shell used by Docker)

![Docker Installation](/assets/img/docker_toolbox_install.PNG)

By default, a shortcut to the Docker Quickstart terminal will be created on your desktop. You can open Docker Toolbox using this shortcut.

![Docker Startup](/assets/img/docker_toolbox_startup.PNG)

### Step 2. Run Hummingbot

Open Docker Toolbox using the Quickstart shortcut. Move onto the next step when you reach the following screen.

![Docker Ready](/assets/img/docker_toolbox_cmdline.PNG)

Enter the following commands into the command line.  You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Navigate to root folder
cd ~

# 2) Download Hummingbot install, start, and update script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh

# 3) Enable script permissions
chmod a+x *.sh

# 4) Create a hummingbot instance
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Navigate to root folder
cd ~

# 2) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data
mkdir hummingbot_files/hummingbot_scripts

# 3) Launch a new instance of hummingbot
docker run -it \
--network host \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_scripts,destination=/scripts/" \
coinalpha/hummingbot:latest
```

## Running Hummingbot in the background

Press keys `Ctrl+P` then `Ctrl+Q` in sequence to detach from Docker i.e. return to command line. This exits out of Hummingbot without shutting down the container instance.

## Starting Hummingbot running in the background

Use the start script by running the command `./start.sh` to attach to a Hummingbot instance running in the background.

## Install a previous Hummingbot version

A previous version can be installed when creating a Hummingbot instance.

```bash
# 1) Run the script to create a hummingbot instance
./create.sh 

# 2) Specify the version to be installed when prompted

** ✏️  Creating a new Hummingbot instance **

ℹ️  Press [enter] for default values.

➡️  Enter Hummingbot version: [latest|development] (default = "latest")

```

 For example, enter `version-0.16.0`. The versions are listed here in [Hummingbot Tags](https://hub.docker.com/r/coinalpha/hummingbot/tags).