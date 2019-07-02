# Overview of Installing Hummingbot

## System Requirements

Hummingbot is tested and supported on the following 64-bit systems:

* Windows 10 or later
* macOS 10.12.6 (Sierra) or later
* Linux: Ubuntu 16.04 or later, Debian GNU/Linux 9, CentOS 7

## Installation Options

Hummingbot can be installed locally in two ways: via Docker or from source.  The table below contains key differences between the two methods for you to choose your preferred option.

!!! note "A Third Option: Using the Cloud"
    It is also possible to run instances of Hummingbot on a virtual machine by using cloud providers. In fact, **we recommend setting up bots on cloud servers** as they will likely have more stable networks, and can improve performance if you select servers close to exchanges you are trading on.

| | Source | Docker |
|----|----|----|
| **Windows compatibility** | ❌ No native support; available only by installing Linux subsystem | <font color="green">✓</font> Available with both native Docker application and Docker Toolbox|
| **Installation process** | Requires installation of dependencies and then downloading, installing, and compiling code | <font color="green">✓</font> Easy to use as Hummingbot docker image is pre-installed, pre-compiled, and includes all dependencies |
| **Updating versions** | Download latest code using `git`, uninstall old version, reinstall, recompile | <font color="green">✓</font> Remove and recreate container (can be done with a single command) |
| **Code accessibility** | <font color="green">✓</font> Easy access for editing and perusing files | Difficult to access and read through files |
| **Running multiple instances** | Requires multiple installations | <font color="green">✓</font> Easy to deploy multiple instances |

## Installation Guides

Installing via the Cloud:

* [Setting up a Virtual Machine](/installation/cloud)

Installing from Docker:

* [For Windows Systems](/installation/windows)
* [For macOS Systems](/installation/macOS)
* [For Linux Systems](/installation/linux)

Installing from source:

* [For Windows Systems](/installation/docker_windows)
* [For macOS Systems](/installation/docker_macOS)
* [For Linux Systems](/installation/docker_linux)
