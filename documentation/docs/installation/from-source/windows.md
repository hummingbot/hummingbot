# Windows Source Installation

!!! info "Recommended for Developers Only"
    [Installation using Docker](/installation/windows) is more efficient for running Hummingbot.  Installing from source is only recommended for developers who want to access and modify the software code.

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

* Install the [Docker version](/installation/windows). Note that it is recommended to use the Docker Toolbox over native Docker in most cases.
* Install in [the cloud](/installation/cloud) by using a native Linux virtual machine.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

## Installing Hummingbot on Windows Subsystems for Linux

Below, we summarize instructions for installing Hummingbot from source on Windows 10, using Windows Subsystem for Linux (WSL).

#### Step 1. Install Ubuntu in Windows Subsystem for Linux

Follow these [instructions](https://docs.microsoft.com/en-us/windows/wsl/install-win10) for installing Windows Subsystem for Linux, and then Ubuntu.

#### Step 2. Install Hummingbot on Linux Subsystem

![Bash for Windows](/assets/img/bash-for-windows.png)

You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 3) Run installation
./install-source-ubuntu.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Log out and log back into shell to register "conda" command
exit

# 4) Log back into or open a new Linux terminal

# 5) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 6) Install Hummingbot
cd hummingbot && ./install

# 7) Activate environment and compile code
conda activate hummingbot && ./compile

# 8) Start Hummingbot
bin/hummingbot.py
```