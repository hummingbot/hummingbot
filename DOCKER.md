# Docker Instructions

Compiled versions of `hummingbot` are available on Docker Hub at [`coinalpha/hummingbot`](https://hub.docker.com/r/coinalpha/hummingbot).

## Running `hummingbot` with Docker

For instructions on operating `hummingbot` with Docker, navigate to [`hummingbot` documentation: Install with Docker](https://docs.hummingbot.io/installation/#install-via-docker).

---

## Development commands: The following commands apply to deploying to Docker Hub.

### Create docker image

```sh
# Define a tag for the Docker image, like a version number
# For example, TAG=my-label
export TAG=<your_tag>

# Build Docker image with the given tag and the Dockerfile in the current directory
docker build -t coinalpha/hummingbot:${TAG} -f Dockerfile .

# Push the Docker image with the given tag to the Docker Hub repository
docker push coinalpha/hummingbot:${TAG}
```

#### Build and Push

```sh
$ docker image rm coinalpha/hummingbot:$TAG && \
  docker build -t coinalpha/hummingbot:$TAG -f Dockerfile . && \
  docker push coinalpha/hummingbot:$TAG
```
