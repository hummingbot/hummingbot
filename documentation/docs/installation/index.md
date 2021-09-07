Hummingbot is a local software client that helps you run trading strategies that automate the execution of orders and trades on various cryptocurrency exchanges and protocols.

Hummingbot's code is publicly hosted at https://github.com/coinalpha/hummingbot, and the `development` branch is continually updated. Approximately once a month, we publish an official release of Hummingbot onto the `master` branch.

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

## Installation guides

### [Install on MacOS/Windows](./binaries)

Download and run the binary installer to run Hummingbot on **MacOS** or **Windows**.

### [Install Docker image](./docker)

Installed a compiled Docker image. CoinAlpha publishes Docker images for the `latest` and `development` builds of Hummingbot, as well as every version. 

We recommend this path for users who run Hummingbot in the cloud or multiple bots.

### [Install from Source](./source)

Install Hummingbot from source, including all dependencies. 

We recommend this path for users who want to customize Hummingbot's behavior or to build new connectors and strategies.

### [Install on Raspberry Pi](./raspberry-pi)

Experimental.
