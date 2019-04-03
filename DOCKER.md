# Docker Instructions

Compiled versions of `hummingbot` are available on Docker Hub at [`coinalpha/hummingbot`](https://cloud.docker.com/u/coinalpha/repository/docker/coinalpha/hummingbot).

## Running `hummingbot` with Docker

For instructions on operating `hummingbot` with Docker, navigate to [`hummingbot` documentation: docker instructions](https://docs.hummingbot.io/installation/#option-1-run-hummingbot-using-docker).

---

## Development commands: deploying to Docker Hub

### 1) Build binary

From a Linux environment, build a wheel by running the following command from this repo's root folder:

```sh
# Run from repo root/
$ ./docker/build_wheel.sh
```

This will create a new wheel file in the `dist/` folder.  Note the name of this new wheel file, which will be used in step 2.


### 2) Build DockerFile

Run the docker build command as follows, with the wheel file name as the argument `LINUX_PACKAGE`

```sh
# Run from root/
$ docker build -t coinalpha/hummingbot:$TAG -f ./docker/Dockerfile --build-arg LINUX_PACKAGE=$WHL_FILENAME .
```

#### Build and Push

```sh
$ docker image rm coinalpha/hummingbot:$TAG && \
  docker build -t coinalpha/hummingbot:$TAG -f ./docker/Dockerfile \
  --build-arg LINUX_PACKAGE=$WHL_FILENAME . && \
  docker push coinalpha/hummingbot:$TAG
```
