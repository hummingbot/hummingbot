# Mac

## Install via binary

<iframe width="616" height="347" src="https://www.youtube.com/embed/klN-ToclwW4" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

The macOS install package allows very easy installation and running Hummingbot on Mac computers. macOS install packages are released with every Hummingbot release starting from v0.18.

To install Hummingbot with macOS install package:

1. Download Hummingbot .dmg file from our [download page](https://hummingbot.io/download).
2. Open the downloaded .dmg file, drag and drop the application bundle into the `/Application` folder.

![Drag and Drop Application Bundle](/assets/img/macos-dmg-1.png)

3. Launch Hummingbot just like any other installed application on your Mac. You can also add it to your Dock for easy access.

![Added Hummingbot to Dock"](/assets/img/macos-dmg-2.png)

When you start Hummingbot for the first time, it will ask for permission to launch Terminal since it is a Terminal application. Press "OK" to allow it to open.

![Granting Terminal access to Hummingbot"](/assets/img/macos-dmg-3.png)

#### Application data files

The application data files (e.g., logs and config files) are located differently for binary package installed Hummingbot vs. source compiled Hummingbot.

For the macOS .dmg distribution, the application data files are located in `~/Library/Application\ Support/Hummingbot`

!!! tip
    For error **'Cannot be opened because the developer cannot be verified'**, you can `click then open` to run the installer.

## Install via Docker

1. Install Docker

Skip this step if you already have Docker installed. You can install Docker by [downloading an installer](https://docs.docker.com/docker-for-mac/install/) from the official page. After you have downloaded and installed Docker, restart your system if necessary.

2. Install Hummingbot

You can install Hummingbot by selecting **_either_** of the following options from the tabs below:

- **Scripts**: download and use automated install scripts.
- **Manual**: run install commands manually.

Scripts

```Scripts
# 1) Download Hummingbot install, start, and update script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh -o start.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh -o update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

Manual

```Manual
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

## Install from source

**Install dependencies**

This section walks you through how to prepare your development environment.

1. Install Xcode command line tools

Running Hummingbot on **macOS** requires [Xcode](https://developer.apple.com/xcode/) and Xcode command line tools.

```
xcode-select --install
```

2. Install Anaconda3

Hummingbot requires Python 3 and other Python libraries. To manage these dependencies, Hummingbot uses Anaconda, an open-source environment, and package manager for Python that is the current industry standard for data scientists and data engineers.

To install Anaconda, go to [the Anaconda site](https://www.anaconda.com/distribution/) and download the **Python 3.7 installer** for your operating system. Both the graphical installer and the command line installer will work. Run the installer, and it will guide you through the installation process.

Afterward, open a Terminal window and try the `conda` command. If the command is valid, then Anaconda has been successfully installed, even if the graphical installer says that it failed.

!!! warning
    If you use ZSH or another Unix shell, copy the code snippet below to your `.zshrc` or similar file. By default, Anaconda only adds it to your `.bash_profile` file. This makes the `conda` command available in your root path.

```
__conda_setup="$(CONDA_REPORT_ERRORS=false '/anaconda3/bin/conda' shell.bash hook 2> /dev/null)"
if [ $? -eq 0 ]; then
    \eval "$__conda_setup"
else
    if [ -f "/anaconda3/etc/profile.d/conda.sh" ]; then
        . "/anaconda3/etc/profile.d/conda.sh"
        CONDA_CHANGEPS1=false conda activate base
    else
        \export PATH="/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
```

3. Install Hummingbot

```
# 1) Clone Hummingbot repo
git clone https://github.com/CoinAlpha/hummingbot.git

# 2) Navigate into the hummingbot folder
cd hummingbot

# 3) Run install script
./install

# 4) Activate the environment
conda activate hummingbot

# 5) Compile
./compile

# 6) Run Hummingbot
bin/hummingbot.py
```

After installing Hummingbot from source, see [Launch Hummingbot from source](/operation/launch-exit/) for instructions on starting and running Hummingbot from source.
