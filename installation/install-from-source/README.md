# Installing from Source

The following commands download and run scripts that (1) install local dependencies and (2) install Hummingbot.

Copy and paste the commands for your operating system into terminal.

## Linux Installation

### Ubuntu (Recommended)

- Supported versions: 16.04 LTS, 18.04 LTS, 19.04

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh
chmod a+x install-source-ubuntu.sh
./install-source-ubuntu.sh
```

### Debian

- Supported version: Debian GNU/Linux 9

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-debian.sh
chmod a+x install-source-debian.sh
./install-source-debian.sh
```

### CentOS

- Supported version: 7

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-centos.sh
chmod a+x install-source-centos.sh
./install-source-centos.sh
```

## MacOS Installation

```
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-macOS.sh -o install-source-macOS.sh
chmod a+x install-source-macOS.sh
./install-source-macOS.sh
```

## Windows Installation

Install [required applications](https://github.com/CoinAlpha/hummingbot/blob/development/documentation/docs/installation/source/windows.md) before using the script the first time.

```
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-windows.sh -o install-source-windows.sh
chmod a+x install-source-windows.sh
./install-source-windows.sh
```

## Windows Installation using WSL

```
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh -o install-source-ubuntu.sh
chmod a+x install-source-ubuntu.sh
./install-source-ubuntu.sh
```

---

## Updating Hummingbot

The `update.sh` script updates Hummingbot to the latest version. Run the following commands from the root folder:

```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/update.sh
chmod a+x update.sh
./update.sh
```
