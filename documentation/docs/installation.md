# Overview of Hummingbot Installation

## Recommended Setup

We recommend that users utilize the setup below for the best experience running Hummingbot:

| | |
|---|---|
| **Cloud server** | Install on AWS, Google Cloud or another cloud provider for ease of 24/7 operation and network stability. |
| **Linux (Ubuntu)** | Hummingbot was designed and optimized for UNIX-based systems such as Linux and MacOS. |
| **Docker** | Run Hummingbot through Docker for easier setup, operation, operation of multiple bots, and updating. |
| **tmux** | Use `tmux` for persistent operation to prevent the cloud server from going to sleep. |


#### Installation Guides

Recommended setup:

1. [Setting up a Cloud server](/installation/cloud)
2. [Install Docker + Hummingbot on Linux](/installation/linux)

Alternative installations with Docker:

* [For macOS Systems](/installation/macOS)
* [For Windows Systems](/installation/windows)

## Note for Windows Users

Since native Windows installation and operation is not supported, we recommend that Windows users either:

1. Install the Docker version in a Linux (Ubuntu) server in the cloud (see [Setup a Cloud Server](/installation/cloud/))
2. Install the Docker version locally using Docker Toolbox (see [Install on Windows](/installation/windows/))

## Installation from Source (for Developers)

For users who want to access to and intend to edit the codebase, you can install from source:

* [For Linux Systems](/installation/from-source/linux)
* [For macOS Systems](/installation/from-source/macOS)
* [For Windows Systems](/installation/from-source/windows)

