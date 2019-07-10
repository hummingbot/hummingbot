# Overview of Hummingbot Installation

## Recommended Setup

We recommend the following platform/setup for running Hummingbot:

| | |
|---|---|
| **Cloud server** | Install on the cloud for ease of 24/7 operation and network stability. |
| **Linux (Ubuntu)** | Hummingbot was designed and optimized for UNIX-based systems such as Linux and MacOS. |
| **Docker** | Run Hummingbot through Docker for easier setup, operation, operation of multiple bots, and updating. |
| **tmux** | Use `tmux` for persistent operation to prevent the cloud server from going to sleep. |


#### Installation Guides

Installing via the Cloud:

* [Setting up a Virtual Machine](/installation/cloud)

Installing with Docker:

* [For Linux Systems](/installation/linux) *(Recommended)*
* [For macOS Systems](/installation/macOS)
* [For Windows Systems](/installation/windows)

## Installation from Source (for Developers)

For Users who want to access to and intend to edit the code base, you can install from source:

* [For Linux Systems](/installation/from-source/linux)
* [For macOS Systems](/installation/from-source/macOS)
* [For Windows Systems](/installation/from-source/windows)

## Windows Users

Native Windows installation and operation is not supported.  We recommend Windows users to either:

1. deploy Hummingbot on the cloud, or
2. install locally using Windows Subsystems for Linux.