# Set the base image
FROM arm64v8/python:3.7-slim AS builder

# Install linux dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y gcc \
        build-essential pkg-config libusb-1.0 curl git sudo libudev-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Add hummingbot user
RUN useradd -m -s /bin/bash hummingbot

# Switch to hummingbot user
USER hummingbot:hummingbot
WORKDIR /home/hummingbot

# Install miniconda
RUN curl https://repo.anaconda.com/miniconda/Miniconda3-py37_4.9.2-Linux-aarch64.sh -o ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b && \
    rm ~/miniconda.sh && \
    ~/miniconda3/bin/conda init && \
    ~/miniconda3/bin/conda clean -tipsy

# Dropping default ~/.bashrc because it will return if not running as interactive shell, thus not invoking PATH settings
RUN :> ~/.bashrc

# Install nvm and CeloCLI; note: nvm adds own section to ~/.bashrc
SHELL [ "/bin/bash", "-lc" ]
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && \
    export NVM_DIR="/home/hummingbot/.nvm" && \
    source "/home/hummingbot/.nvm/nvm.sh" && \
    nvm install 10 && \
    npm install --only=production -g @celo/celocli@1.0.3 && \
    nvm cache clear && \
    npm cache clean --force && \
    rm -rf /home/hummingbot/.cache

# Copy environment only to optimize build caching, so changes in sources will not cause conda env invalidation
COPY --chown=hummingbot:hummingbot setup/environment-linux-aarch64.yml setup/

# ./install | create hummingbot environment
RUN ~/miniconda3/bin/conda env create -f setup/environment-linux-aarch64.yml && \
    ~/miniconda3/bin/conda clean -tipsy && \
    # clear pip cache
    rm -rf /home/hummingbot/.cache

# Copy remaining files
COPY --chown=hummingbot:hummingbot bin/ bin/
COPY --chown=hummingbot:hummingbot hummingbot/ hummingbot/
COPY --chown=hummingbot:hummingbot setup.py .
COPY --chown=hummingbot:hummingbot LICENSE .
COPY --chown=hummingbot:hummingbot README.md .
COPY --chown=hummingbot:hummingbot DATA_COLLECTION.md .

# activate hummingbot env when entering the CT
RUN echo "source /home/hummingbot/miniconda3/etc/profile.d/conda.sh && conda activate $(head -1 setup/environment-linux-aarch64.yml | cut -d' ' -f2)" >> ~/.bashrc

# ./compile + cleanup build folder
RUN /home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux-aarch64.yml | cut -d' ' -f2)/bin/python3 setup.py build_ext --inplace -j 8 && \
    rm -rf build/ && \
    find . -type f -name "*.cpp" -delete

# Build final image using artifacts from builder
FROM arm64v8/python:3.7-slim AS release
# Dockerfile author / maintainer 
LABEL maintainer="CoinAlpha, Inc. <dev@coinalpha.com>"

# Build arguments
ARG BRANCH=""
ARG COMMIT=""
ARG BUILD_DATE=""
LABEL branch=${BRANCH}
LABEL commit=${COMMIT}
LABEL date=${BUILD_DATE}

# Set ENV variables
ENV COMMIT_SHA=${COMMIT}
ENV COMMIT_BRANCH=${BRANCH}
ENV BUILD_DATE=${DATE}

ENV STRATEGY=${STRATEGY}
ENV CONFIG_FILE_NAME=${CONFIG_FILE_NAME}
ENV WALLET=${WALLET}
ENV CONFIG_PASSWORD=${CONFIG_PASSWORD}

ENV INSTALLATION_TYPE=docker

# Add hummingbot user
RUN useradd -m -s /bin/bash hummingbot

# Create mount points
RUN mkdir /conf /logs /data /certs /scripts && chown -R hummingbot:hummingbot /conf /logs /data /certs /scripts
VOLUME /conf /logs /data /certs /scripts

# Add symbolic links to key folders
RUN ln -s /conf /home/hummingbot/conf && \
  ln -s /logs /home/hummingbot/logs && \
  ln -s /data /home/hummingbot/data && \
  ln -s /certs /home/hummingbot/certs && \
  ln -s /scripts /home/hummingbot/scripts

# Pre-populate scripts/ volume with default scripts
COPY --chown=hummingbot:hummingbot scripts/ scripts/

# Install packages required in runtime
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y sudo libusb-1.0 libudev-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Switch to hummingbot user
USER hummingbot:hummingbot
WORKDIR /home/hummingbot

# Copy all build artifacts from builder image
COPY --from=builder --chown=hummingbot:hummingbot /home/ /home/

# additional configs (sudo)
COPY docker/etc /etc

# Setting bash as default shell because we have .bashrc with customized PATH (setting SHELL affects RUN, CMD and ENTRYPOINT, but not manual commands e.g. `docker run image COMMAND`!)
SHELL [ "/bin/bash", "-lc" ]
CMD /home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux-aarch64.yml | cut -d' ' -f2)/bin/python3 bin/hummingbot_quickstart.py \
    --auto-set-permissions $(id -nu):$(id -ng)
