# Set the base image
FROM continuumio/miniconda3:4.6.14

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

# Create mount points
RUN mkdir /conf && mkdir /logs
VOLUME /conf /logs

COPY bin/ bin/
COPY hummingbot/ hummingbot/
COPY setup/environment-linux.yml setup/
COPY setup.py .
COPY LICENSE .
COPY README.md .
COPY DATA_COLLECTION.md .

# Install linux dependencies
RUN apt update && \
    apt-get update && \
    apt-get install -y gcc build-essential

# ./install | create hummingbot environment
RUN conda env create -f setup/environment-linux.yml

# conda activate hummingbot
RUN echo "source activate $(head -1 setup/environment-linux.yml | cut -d' ' -f2)" > ~/.bashrc
ENV PATH /opt/conda/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin:$PATH

# ./compile
RUN /opt/conda/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 setup.py build_ext --inplace -j 8

CMD [ "sh", "-c", "/opt/conda/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 bin/hummingbot_quickstart.py -s ${STRATEGY} -f ${CONFIG_FILE_NAME} -w \"${WALLET}\" -p \"${CONFIG_PASSWORD}\"" ]

