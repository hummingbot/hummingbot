# Raspberry Pi Source Installation

Running Hummingbot on a Raspberry Pi has the same main benefit of running it on a cloud server: having a dedicated machine for Hummingbot.  Raspberry Pi’s are relatively low cost, easy to set up, and, of course, don’t have the monthly charges associated with a cloud provider.

Read through our full blog post about [Deploying Hummingbot on a Raspberrry Pi](https://hummingbot.io/blog/2020-07-deploying-hummingbot-on-a-raspberry-pi/).

The only way to currently install Hummingbot on a Raspberry Pi is by downloading the source files from GitHub and compiling and running from source. This adds a few more steps than downloading binaries or running from Docker, but below we have provided a step-by-step guide to walk you through the process.


## Preparing the Raspberry Pi for installation

**Step 1. Install 64-bit Raspberry Pi OS**

To run Hummingbot on a Raspberry Pi, a 64-bit OS is required. Raspberry Pi has a beta 64-bit version of the Raspberry Pi OS. You can download the OS from the [Raspberry Pi website](https://www.raspberrypi.org/forums/viewtopic.php?f=117&t=275370).

**Step 2. Load the image file to your Raspberry Pi’s SD card**

Raspberry Pi has an easy to follow [guide](https://www.raspberrypi.org/documentation/installation/installing-images/) with alternatives on how to load the SD card with a Raspberry Pi OS from different operating systems.

**Step 3. Boot your Raspberry Pi**

Insert your SD card into the Raspberry Pi and plug in the power source. From there, the first launch options will be prompted.


## Install Hummingbot Dependencies

**Step 1. Open the Raspberry Pi terminal**

In the top left corner of the desktop, there is a shortcut that opens the terminal.
 
**Step 2.  Install Miniforge, Python and update alternatives**

```
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
sh Miniforge3-Linux-aarch64.sh
sudo apt-get install python3.7
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
```

**Step 3. Log out and Log back in to enable `conda`**

This will make the `conda` command available in shell / terminal.


## Install pip dependencies

**Step 1. Create a conda environment for Hummingbot**

```
conda create --name hummingbot
```

**Step 2. Activate your conda environment**

```
conda activate hummingbot
```

**Step 3. Install the pip dependencies**

```
pip install pandas cython cachetools aiohttp ruamel.yaml eth_account aiokafka sqlalchemy binance python-binance ujson websockets signalr-client-aio web3 prompt_toolkit 0x-order-utils 0x-contract-wrappers eth_bloom pyperclip telegram python-telegram-bot jwt numpy mypy_extensions
```

## Install, compile, and run Hummingbot

**Step 1. Clone the Hummingbot repo from Github**

```
git clone https://github.com/CoinAlpha/hummingbot.git
```
 
**Step 2. Clean your Hummingbot directory and compile**

```
cd hummingbot && ./clean && ./compile
```

**Step 3. Run Hummingbot**

```
bin/hummingbot.py
```