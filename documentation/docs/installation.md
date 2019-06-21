# Installing Hummingbot

## System requirements

Hummingbot is tested and supported on the following 64-bit systems:

* Windows 10 or later
* macOS 10.12.6 (Sierra) or later
* Linux: Ubuntu 16.04 or later, Debian GNU/Linux 9, CentOS 7

## Installation options

Hummingbot can be installed locally in two ways: via Docker or from source.  Choosing how to install depends on your preferences for intended use.

| | Source | Docker |
|----|----|----|
| **Windows** | ❌ No native support; available only by installing Linux subsystem | <font color="green">✓</font> |
| **Installation** | Requires installation of dependencies and then downloading, installing, and compiling code | <font color="green">✓</font> Simple installation: hummingbot docker image is pre-installed, pre-compiled, and includes all dependendencies |
| **Updating versions** | Download latest code using `git`, uninstall, reinstall, recompile | <font color="green">✓</font> Remove and recreate container (can be single command) |
| **Code accessibility** | <font color="green">✓</font> Easy access for editing | Less accessible |
| **Running multiple instances** | Requires multiple installations | <font color="green">✓</font> Easy to deploy multiple instances |


## Installation Guides

| | | |  |
|---|---|---|---|
| **Install from source** | [Windows](/installation/windows) | [MacOS](/installation/macos) | [Linux](/installation/linux) |
| **Install with Docker** | [Windows](/installation/docker_windows) | [MacOS](/installation/docker_macos) | [Linux](/installation/docker_linux) |
| [**Install in the cloud**](/installation/cloud/) |