# Linux Installation Using Docker

You can install Docker and/or Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

## Existing Docker Installation

If you already have Docker installed, use the following commands to install and start Hummingbot:

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Ubuntu

*Supported versions: 16.04 LTS, 18.04 LTS, 19.04*

#### Part 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update Ubuntu's database of software
sudo apt-get update

# 2) Install Docker
sudo apt install -y docker.io

# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 

# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER 

# **Note**: the script will close the terminal window
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Part 2](#part-2-install-hummingbot).

#### Part 2: Install Hummingbot

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Debian

*Supported version: Debian GNU/Linux 9*

#### Part 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-docker-debian.sh

# 2) Enable script permissions
chmod a+x install-docker-debian.sh

# 3) Run installation
./install-docker-debian.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update package database
sudo apt update

# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common

# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update

# 4) Install Docker
sudo apt install -y docker-ce

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# **Note**: the script will close the terminal window
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Part 2](#part-2-install-hummingbot_1).

#### Part 2: Install Hummingbot

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## CentOS

*Supported version: 7*

#### Part 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-docker-centos.sh

# 2) Enable script permissions
chmod a+x install-docker-centos.sh

# 3) Run installation
./install-docker-centos.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update package database
sudo yum check-update

# 2) Install Docker
curl -fsSL https://get.docker.com/ | sh 

# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# **Note**: the script will close the terminal window
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Part 2](#part-2-install-hummingbot_2).

#### Part 2: Install Hummingbot

```bash tab="Option 1: Easy Install"
# 1) Download Docker and Hummingbot install scripts
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Developer Notes

- Additional details of the scripts can be found on [Github: Hummingbot Install with Docker](https://github.com/CoinAlpha/hummingbot/tree/development/installation/install-docker).