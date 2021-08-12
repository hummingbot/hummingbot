
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

## Supported-installation environments

| Platform     |                  Binary                             |                  Docker                             |                  Source                             |
| ------------ | :-------------------------------------------------: | :-------------------------------------------------: | :-------------------------------------------------: |
| Windows      | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> |
| MacOS        | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> |
| Linux        |                     -                               | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> |
| Raspberry Pi |                     -                               | <span style="color:green; font-size:25px">⬤</span> | <span style="color:green; font-size:25px">⬤</span> |

## For cloud

For experienced and technical users, we recommend setting up a cloud instance and installing the Docker version or from source. This enables Hummingbot to run 24/7.

Using Hummingbot as a long running service can be achieved with the help of cloud platforms such as Google Cloud Platform, Amazon Web Services, and Microsoft Azure. You may read our blog about running [Hummingbot on different cloud providers](https://www.hummingbot.io/blog/2019-06-cloud-providers/).

As of **version 0.28.0** installing Docker takes up around 500 MB of storage space and 4 GB for Hummingbot Docker image. We tested to install and run Hummingbot on these free to lowest machine types.

| Provider              | Instance Type   | Instance Details      |
| --------------------- | --------------- | --------------------- |
| Google Cloud Platform | g1-small        | 1 vCPU, 1.7 GB memory |
| Amazon Web Services   | t2.small        | 1 vCPU, 2 GB memory   |
| Microsoft Azure       | Standard_D2s_v3 | 2 vCPU, 8 GB memory   |

These instances are pre-loaded with system files that takes up around 1.2 GB so we recommend having at least **8 GB of storage space** in your cloud server.

!!! note
    Exception for celo-arb strategy — Running a [Celo Arbitrage](https://docs.hummingbot.io/strategies/celo-arb/) strategy requires a minimum of `t2.medium` AWS instance type for improved performance.

Check with the relevant cloud provider for instructions on how to set up a new Virtual Machine Instance on each major cloud platform.

## Update Hummingbot

We publish a new release of Hummingbot approximately once every month.

See this article for instructions on how to Restore or Update Hummingbot version:

- [Update Version](./update-version)

- [Restore Previous Version](./restore-previous-version)
