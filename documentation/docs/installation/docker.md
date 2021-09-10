# Install Hummingbot with Docker

CoinAlpha publishes [Docker images](https://hub.docker.com/r/coinalpha/hummingbot) for the `latest` and `development` builds of Hummingbot, as well as every version. 

You can install Docker and Hummingbot by selecting the following options below:

- **Scripts**: download and use automated install scripts
- **Manual**: run install commands manually

## Linux/Ubuntu

_Supported versions: 16.04 LTS, 18.04 LTS, 19.04_

### Install Docker

=== "Scripts"

    ```bash
    # 1) Download Docker install script
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/install-docker/install-docker-ubuntu.sh

    # 2) Enable script permissions
    chmod a+x install-docker-ubuntu.sh

    # 3) Run installation
    ./install-docker-ubuntu.sh
    ```

=== "Manual"

    ```bash
    # 1) Update Ubuntu's database of software
    sudo apt-get update

    # 2) Install tmux
    sudo apt-get install -y tmux

    # 3) Install Docker
    sudo apt install -y docker.io

    # 4) Start and Automate Docker
    sudo systemctl start docker && sudo systemctl enable docker

    # 5) Change permissions for docker (optional)
    # Allow docker commands without requiring sudo prefix
    sudo usermod -a -G docker $USER

    # 6) Close terminal
    exit
    ```

!!! warning
    Please restart terminal — close and restart your terminal window to enable the correct permissions for `docker` command before proceeding to next step.

### Install Hummingbot

=== "Scripts"

    ```bash
    # 1) Download Hummingbot install, start, and update script
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/create.sh
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/start.sh
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/update.sh

    # 2) Enable script permissions
    chmod a+x *.sh

    # 3) Create a hummingbot instance
    ./create.sh
    ```

=== "Manual"

    ```bash
    # 1) Create folder for your new instance
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

## MacOS

You can install Docker by [downloading an installer](https://docs.docker.com/docker-for-mac/install/) from the official page. After you have downloaded and installed Docker, restart your system if necessary.

=== "Scripts"

    ```bash
    # 1) Download Hummingbot install, start, and update script
    curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/create.sh -o create.sh
    curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/start.sh -o start.sh
    curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/master/installation/docker-commands/update.sh -o update.sh

    # 2) Enable script permissions
    chmod a+x *.sh

    # 3) Create a hummingbot instance
    ./create.sh
    ```

=== "Manual"

    ```bash
    # 1) Create a folder for your new instance
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

## Windows

The Hummingbot codebase is designed and optimized for UNIX-based systems such as macOS and Linux. Windows users can install using Hummingbot using [Docker Desktop](https://docs.docker.com/docker-for-windows/).

!!! note
    Docker Toolbox has been deprecated and is no longer in active development. Please see this [link](https://docs.docker.com/docker-for-windows/docker-toolbox/) for more info.

### Install Docker Desktop

![Docker Desktop](/assets/img/docker_desktop_download.gif)

**1 - Install Docker Desktop**

- [Windows Home](https://docs.docker.com/docker-for-windows/install-windows-home/)
- [Windows Pro / Enterprise](https://docs.docker.com/docker-for-windows/install/)

**2 - Enable WSL 2**

To enable WSL 2, open `Windows PowerShell` and run it as administrator. Use the command below, and this will take a while to complete:

```
wsl.exe --set-version Ubuntu-18.04 2
```

**3 - Open Docker Desktop, Go to Settings > Resources, and then enable WSL Integration**

![Docker Desktop WSL enable](/assets/img/docker_desktop_WSLenable.gif)

**4 - Open `Ubuntu 18.04 LTS` and install Hummingbot**

Follow the instructions in the Linux section above to complete installing Hummingbot.
