# Windows Source Installation

Installing from source is only recommended for developers who want to access and modify the software code. We recommend that Windows users either:

- Follow the guide on [Hummingbot Windows Binary version](/installation/download/windows/) using `setup.exe` installer binary.

- Follow the guide on [Hummingbot Windows Docker version](/installation/docker/windows). Note that it is recommended to use the Docker Toolbox over native Docker in most cases.

Setting up Hummingbot locally on Windows can be done in two ways:

- [Installing Hummingbot on Windows System](/installation/source/windows/#installing-hummingbot-on-windows-system)
- [Installing Hummingbot on Windows Subsystems for Linux](/installation/source/windows/#installing-hummingbot-on-windows-subsystems-for-linux)

## Installing Hummingbot on Windows System

#### Step 1. Install required Applications
1. Install [Git for Windows](https://git-scm.com/download/win).
2. Install [Python for Windows](https://www.python.org/downloads/windows/).
3. Install [Anaconda or miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html).
4. Install [Visual Studio Code](https://code.visualstudio.com/download), [Visual Studio BuildTools 2019, Core Features, C++](https://visualstudio.microsoft.com/thank-you-downloading-visual-studio/?sku=BuildTools&rel=16) and [C++ redistributable 2019](https://aka.ms/vs/16/release/VC_redist.x64.exe).

!!! warning
    Some prerequisites are large applications and may need to restart your computer.

#### Step 2. Install Hummingbot on Windows System

Launch Git Bash App<br />
![git-bash](/assets/img/git-bash.png)

```
# initialized conda
conda init bash
# exit git-bash to take effect
exit
# launch Git Bash App again
```

You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Navigate to root folder
cd ~

# 2) Download install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-windows.sh -o install-source-windows.sh

# 3) Enable script permissions
chmod a+x install-source-windows.sh

# 4) Run installation
./install-source-windows.sh
```

```bash tab="Option 2: Manual Installation"
cd ~
export CONDAPATH="$(pwd)/miniconda3"
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3"
# Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git
# Install Hummingbot
export hummingbotPath="$(pwd)/hummingbot" && cd $hummingbotPath && ./install
# Activate environment and compile code
conda activate hummingbot && ./compile
# Start Hummingbot
winpty python bin/hummingbot.py
```


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
# 1) Navigate to root folder
cd ~

# 2) Download install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh -o install-source-ubuntu.sh

# 3) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 4) Run installation
./install-source-ubuntu.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Navigate to root folder
cd ~

# 2) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 3) Install Miniconda3
curl https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -o Miniconda3-latest-Linux-x86_64.sh
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


