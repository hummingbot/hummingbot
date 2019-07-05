# Installing with Docker

> If you already have Docker installed, do not use the commands below.  Instead, proceed to [Docker commands](../docker-commands/README.md).

The following commands download and run scripts that (1) install Docker and (2) install Hummingbot.

Copy and paste the commands for your operating system into the terminal.

## Linux Installation

### Ubuntu (Recommended)

- Supported versions: 16.04 LTS, 18.04 LTS, 19.04

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-with-docker/install-docker-ubuntu.sh
chmod a+x install-docker-ubuntu.sh
./install-docker-ubuntu.sh
```

### Debian

- Supported version: Debian GNU/Linux 9

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-with-docker/install-docker-debian.sh
chmod a+x install-docker-debian.sh
./install-docker-debian.sh
```

### CentOS

- Supported version: 7

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-with-docker/install-docker-centos.sh
chmod a+x install-docker-centos.sh
./install-docker-centos.sh
```

---

## Docker Operation

Once you have have installed Docker and Hummingbot, proceed to [Docker commands](../docker-commands/README.md) for additional instructions, such as updating Hummingbot.