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
COPY mcp_server.py .

# MCP server runtime: a dedicated venv so its deps (mcp/starlette/uvicorn) can never
# conflict with the trading env. bin/hbot-mcp execs this python when it exists.
RUN python3 -m venv /opt/mcp-venv && \
    /opt/mcp-venv/bin/pip install --no-cache-dir "mcp>=1.10"

# activate hummingbot env when entering the CT
SHELL [ "/bin/bash", "-lc" ]
RUN echo "conda activate hummingbot" >> ~/.bashrc

COPY setup/pip_packages.txt /tmp/pip_packages.txt
RUN python3 -m pip install --no-deps -r /tmp/pip_packages.txt && \
    rm /tmp/pip_packages.txt


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
ENV BUILD_DATE=${BUILD_DATE}

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
COPY --from=builder /opt/mcp-venv/ /opt/mcp-venv/
COPY --from=builder /home/ /home/

# Put the hummingbot env on PATH so non-login shells (e.g. `docker exec … hbot`) find the env's python
# + console scripts without `conda activate`, and expose the `hbot` CLI there (mirrors make install).
# This lets the image run as a single-bot container: `docker run … hbot start <config>`,
# `docker exec … hbot status`.
ENV PATH=/opt/conda/envs/hummingbot/bin:$PATH
RUN ln -sf /home/hummingbot/bin/hbot /opt/conda/envs/hummingbot/bin/hbot && \
    ln -sf /home/hummingbot/bin/hbot-mcp /opt/conda/envs/hummingbot/bin/hbot-mcp

# The MCP server shells out to hbot; point it straight at the env's CLI so it skips the
# conda-env probe bin/hbot-host would run on every tool call.
ENV HBOT_BIN=/opt/conda/envs/hummingbot/bin/hbot

# Interactive shells (`docker exec -it … bash`) source /root/.bashrc, whose conda init
# activates BASE — whose python then shadows the env for `#!/usr/bin/env python` scripts
# like hbot. Activate the hummingbot env instead. (The builder stage sets this in ITS OWN
# /root/.bashrc, which is never copied here — this must be done in the release stage.)
RUN echo "conda activate hummingbot" >> /root/.bashrc

# Setting bash as default shell because we have .bashrc with customized PATH (setting SHELL affects RUN, CMD and ENTRYPOINT, but not manual commands e.g. `docker run image COMMAND`!)
SHELL [ "/bin/bash", "-lc" ]

# Set the default command to run when starting the container

CMD conda activate hummingbot && ./bin/hummingbot_quickstart.py 2>> ./logs/errors.log
