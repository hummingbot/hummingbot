# Windows Source Installation

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

* Install the [Docker version](/installation/docker_windows). Note that it is recommended to use the Docker Toolbox over native Docker in most cases.
* Install in [the cloud](/installation/cloud) by using a native Linux virtual machine.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

## Installing Hummingbot on Windows Subsystems for Linux

Below, we summarize instructions for installing Hummingbot from source on Windows 10, using Windows Subsystem for Linux (WSL). Users may use <a href="ttps://www.virtualbox.org/" target="_blank">VirtualBox</a> rather than WSL.

### 1. Install Ubuntu in Windows Subsystem for Linux

Follow these <a href="https://docs.microsoft.com/en-us/windows/wsl/install-win10" target="_blank">instructions</a> for installing Windows Subsystem for Linux, and then Ubuntu.

### 2. Install Hummingbot on Linux Subsystem

![Bash for Windows](/assets/img/bash-for-windows.png)

Once you can run Linux on your computer, you can proceed to either of the following guides to setup and run Hummingbot:

- [Install on Linux from source](/installation/linux/)
- [Install on Linux from Docker](/installation/docker_linux/)
