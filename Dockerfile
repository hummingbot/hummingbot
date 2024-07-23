# Set the base image
FROM continuumio/miniconda3:latest AS builder

# Install system dependencies
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0 gcc g++ python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /home/hummingbot

# Create conda environment
COPY setup/environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml && \
    conda clean -afy && \
    rm /tmp/environment.yml

# Copy remaining files
COPY bin/ bin/
COPY hummingbot/ hummingbot/
COPY scripts/ scripts/
COPY controllers/ controllers/
COPY scripts/ scripts-copy/
COPY setup.py .
COPY LICENSE .
COPY README.md .
COPY DATA_COLLECTION.md .

# activate hummingbot env when entering the CT
SHELL [ "/bin/bash", "-lc" ]
RUN echo "conda activate hummingbot" >> ~/.bashrc

RUN python3 setup.py build_ext --inplace -j 8 && \
    rm -rf build/ && \
    find . -type f -name "*.cpp" -delete


# Build final image using artifacts from builder
FROM continuumio/miniconda3:latest AS release

# Dockerfile author / maintainer
LABEL maintainer="Fede Cardoso @dardonacci <federico@hummingbot.org>"

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

ENV INSTALLATION_TYPE=docker

# Install system dependencies
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0 && \
    rm -rf /var/lib/apt/lists/*

# Create mount points
RUN mkdir -p /home/hummingbot/conf /home/hummingbot/conf/connectors /home/hummingbot/conf/strategies /home/hummingbot/conf/controllers /home/hummingbot/conf/scripts /home/hummingbot/logs /home/hummingbot/data /home/hummingbot/certs /home/hummingbot/scripts /home/hummingbot/controllers

WORKDIR /home/hummingbot

# Copy all build artifacts from builder image
COPY --from=builder /opt/conda/ /opt/conda/
COPY --from=builder /home/ /home/

######## resolve dydx&injective confilct ###############
ENV SRC_TARGET_PATH=anaconda3/envs/hummingbot/lib/python3.10/site-packages/v4_proto/cosmos
ENV DEST_TARGET_PATH=anaconda3/envs/hummingbot/lib/python3.10/site-packages/pyinjective/proto/cosmos

RUN apt-get update && apt-get install -y findutils

RUN SRC_DIR=$(find / -type d -path "*/$SRC_TARGET_PATH" 2>/dev/null) \
    && DEST_DIR=$(find / -type d -path "*/$DEST_TARGET_PATH" 2>/dev/null) \
    && if [ ! -d "$SRC_DIR" ]; then \
         echo "Source directory $SRC_DIR does not exist." \
         && exit 1; \
       fi \
    && if [ ! -d "$DEST_DIR" ]; then \
         echo "Destination directory $DEST_DIR does not exist." \
         && exit 1; \
       fi \
    && for dir in $(ls "$SRC_DIR"); do \
         if [ -d "$SRC_DIR/$dir" ]; then \
           echo "Copying directory $dir from $SRC_DIR to $DEST_DIR" \
           && mkdir -p "$DEST_DIR/$dir" \
           && cp -r "$SRC_DIR/$dir"/* "$DEST_DIR/$dir"/; \
         fi \
       done \

######## resolve dydx&injective confilct END ###############

# Setting bash as default shell because we have .bashrc with customized PATH (setting SHELL affects RUN, CMD and ENTRYPOINT, but not manual commands e.g. `docker run image COMMAND`!)
SHELL [ "/bin/bash", "-lc" ]

# Set the default command to run when starting the container

CMD conda activate hummingbot && ./bin/hummingbot_quickstart.py 2>> ./logs/errors.log