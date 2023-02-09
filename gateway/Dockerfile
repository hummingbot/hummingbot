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
WORKDIR /usr/src/app/

# copy pwd file to container
COPY . .

RUN ln -s /conf /usr/src/app/conf && \
    ln -s /logs /usr/src/app/logs && \
    ln -s /certs /usr/src/app/certs

# create app writable directory for db files
RUN mkdir -p /var/lib/gateway /certs /conf /logs /usr/src/app/gateway.level /usr/src/app/transactions.level \
    /usr/src/app/db
RUN chown -R hummingbot:hummingbot /var/lib/gateway /usr/src/app/logs /usr/src/app/conf /usr/src/app/certs \
    /usr/src/app/gateway.level /usr/src/app/transactions.level /usr/src/app/db

# install dependencies
RUN yarn install --frozen-lockfile

EXPOSE 15888

RUN yarn build

CMD ["gosu", "hummingbot:hummingbot", "yarn", "run", "start"]
