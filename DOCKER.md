# Docker Instructions

Compiled versions of `hummingbot` are available on Docker Hub at [`coinalpha/hummingbot`](https://hub.docker.com/r/coinalpha/hummingbot).

## Running `hummingbot` with Docker

For instructions on operating `hummingbot` with Docker, navigate to [`hummingbot` documentation: Install with Docker](https://docs.hummingbot.io/installation/#install-via-docker).

---

## Development commands: deploying to Docker Hub

### Create docker image

```sh
# Create a label for image
export TAG=my-label

# Build docker image
$ docker build -t coinalpha/hummingbot:$TAG -f Dockerfile .

# Push docker image to docker hub
$ docker push coinalpha/hummingbot:$TAG
```

#### Build and Push

```sh
$ docker image rm coinalpha/hummingbot:$TAG && \
  docker build -t coinalpha/hummingbot:$TAG -f Dockerfile . && \
  docker push coinalpha/hummingbot:$TAG
```
