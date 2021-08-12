# Windows

## Install via binary

<iframe width="616" height="347" src="https://www.youtube.com/embed/9TsZ_xjExXs" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

The Windows setup package is the easiest way for Windows users to set up and run Hummingbot. Windows setup packages are released with every Hummingbot release starting from v0.18.

To install Hummingbot with Windows setup package:

1. Download Setup.exe from our [download page](https://hummingbot.io/download).
2. Double-click the `Setup.exe` hummingbot binary package to launch the installer.

![Hummingbot installed](/assets/img/windows-setup-1.png)

3. Start Hummingbot in your Windows start menu.

![Hummingbot installed](/assets/img/windows-setup-2.png)

#### Application data files

The application data files (e.g., logs and config files) are located differently for binary package installed Hummingbot vs. source compiled Hummingbot.

For the Windows binary distribution, the application data files are located in `%localappdata%\hummingbot.io\Hummingbot`.

## Install via Docker

The Hummingbot codebase is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

- Install in the cloud and use a native Linux virtual machine.
- Install using Docker version: [Docker Desktop](https://docs.docker.com/docker-for-windows/) recommended.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

!!! note
    Docker Toolbox has been deprecated and is no longer in active development. Please see this [link](https://docs.docker.com/docker-for-windows/docker-toolbox/) for more info.

**Docker Desktop**

Supports Windows Home, Pro, and Enterprise edition. Download the latest version of Docker Desktop .exe file via [Docker Hub](https://hub.docker.com/editions/community/docker-ce-desktop-windows/)

![Docker Desktop](/assets/img/docker_desktop_download.gif)

!!! note
    Docker Desktop requires WSL 2 feature enabled. For detailed instructions, refer to the [Microsoft documentation](https://docs.microsoft.com/en-us/windows/wsl/install-win10).

1. For installation procedures, you check the link below depending on the version of your Windows operating system.

   - [Windows Home](https://docs.docker.com/docker-for-windows/install-windows-home/)
   - [Windows Pro / Enterprise](https://docs.docker.com/docker-for-windows/install/)

2. To enable WSL 2, open `Windows PowerShell` and run it as administrator. Use the command below, and this will take a while to complete:

```Windows PowerShell
wsl.exe --set-version Ubuntu-18.04 2
```

3. Open Docker Desktop, Go to Settings > Resources, and then enable WSL Integration

![Docker Desktop WSL enable](/assets/img/docker_desktop_WSLenable.gif)

4. Open `Ubuntu 18.04 LTS` and move to the next step to install HummingBot.

Enter the following commands into the command line. You can install Hummingbot by selecting **_either_** of the following options from the tabs below:

- **Scripts**: download and use automated install scripts.
- **Manual**: run install commands manually.

Scripts

```Scripts
# 1) Navigate to the root folder
cd ~

# 2) Download Hummingbot install, start, and update script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh

# 3) Enable script permissions
chmod a+x *.sh

# 4) Create a hummingbot instance
./create.sh
```

Manual

```Manual
# 1) Navigate to the root folder
cd ~

# 2) Create a folder for your new instance
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

## Install from source

This section walks you through how to prepare your development environment and install Hummingbot from source manually.

Installing from source is only recommended for developers who want to access and modify the software code.

Step 1. Install required Applications

1. Install [Git for Windows](https://git-scm.com/download/win).

- During the installation of Git Bash, make sure to tick the Enable experimental support for pseudo consoles.
  ![anaconda-path](/assets/img/git-installation.png)

2. Install [Python for Windows](https://www.python.org/downloads/windows/).
3. Install [Anaconda or miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html).
4. Install [Visual Studio Code](https://code.visualstudio.com/download), [Visual Studio BuildTools 2019, Core Features, C++](https://visualstudio.microsoft.com/thank-you-downloading-visual-studio/?sku=BuildTools&rel=16) and [C++ redistributable 2019](https://aka.ms/vs/16/release/VC_redist.x64.exe).

- During installation, make sure to add Anaconda or Miniconda to your PATH environmental variable by clicking the tick box as shown below, or you can add them [manually](https://www.geeksforgeeks.org/how-to-setup-anaconda-path-to-environment-variable/).
  ![anaconda-path](/assets/img/anaconda-path.png)

!!! note
    Some prerequisites are large applications and may need to restart your computer.

Step 2. Install Hummingbot on Windows System

1. Launch Git Bash App.
2. Run the following commands:

```
# initialized conda
conda init bash
# exit git-bash to take effect
exit
# launch Git Bash App again
```

3. You can install Hummingbot by selecting **_either_** of the following options from the tabs below:

- **Scripts**: download and use automated install scripts.
- **Manual**: run install commands manually.

Scripts

```scripts
# 1) Navigate to the root folder
cd ~

# 2) Download install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-windows.sh -o install-source-windows.sh

# 3) Enable script permissions
chmod a+x install-source-windows.sh

# 4) Run installation
./install-source-windows.sh
```

Manual

```Manual
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

After installing Hummingbot from source, see [Launch Hummingbot from source](/operation/launch-exit/) for instructions on starting and running Hummingbot from source.
