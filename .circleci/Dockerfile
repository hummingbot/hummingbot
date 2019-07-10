# Set the base image
FROM continuumio/miniconda3:4.6.14

# Dockerfile author / maintainer 
LABEL maintainer="CoinAlpha, Inc. <dev@coinalpha.com>"

# Install required packages
RUN pip install nose && apt-get update && apt-get install -y python3-dev