# Set the base image
FROM continuumio/miniconda3:4.6.14

# Dockerfile author / maintainer 
LABEL maintainer="CoinAlpha, Inc. <dev@coinalpha.com>"

# Create mount points
RUN mkdir /conf && mkdir /logs
VOLUME /conf /logs

COPY bin/ bin/
COPY hummingbot/ hummingbot/
COPY setup/environment-linux.yml setup/
COPY setup.py .
COPY LICENSE .

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

CMD [ "sh", "-c", "/opt/conda/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 bin/hummingbot.py" ]
