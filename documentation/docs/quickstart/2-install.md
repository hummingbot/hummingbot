# [Quickstart] Install Hummingbot

Below, we show you how to easily install Hummingbot using our installation scripts for each supported platform.

For more detailed instructions, refer to our [User Manual](/installation/index).

## Linux

For Linux we highlight the Docker image method for new users since it contains all necessary dependencies.

### Step 1: Install Docker

Docker is an open source containerization product that pre-packages all dependencies into a single container, greatly simplifying the installation process.

```bash
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh
```

!!! warning "Restart Terminal"
    The above commands will close your terminal/bash window in order to enable the correct permissions for the `docker` command. Close and restart your bash/terminal window if it did not close automatically.

We also have instructions for installing Docker on [Debian](/installation/via-docker/linux/#debian) and [CentOS](/installation/via-docker/linux/#centos).


### Step 2: Install Hummingbot

We have created automated docker scripts that simplify the process of installing and running Hummingbot with Docker:

* `create.sh`: Creates a new instance of Hummingbot
* `start.sh`: Starts a stopped Hummingbot instance
* `update.sh`: Updates Hummingbot

The scripts help you install an instance of Hummingbot and set up folders to house your logs, configuration files and trades/orders database file:
```
hummingbot_files       # Default name of top level folder for hummingbot-related files
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
├── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
└── hummingbot_data    # Maps to hummingbot's data/ folder, which stores the SQLite database file
```

To download the scripts and create a Hummingbot instance, run the following commands:

```bash
# 1) Download hummingbot helper scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Run create.sh script to create hummingbot instance
./create.sh
```

Afterwards, you should see the Hummingbot client interface. Proceed to [Configure a Bot](/quickstart/3-configure-bot).


## Windows and macOS

Setup and install package to install on local computer can be downloaded from our official website:

- [Download the Hummingbot client](https://hummingbot.io/download/)

You may also refer to our User Manual for more information.

- [Windows Binary Installation](/installation/from-binary/windows)
- [macOS Binary Installation](installation/from-binary/macos)


## Hummingbot for Developers

For developers looking to contribute to Hummingbot and extend its capabilities, it is recommended to install Hummingbot from source.

- [Linux Source Installation](/installation/from-source.linux)
- [macOS Source Installation](installation/from-source/macOS)
- [Windows Source Installation](installation/from-source/windows)