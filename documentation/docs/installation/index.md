# Installing Hummingbot

## System requirements

Hummingbot has been successfully tested with the following specifications:

Resource | Requirement
---|---
**Operating System** | **Linux**: Ubuntu 16.04 or later (recommended)<ul><li>*Other Linux installations: Debian GNU/Linux 9, CentOS 7, Amazon Linux 2 AMI*</ul>**MacOS**: macOS 10.12.6 (Sierra) or later<br/>**Windows**: Windows 10 or later
**Memory/RAM** | 1 GB one instance *+250 MB per additional instance*
**Storage** | <li>**Install using Docker**: 5 GB per instance<li>**Install from source**: 3 GB per instance
**Network** | A reliable internet connection is critical to keeping Hummingbot connected to exchanges.

## For new users

For new users, we recommend installing Hummingbot on a desktop or laptop computer in order to test it out.

Windows and macOS users can download the installer, while Linux users can install Hummingbot via Docker.

* **Windows**: [Download Hummingbot](https://hummingbot.io/download) | [Installation Guide](download/windows)
* **macOS**: [Download Hummingbot](https://hummingbot.io/download) | [Installation Guide](download/macos)
* **Linux**: [Install via Docker](docker/linux/)

## For experienced users and developers

For experienced and technical users, we recommend setting up a cloud instance and installing the Docker version or from source. This enables Hummingbot to run 24/7. 

See our [Cloud Server guide](cloud) for how to set up a server on the top cloud platforms (AWS, Google Cloud, and Azure).

### Install via Docker
* [Linux](docker/linux/)
* [Windows](docker/windows)
* [macOS](docker/macOS)

### Install from source
* [Linux](source/linux)
* [Windows](source/windows)
* [macOS](source/macOS)

## Updating Hummingbot

We publish a new release of Hummingbot approximately once every month. 

See this article for instructions on keeping Hummingbot updated: [Updating Hummingbot](updating.md)