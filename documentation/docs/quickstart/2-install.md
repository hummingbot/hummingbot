# [Quickstart] Install Hummingbot

Below, we show you how to install Hummingbot using our installation scripts for each supported platform. We highlight the Docker image method for new users since it contains all necessary dependencies.

If you would like to install from source or see the detailed installation instructions, see [Installation](/installation) in the User Manual.


## Step 1: Install Docker

If you don't already have Docker, we show you how to install Docker for each platform. Docker is an open source containerization product that pre-packages all dependencies into a single container, greatly simplifying the installation process.

### Linux/Cloud

Install `tmux` to allow you to easily run Hummingbot remotely:

!!! note
    To learn more about `tmux` please visit [getting-started-with-tmux](https://linuxize.com/post/getting-started-with-tmux/).

```bash tab="Ubuntu / Debian"
sudo apt-get update
sudo apt-get install -y tmux
```

```bash tab="CentOS"
sudo yum -y install tmux
```

Install Docker:
```bash
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh

# Note: The script will close the terminal window
```

!!! warning "Restart Terminal"
    The above commands will close your terminal/bash window in order to enable the correct permissions for the `docker` command. Close and restart your bash/terminal window if it did not close automatically.

### MacOS

You can install Docker by [downloading an installer](https://docs.docker.com/v17.12/docker-for-mac/install/) from the official page. After you have downloaded and installed Docker, restart your system if necessary.

### Windows

Download the latest version Docker Toolbox .exe file at the following link: [Docker Toolbox Releases](https://github.com/docker/toolbox/releases/).

![Docker Download](/assets/img/docker_toolbox_download.PNG)

Locate the installer in the downloads folder and run a full installation with included VirtualBox and Git for Windows. (Git is the default shell used by Docker)

![Docker Installation](/assets/img/docker_toolbox_install.PNG)

By default, a shortcut to the Docker Quickstart terminal will be created on your desktop. You can open Docker Toolbox using this shortcut.

![Docker Startup](/assets/img/docker_toolbox_startup.PNG)


## Step 2: Install Hummingbot

### Using Automated Docker Scripts
We have created helper scripts that simplify the process of installing and running Hummingbot with Docker:

* `create.sh`: Creates a new instance of Hummingbot
* `start.sh`: Starts Hummingbot
* `update.sh`: Updates Hummingbot

The scripts help you install an instance of Hummingbot and set up folders to house your logs and configuration files:
```
hummingbot_files       # Top level folder for hummingbot-related files
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
└── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
```

!!! warning
    When you update Hummingbot, use the `update.sh` helper script. Do not delete these folders; otherwise, your configuration info may be lost.


### Linux/Cloud

Open a new Bash window and run `tmux` to create a new process:
```
tmux
```

Aftewards, run the following commands:
```bash
# 1) Download Hummingbot helper scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Run install script
./create.sh
```

Afterwards, you should see the Hummingbot client interface. Proceed to [Configure a Bot](/quickstart/3-configure-bot).

### MacOS

Open a Terminal window and run the following commands:
```bash
# 1) Download Hummingbot helper scripts
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Run install script
./create.sh
```

Afterwards, you should see the Hummingbot client interface. Proceed to [Configure a Bot](/quickstart/3-configure-bot).


### Windows

Open Docker Toolbox using the Docker Quickstart desktop shortcut. You should see the following screen:

![Docker Ready](/assets/img/docker_toolbox_cmdline.PNG)

From inside the Docker Toolbox window, run the following commands:

```bash
# 1) Navigate to root folder
cd ~

# 2) Download Hummingbot helper scripts
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh

# 3) Enable script permissions
chmod a+x *.sh

# 4) Run install script
./create.sh
```

Afterwards, you should see the Hummingbot client interface. Proceed to [Configure a Bot](/quickstart/3-configure-bot).

---
# Next: [Configure Your First Trading Bot](/quickstart/3-configure-bot)
