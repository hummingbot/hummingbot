# Installing Hummingbot

## System requirements

Hummingbot is tested and supported on the following 64-bit systems:

* Windows 10 or later
* macOS 10.12.6 (Sierra) or later
* Ubuntu 16.04 or later, Debian GNU/Linux 9, CentOS 7

## Installation options

Hummingbot can be installed locally in two ways: via Docker or from source.

| | Source | Docker |
|----|----|----|
| **Windows** | ❌ Not currently supported | <font color="green">✓</font> |
| **Installation** | Requires installation of dependencies and then downloading, installing, and compiling code | <font color="green">✓</font> Simple installation: hummingbot docker image is pre-installed, pre-compiled, and includes all dependendencies |
| **Updating versions** | Download latest code using `git`, uninstall, reinstall, recompile | <font color="green">✓</font> Remove and recreate container (can be single command) |
| **Code accessibility** | <font color="green">✓</font> Easy access for editing | Less accessible |
| **Running multiple instances** | Requires multiple installations | <font color="green">✓</font> Easy to deploy multiple instances |



### Windows

For Windows users, we strongly recommend using Docker as Hummingbot does not currently have native Windows support.

* [Install using Docker](/installation/docker_windows)
* [Install from source](/installation/windows)

*Estimated installation time: 10 minutes*

### MacOS

On MacOS, it's quicker and easier to install Hummingbot using Docker. If you are looking to make your own modifications, however, installing from source might be a better fit.

* [Install using Docker](/installation/docker_macOS)
* [Install from source](/installation/macOS)

### Linux

On Linux systems, it's quicker and easier to install Hummingbot using Docker. If you are looking to make your own modifications, however, installing from source might be a better fit.

* [Install using Docker](/installation/docker_linux)
* [Install from source](/installation/linux)

*Estimated installation time: 10 minutes*

### Using Cloud Servers

Utilizing cloud virtual machines makes it easier to run Hummingbot continuously for longer periods of time and can be configured to any OS.

* [Install in the cloud](/installation/cloud)

*Estimated installation time: 15 minutes*
