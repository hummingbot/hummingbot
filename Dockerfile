# Set the base image
FROM ubuntu:20.04

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

# Add hummingbot user
RUN useradd -m -s /bin/bash hummingbot && \
  ln -s /conf /home/hummingbot/conf && \
  ln -s /logs /home/hummingbot/logs && \
  ln -s /data /home/hummingbot/data

# Create mount points
RUN mkdir /conf /logs /data && chown -R hummingbot:hummingbot /conf /logs /data
VOLUME /conf /logs /data

# Install linux dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y gcc \
        build-essential pkg-config libusb-1.0 curl git \
        sudo


# Switch to hummingbot user
USER hummingbot:hummingbot
WORKDIR /home/hummingbot

# Copy files
COPY --chown=hummingbot:hummingbot bin/ bin/
COPY --chown=hummingbot:hummingbot hummingbot/ hummingbot/
COPY --chown=hummingbot:hummingbot setup/environment-linux.yml setup/
COPY --chown=hummingbot:hummingbot setup.py .
COPY --chown=hummingbot:hummingbot LICENSE .
COPY --chown=hummingbot:hummingbot README.md .
COPY --chown=hummingbot:hummingbot DATA_COLLECTION.md .
COPY docker/etc /etc

# Install miniconda
RUN curl https://repo.anaconda.com/miniconda/Miniconda3-py38_4.8.2-Linux-x86_64.sh -o ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b && \
    rm ~/miniconda.sh && \
    ~/miniconda3/bin/conda clean -tipsy && \
    ~/miniconda3/bin/conda update -n base conda -y

# ./install | create hummingbot environment
RUN ~/miniconda3/bin/conda env create -f setup/environment-linux.yml

# conda activate hummingbot
RUN echo "source /home/hummingbot/miniconda3/etc/profile.d/conda.sh && conda activate $(head -1 setup/environment-linux.yml | cut -d' ' -f2)" > ~/.bashrc
ENV PATH /home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin:$PATH

# Install nvm and CeloCLI
SHELL [ "/bin/bash", "-lc" ]
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.35.3/install.sh | bash && \
    export NVM_DIR="/home/hummingbot/.nvm" && \
    source "/home/hummingbot/.nvm/nvm.sh" && \
    source "/home/hummingbot/miniconda3/etc/profile.d/conda.sh" && \
    conda activate hummingbot && \
    nvm install 10 && \
    npm install -g @celo/celocli@0.0.48

# ./compile
RUN /home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 setup.py build_ext --inplace -j 8

CMD /home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 bin/hummingbot_quickstart.py \
    --auto-set-permissions $(id -nu):$(id -ng)
