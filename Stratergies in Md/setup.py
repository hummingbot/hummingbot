#!/usr/bin/env python

from setuptools import setup, find_packages

# Load requirements from requirements.txt
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

# Load long description from README.md
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="hummingbot-adaptive-mm",
    version="0.1.0",
    author="YourName",
    author_email="your.email@example.com",
    description="Adaptive Market Making Strategy for Hummingbot",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/adaptive-market-making",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
) 