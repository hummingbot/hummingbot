# Docker Instructions

Base image for CI, including:
- miniconda
- nosetests

```sh
# Build docker image
$ docker build -t coinalpha/condatest:$TAG -f Dockerfile .

# Push docker image to docker hub
$ docker push coinalpha/condatest:$TAG
```

#### Build and Push

```sh
$ docker image rm coinalpha/condatest:$TAG && \
  docker build -t coinalpha/condatest:$TAG -f Dockerfile \
  docker push coinalpha/condatest:$TAG
```
