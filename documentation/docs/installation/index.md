Hummingbot is a local software client that helps you run trading strategies that automate the execution of orders and trades on various cryptocurrency exchanges and protocols.

## Releases

Hummingbot's code is publicly hosted at https://github.com/coinalpha/hummingbot, and the `development` branch is continually updated. 

Approximately once a month, we publish an official release of Hummingbot onto the `master` branch. See [Releases](https://github.com/CoinAlpha/hummingbot/releases).

## Installation options

### 💻 Binary (Mac/Windows)

Download and run the binary installer to install the latest release of Hummingbot:

[Windows :fontawesome-brands-windows:](https://dist.hummingbot.io/hummingbot_v0.44.0_setup.exe){ .md-button } [MacOS :fontawesome-brands-apple:](https://dist.hummingbot.io/hummingbot_v0.44.0.dmg){ .md-button }

Read the binary installation guide: [Install Hummingbot on MacOS/Windows](./binary)

### 🐳 Docker

The [Hummingbot DockerHub](https://hub.docker.com/r/coinalpha/hummingbot) publishes Docker images for the `master` (latest) and `development` builds of Hummingbot, as well as past versions. 

We recommend this path for users who run Hummingbot on Linux, in the cloud, and/or multiple bots.

Read the Docker installation guide: [Install Hummingbot on Docker](./docker)

### 🛠️ Source

Install Hummingbot from source, including all dependencies.

We recommend this path for **developers** who want to customize Hummingbot's behavior or to build new connectors and strategies.

Read the source installation guide: [Install Hummingbot from Source](./source)

### 🍓 Raspberry Pi

Hummingbot doesn't require much power, so some users have run successfully run multiple instances on a single Raspberry Pi. We maintain an **experimental** build that shows users how to do this.

[Install on Raspberry Pi](./raspberry-pi)

## System requirements

Hummingbot has been successfully tested with the following specifications:

| Resource             | Requirement                                                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Operating System** | **Linux**: Ubuntu 16.04 or later (recommended) \*Other Linux installations: Debian GNU/Linux 9, CentOS 7, Amazon Linux 2 AMI |
|                      | **MacOS**: macOS 10.12.6 (Sierra) or later                                                                                   |
|                      | **Windows**: Windows 10 or later                                                                                             |
| **Memory/RAM**       | 1 GB one instance _+250 MB per additional instance_                                                                          |
| **Storage**          | **Install using Docker**: 5 GB per instance                                                                                  |
|                      | **Install from source**: 3 GB per instance                                                                                   |
| **Network**          | A reliable internet connection is critical to keeping Hummingbot connected to exchanges.                                     |
