# Raspberry Pi

## Install via Docker (BETA)

### Prerequisite

!!! note
    This installation method is currently under testing and awaiting feedback from users. Should you run into problems or have found a fix to solve errors along the way, feel free to reach out through our [Discord](https://discord.com/invite/2MN3UWg) support channel.

1. Install Docker and change permissions.

```
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -a -G docker $USER
```

2. Start and automate docker.

```
sudo systemctl start docker && sudo systemctl enable docker
```

3. Exit terminal/shell to refresh shell.

```
Exit
```

!!! warning
    Restart terminal — close and restart your terminal window to enable the correct permissions for `docker` command before proceeding.

4. Install Hummingbot:

You can install Hummingbot with **_either_** of the following options:

- **Scripts**: download and use automated install scripts.
- **Manual**: run install commands manually.

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

# 4) Pull Hummingbot ARM image when asked what version to use
Enter Hummingbot version: [ latest/development ] ( default = 'latest' )
>> version-0.38.1-arm_beta

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
coinalpha/hummingbot:version-0.38.1-arm_beta
```

## Install from source

This guide walks you through how to prepare your development environment and get started developing for Hummingbot.

Running Hummingbot on a Raspberry Pi has the same main benefit of running it on a cloud server: having a dedicated machine for Hummingbot. Raspberry Pi’s are relatively low cost, easy to set up, and, of course, don’t have the monthly charges associated with a cloud provider.

![rpi](/assets/img/rpi-hummingbot.jpg)

Read through our full blog post about [Deploying Hummingbot on a Raspberry Pi](https://hummingbot.io/blog/2020-07-deploying-hummingbot-on-a-raspberry-pi/).

The only way to currently install Hummingbot on a Raspberry Pi is by downloading the source files from GitHub and compiling and running from source. This adds a few more steps than downloading binaries or running from Docker, but below we have provided a step-by-step guide to walk you through the process.

### Prerequisites

**Install 64-bit Raspberry Pi OS**

To run Hummingbot on a Raspberry Pi, a 64-bit OS is required. Raspberry Pi has a beta 64-bit version of the Raspberry Pi OS. You can download the OS from the [Raspberry Pi website](https://www.raspberrypi.org/forums/viewtopic.php?f=117&t=275370).

**Load the image file to your Raspberry Pi’s SD card**

Raspberry Pi has an easy to follow [guide](https://www.raspberrypi.org/documentation/installation/installing-images/) with alternatives on how to load the SD card with a Raspberry Pi OS from different operating systems.

**Boot your Raspberry Pi**

Insert your SD card into the Raspberry Pi and plug in the power source.
From there, the first launch options will be prompted.

** Install Hummingbot dependencies **

Open the Raspberry Pi terminal. In the top left corner of the desktop, there is a shortcut that opens the terminal.

```
# Install Miniforge, Python and update alternatives
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
sh Miniforge3-Linux-aarch64.sh
sudo apt-get install python3.7
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1

```

Logout and login again to enable `conda`, this will make the `conda` command available in shell / terminal.

**Install pip dependencies**

```
# Create a conda environment for Hummingbot
conda create --name hummingbot

# Activate your conda environment
conda activate hummingbot

# Clone the Hummingbot repo from Github
git clone https://github.com/CoinAlpha/hummingbot.git

# Install the pip dependencies
cd hummingbot
pip install -r setup/requirements-arm.txt
```

**Compile and run Hummingbot**

```
# Clean your Hummingbot directory and compile
./clean && ./compile

# Run Hummingbot
bin/hummingbot.py
```

!!! warning
    Compiling the bot from source would normally take 45 minutes or more

## Create Hummingbot ARM image for Docker

This guide would help you build your own Hummingbot ARM image when there is a new release. Please be advised that for every new release, you would need to [install from source](#install-from-source) first and follow the steps provided in order to create an image that you can use for your RaspberryPi docker.

1. Go to your source directory and run the command below

```
# Set a name of your image on insert_name
docker build -t coinalpha/hummingbot:insert_name -f Dockerfile.arm .
```

On this sample, we set `v036` for the name of the image. This is needed when you run `./create.sh` command
![](/assets/img/rpi-docker-img.png)

!!! warning
    Building the Hummingbot ARM image from source would normally take 45 minutes or more

## Controlling remotely using VNC Viewer

SSH and VNC features are natively built into the Raspberry Pi and can easily be turned on in the Raspberry Pi configurations settings. By turning these on, you can access the Raspberry Pi from another computer by:

1. Using terminal to SSH, similar to how you would access a cloud server
2. Using VNC to enable remote desktop access to the Raspberry Pi GUI.

This is very convenient; after initial setup of the Raspberry Pi, you can simply unplug the monitor, keyboard and mouse, and just set the Raspberry Pi itself aside and just access it remotely going forward.

![rpi](/assets/img/rpi-ssh.jpg)

**Step 1. Enable SSH and VNC on your Raspberry Pi**

- Option 1: Terminal using raspi-config

```
sudo raspi-config
```

Under Interfacing Options, enable SSH and VNC.

- Option 2: Access in Raspberry Pi Configuration

Select the menu in the top left corner of the screen then go to **Preferences > Raspberry Pi configuration > Interfaces** from there you will see options to enable SSH and VNC.

![rpi](/assets/img/rpi-config.jpg)

!!! tip
    Set a default screen resolution in `raspi-config` select: `7 Advanced Options` > `A5 Resolution` to enable VNC access to the GUI whenever you boot the Raspberry Pi without a connected monitor. For troubleshooting please visit this [link](https://www.raspberrypi.org/forums/viewtopic.php?t=216737).

Setting a default resolution will avoid the following error:

![rasp](/assets/img/rasp-no-monitor.png)

**Step 2. Get your Raspberry Pi’s IP address**

Type `ifconfig` to get the IP address of your Raspberry Pi to enter into your VNC Viewer. For SSH, you can run `ssh pi@[ipaddress]`. The IP address is the `inet` address which is not the localhost IP address 127.0.0.1:

![rpi](/assets/img/rpi-private-address.jpg)
