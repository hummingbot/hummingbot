# Docker

## Why use Docker Compose?

Using Docker for Hummingbot deployment offers several benefits, such as simplifying the installation process, enabling easy versioning and scaling, and ensuring a consistent and isolated environment for running the bot. This repository aims to help users get started with deploying Hummingbot using Docker by providing different examples that demonstrate how to set up and customize the bot according to their needs.

## Install Docker Compose

The examples below use Docker Compose, a tool for defining and running multi-container Docker applications. You can install Docker Compose either via command line or by running an installer.

Linux (Ubuntu / Debian):

```bash
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

Mac (Homebrew):

```bash
brew install docker-compose
```

If you want to be guided through the installation, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) includes Docker Compose along with Docker Engine and Docker CLI which are Compose prerequisites:

* [Linux](https://docs.docker.com/desktop/install/linux-install/)
* [Mac](https://docs.docker.com/desktop/install/mac-install/)
* [Windows](https://docs.docker.com/desktop/install/windows-install/)


Verify that Docker Compose is installed correctly by checking the version:

```bash
docker compose version
```

Hummingbot's [deploy-examples](https://github.com/hummingbot/deploy-examples) repository provides various examples of how to deploy Hummingbot using Docker Compose, a tool for defining and running multi-container Docker applications.

Compiled images of `hummingbot` are available on our official DockerHub: https://hub.docker.com/r/hummingbot/hummingbot

## Building a Docker Image

You can also build and run a Docker-based Hummingbot image using the `docker-compose.yml` file in the root folder:
```yml
version: "3.9"
services:
  hummingbot:
    container_name: hummingbot
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./conf:/home/hummingbot/conf
      - ./conf/connectors:/home/hummingbot/conf/connectors
      - ./conf/strategies:/home/hummingbot/conf/strategies
      - ./logs:/home/hummingbot/logs
      - ./data:/home/hummingbot/data
      - ./scripts:/home/hummingbot/scripts
    environment:
      # - CONFIG_PASSWORD=a
      # - CONFIG_FILE_NAME=directional_strategy_rsi.py
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: 5
    tty: true
    stdin_open: true
    network_mode: host

  dashboard:
    container_name: dashboard
    image: hummingbot/dashboard:latest
    volumes:
      - ./data:/home/dashboard/data
    ports:
      - "8501:8501"
```

Build and launch the image by running:
```
docker compose up -d
```

Uncomment the following lines in the YML file before running the command above if you would like to:
* Bypass the password screen by entering the previously set password
* Auto-starting a script
```
  # environment:
    # - CONFIG_PASSWORD=a
    # - CONFIG_FILE_NAME=directional_strategy_rsi.py
```

## Useful Docker Commands

Use the commands below or use the Docker Desktop application to manage your containers:

### Create the Compose project
```
docker compose up -d
```

### Stop the Compose project
```
docker compose down
```

### Update the Compose project for the latest images
```
docker compose up --force-recreate --build -d
```

### Give all users read/write permissions to local files
```
sudo chmod -R a+rw <files/folders>
```

### Attach to the container
```
docker attach <container-name>
```

### Detach from the container and return to command line

Press keys <kbd>Ctrl</kbd> + <kbd>P</kbd> then <kbd>Ctrl</kbd> + <kbd>Q</kbd>


### Update the container to the latest image
```
docker compose up --force-recreate --build -d
```

### List all containers
```
docker ps -a
```

### Stop a container
```
docker stop <container-name>
```

### Remove a container
```
docker rm <container-name>
```
