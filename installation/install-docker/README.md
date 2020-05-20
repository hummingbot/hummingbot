# Installing with Docker

## Existing Docker Installation

If you already have Docker installed, use the following commands to install and start Hummingbot:

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
chmod a+x create.sh
./create.sh
```

## Linux Installation: Docker + Hummingbot

The following instructions install both Docker and Hummingbot.

### Ubuntu (Recommended)

*Supported versions: 16.04 LTS, 18.04 LTS, 19.04*

##### 1. Download Install Scripts and Install Docker
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
chmod a+x *.sh
./install-docker-ubuntu.sh
```

##### 2. Install Hummingbot

```
./create.sh
```


### Debian

*Supported version: Debian GNU/Linux 9*

##### 1. Download Install Scripts and Install Docker
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-debian.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
chmod a+x *.sh
./install-docker-debian.sh
```

> Note: the above script will close the terminal window to enable `docker` permissions.  Open a new terminal window to proceed with Part 2.

##### 2. Install Hummingbot

```
./create.sh
```


### CentOS

*Supported version: 7*

##### 1. Download Install Scripts and Install Docker
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-centos.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
chmod a+x *.sh
./install-docker-centos.sh
```

> Note: the above script will close the terminal window to enable `docker` permissions.  Open a new terminal window to proceed with Part 2.

##### 2. Install Hummingbot

```
./create.sh
```


---

## Docker Operation

Once you have have installed Docker and Hummingbot, proceed to [Docker commands](../docker-commands/README.md) for additional instructions, such as updating Hummingbot.