FROM node:18.10.0

# Set labels
LABEL application="gateway-v2"
LABEL branch=${BRANCH}
LABEL commit=${COMMIT}
LABEL date=${BUILD_DATE}

# Set ENV variables
ENV COMMIT_BRANCH=${BRANCH}
ENV COMMIT_SHA=${COMMIT}
ENV BUILD_DATE=${DATE}

# Add hummingbot user and group
RUN groupadd -g 8211 hummingbot && \
    useradd -m -s /bin/bash -u 8211 -g 8211 hummingbot

# Install gosu
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y gosu && \
    rm -rf /var/lib/apt/lists/*

# app directory
WORKDIR /usr/src/app

# create app writable directory for db files
RUN mkdir /var/lib/gateway
RUN chown -R hummingbot /var/lib/gateway

# copy pwd file to container
COPY . .

# install dependencies
RUN yarn install --frozen-lockfile

EXPOSE 15888

RUN yarn build

CMD ["bin/docker-start.sh"]
