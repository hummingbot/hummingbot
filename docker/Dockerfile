# Set the base image
FROM continuumio/anaconda3

# Dockerfile author / maintainer 
LABEL maintainer="CoinAlpha, Inc. <dev@coinalpha.com>"

# Build Variables
ARG LINUX_PACKAGE

COPY dist/${LINUX_PACKAGE} .
COPY setup/environment-dist.yml setup/
COPY LICENSE .

# Update Conda
RUN conda update -n base -c defaults conda

# Install Linux Dependencies
RUN apt update && \
    apt-get update && \
    apt-get install -y gcc build-essential

# Install Hummingbot and Create Environment
RUN conda env create -f setup/environment-dist.yml

# Install Hummingbot
RUN /opt/conda/envs/$(head -1 setup/environment-dist.yml | cut -d' ' -f2)/bin/pip install ${LINUX_PACKAGE}

# Pull the environment name out of the environment-linux.yml and activate
RUN echo "source activate $(head -1 setup/environment-dist.yml | cut -d' ' -f2)" > ~/.bashrc
ENV PATH /opt/conda/envs/$(head -1 setup/environment-dist.yml | cut -d' ' -f2)/bin:$PATH

# Clean-up: remove unnecessary file(s)
RUN rm ${LINUX_PACKAGE}

CMD [ "sh", "-c", "/opt/conda/envs/$(head -1 setup/environment-dist.yml | cut -d' ' -f2)/bin/hummingbot.py" ]