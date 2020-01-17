# [Quickstart] Install Hummingbot

Below, we show you how to easily install Hummingbot using our installation scripts for each supported platform. For more detailed instructions, refer to our [User Manual](https://docs.hummingbot.io/installation/).

## Linux

For Linux we highlight the Docker image method for new users since it contains all necessary dependencies.

### Step 1: Download helper scripts

We have created automated scripts that simplify the process of installing and running Hummingbot with Docker.

* `create.sh`: Creates a new instance of Hummingbot
* `start.sh`: Starts a stopped Hummingbot instance
* `update.sh`: Updates Hummingbot


Copy the commands below and paste into your Linux terminal to download the scripts and enable permissions.

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
chmod a+x *.sh
```

![helper_scripts](/assets/img/helper_scripts.gif)

Ensure the scripts have been downloaded by running `ls -l` command.

![list_scripts](/assets/img/list_scripts.png)


### Step 2: Install Docker

Docker is an open source containerization product that pre-packages all dependencies into a single container, greatly simplifying the installation process. Execute the command below to install Docker using the script we downloaded in the previous step.

```bash
./install-docker-ubuntu.sh
```

Close and restart your bash/terminal window to enable the correct permissions for the `docker` command. Otherwise, you may encounter an error in the next steps.

We also have instructions for installing Docker on [Debian](/installation/via-docker/linux/#debian) and [CentOS](/installation/via-docker/linux/#centos).


### Step 3: Install Hummingbot

Execute `create.sh` script which will help you install an instance of Hummingbot and set up folders to house your logs, configuration files and trades/orders database file.

```
hummingbot_files       # Default name of top level folder for hummingbot-related files
├── hummingbot_conf    # Maps to hummingbot's conf/ folder, which stores configuration files
├── hummingbot_logs    # Maps to hummingbot's logs/ folder, which stores log files
└── hummingbot_data    # Maps to hummingbot's data/ folder, which stores the SQLite database file
```

Run command to execute the script.

```
./create.sh
```

Follow the prompts to choose a version, give your Hummingbot instance a name, and enter the name of the folder where its files will be saved.

![script_create](/assets/img/script_create1.gif)

Afterwards, you should see the Hummingbot client interface. Proceed to [Configure a Bot](/quickstart/3-configure-bot).


## Windows and macOS

Setup and install package to install on local computer can be downloaded from our official website:

- [Download the Hummingbot client](https://hummingbot.io/download/)

You may also refer to our User Manual for more information.

- [Windows Binary Installation](/installation/from-binary/windows)
- [macOS Binary Installation](/installation/from-binary/macos)


## Hummingbot for Developers

For developers looking to contribute to Hummingbot and extend its capabilities, it is recommended to install Hummingbot from source.

- [Linux Source Installation](/installation/from-source/linux)
- [macOS Source Installation](/installation/from-source/macOS)
- [Windows Source Installation](/installation/from-source/windows)