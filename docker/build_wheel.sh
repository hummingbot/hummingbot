#!/bin/bash

# NOTE: ** Run from Linux machine **

# Remove existing environment, if it exists
conda env remove -n $(head -1 setup/environment-dist.yml | cut -d' ' -f2) -y

# Create environment
conda env create -f setup/environment-dist.yml

# Activate environment
echo "source activate $(head -1 setup/environment-dist.yml | cut -d' ' -f2)" > ~/.bashrc
source activate $(head -1 setup/environment-dist.yml | cut -d' ' -f2)

# Create hummingbot package  
python setup.py bdist_wheel