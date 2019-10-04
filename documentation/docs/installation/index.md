# Overview of Hummingbot Installation

## Minimum System Requirements

Hummingbot has been successfully tested with the following specifications:

Resource | Requirement
---|---
**Operating System** | **Linux**: Ubuntu 16.04 or later (recommended)<ul><li>*Other Linux installations: Debian GNU/Linux 9, CentOS 7, Amazon Linux 2 AMI*</ul>**MacOS**: macOS 10.12.6 (Sierra) or later<br/>**Windows**: Windows 10 or later
**Memory/RAM** | 1 GB one instance *+250 MB per additional instance*
**Storage** | <li>**Install using Docker**: 5 GB per instance<li>**Install from source**: 3 GB per instance
**Network** | A reliable internet connection is critical to keeping Hummingbot connected to exchanges.

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
2. [Install Docker + Hummingbot on Linux](/installation/via-docker/linux)

Alternative installations with Docker:

* [For macOS Systems](/installation/via-docker/macOS)
* [For Windows Systems](/installation/via-docker/windows)

## Note for Windows Users

Native Windows installation and operation is currenty not supported.  We recommend that Windows users either:

1. Install the Docker version in a Linux (Ubuntu) server in the cloud (see [Setup a Cloud Server](/installation/cloud/))
2. Install the Docker version locally using Docker Toolbox (see [Install on Windows](/installation/via-docker/windows/))

## Installation from Source (for Developers)

For users who want to access to and intend to edit the codebase, you can install from source:

* [For Linux Systems](/installation/from-source/linux)
* [For macOS Systems](/installation/from-source/macOS)
* [For Windows Systems](/installation/from-source/windows)
