# Linux

You can install Docker and/or Hummingbot by selecting **_either_** of the following options from the tabs below:

- **Scripts**: download and use automated install scripts.
- **Manual**: run install commands manually.

!!! info
    Recommended for Developers Only — installation using Docker is more efficient for running Hummingbot. Installing from source is only recommended for developers who want to access and modify the software code.

Or prepare your development environment and get started developing for Hummingbot.

## Ubuntu

### Install via Docker

_Supported versions: 16.04 LTS, 18.04 LTS, 19.04_

1. Install Docker

Skip this step if you already have Docker installed. Run the following commands:

Scripts

```Scripts
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh
```

Manual

```Manual
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

2. Install Hummingbot

Run the following commands:

Scripts

```Scripts
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

Manual

```Manual
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

### Install from source

_Supported versions: 16.04 LTS, 18.04 LTS, 19.04_

Scripts

```Scripts
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 3) Run installation
./install-source-ubuntu.sh
```

Manual

```Manual
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

After installing Hummingbot from source, see [Launch Hummingbot from source](/operation/launch-exit/) for instructions on how to start and run Hummingbot from source.

## Debian

### Install via Docker

_Supported version: Debian GNU/Linux 9_

1. Install Docker

Skip this step if you already have Docker installed. Run the following commands:

Scripts

```Scripts
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-debian.sh

# 2) Enable script permissions
chmod a+x install-docker-debian.sh

# 3) Run installation
./install-docker-debian.sh
```

Manual

```Manual
# 1) Update package database
sudo apt update

# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common tmux

# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update

# 4) Install Docker
sudo apt install -y docker-ce

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# 6) Close terminal
exit
```

!!! warning
    Please restart terminal — close and restart your terminal window to enable the correct permissions for `docker` command before proceeding to next step.

2. Install Hummingbot

Run the following commands:

Scripts

```Scripts
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

Manual

```Manual
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

### Install from source

_Supported version: Debian GNU/Linux 9_

Scripts

```Scripts
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-debian.sh

# 2) Enable script permissions
chmod a+x install-source-debian.sh

# 3) Run installation
./install-source-debian.sh
```

Manual

```Manual
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential git

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

After installing Hummingbot from source, see [Launch Hummingbot from source](/operation/launch-exit/) for instructions on how to start and run Hummingbot from source.

## CentOS

### Install via Docker

_Supported version: 7_

1. Install Docker

Skip this step if you already have Docker installed. Run the following commands:

Scripts

```Scripts
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-centos.sh

# 2) Enable script permissions
chmod a+x install-docker-centos.sh

# 3) Run installation
./install-docker-centos.sh
```

Manual

```Manual
# 1) Update package database
sudo yum check-update

# 2) Install tmux
sudo yum -y install tmux

# 3) Install Docker
curl -fsSL https://get.docker.com/ | sh

# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# 6) Close terminal
exit
```

!!! warning
    Please restart terminal — Close and restart your terminal window to enable the correct permissions for `docker` command before proceeding to next step.

2. Install Hummingbot

Run the following commands:

Scripts

```Scripts
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

Manual

```Manual
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

### Install from source

_Supported version: 7_

Scripts

```Scripts
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-centos.sh

# 2) Enable script permissions
chmod a+x install-source-centos.sh

# 3) Run installation
./install-source-centos.sh
```

Manual

```Manual
# 1) Install dependencies
sudo yum install -y wget bzip2 git
sudo yum groupinstall -y 'Development Tools'

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

After installing Hummingbot from source, see [Launch Hummingbot from source](/operation/launch-exit/) for instructions on how to start and run Hummingbot from source.

## Developer notes

- Additional details of the scripts can be found on [Github: Hummingbot Install with Docker](https://github.com/CoinAlpha/hummingbot/tree/development/installation/install-docker).
