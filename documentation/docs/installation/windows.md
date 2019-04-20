# Installing Hummingbot on Windows

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

* Install the [Docker version](/installation/docker): note that this uses Docker Toolbox which may require Windows Pro
* Install from source using VirtualBox or Windows Subsystem for Linux

## Installation walkthough

Below, we summarize instructions for installing Hummingbot from source on Windows 10, using Windows Subsystem for Linux. Users may also want to refer to the full instructions for [installing from source](installation/source).

### 1. Install Ubuntu in Windows Subsystem for Linux

Follow these <a href="https://docs.microsoft.com/en-us/windows/wsl/install-win10" target="_blank">instructions</a> for installing Windows Subsystem for Linux. Then, install your favorite Linux distribution; Hummingbot has been tested on Ubuntu so we recommend that if possible.

### 2. Get the `build-essential` package

![Bash for Windows](/assets/img/bash-for-windows.png)

Start the Bash app and install the `build-essential` package which contains `gcc` and `make`, utility libraries used by Hummingbot's installation script:
```
sudo apt-get update
sudo apt-get build-essential
```

### 2. Download and run the Anaconda for Linux installer

To manage Python and Python library dependencies, Hummingbot uses Anaconda, an open source environment and package manager that is the current industry standard for data scientists and data engineers.

From Bash, download the Anaconda for Linux installer:
```
wget -o https://repo.anaconda.com/archive/Anaconda3-2019.03-Linux-x86_64.sh
```

Run the installer:
```
./Anaconda3-2019.03-Linux-x86_64.sh
```

### 3. Install and compile Hummingbot

Afterwards, installation should be identical to installing from source on macOS or Linux. 

Follow the [Install from source](/installation/source) guide starting on step 2.




