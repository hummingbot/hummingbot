# Developer Quickstart – Windows | Installing

This section walks you through how to prepare your development environment and install Hummingbot from source manually.

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users:

* Install in [the cloud](/installation/cloud) by using a native Linux virtual machine.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

## Installing Hummingbot on Windows Subsystems for Linux

Below, we summarize instructions for installing Hummingbot from source on Windows 10, using Windows Subsystem for Linux (WSL).

#### Step 1. Install Ubuntu in Windows Subsystem for Linux

Follow these [instructions](https://docs.microsoft.com/en-us/windows/wsl/install-win10) for installing Windows Subsystem for Linux, and then Ubuntu.

#### Step 2. Install Hummingbot on Linux Subsystem

![Bash for Windows](/assets/img/bash-for-windows.png)

You can install Hummingbot as shown below:

```bash tab="Manual Installation"
# 1) Navigate to root folder
cd ~

# 2) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 3) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 4) Log out and log back into shell to register "conda" command
exit

# 5) Log back into or open a new Linux terminal

# 6) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 7) Install Hummingbot
cd hummingbot && ./install

# 8) Activate environment and compile code
conda activate hummingbot && ./compile

# 9) Start Hummingbot
bin/hummingbot.py
```


---
# Next: [Using Hummingbot](/developers/gettingstarted/windows/2-using)
