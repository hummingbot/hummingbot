# Set the base image
FROM python:3.13-slim-bookworm AS builder

# Install system dependencies. The PyPI `ta-lib` wheel bundles the TA-Lib C library for Linux
# (verified: it imports and computes correctly with no system libta-lib installed), unlike conda's
# `libta-lib` conda-forge package which this used to need separately. gcc/g++/make/python3-dev are
# a source-build safety net for whichever dependency doesn't ship a wheel for this interpreter/arch.
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0-0 gcc g++ python3-dev make && \
    rm -rf /var/lib/apt/lists/*

# Pinned for reproducible builds (the version uv.lock was written with); bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

# Use the image's own system python, not one uv would download: a downloaded standalone
# interpreter lives under /root (outside what the release stage copies below), and `.venv/bin/python`
# would symlink to it, breaking once this builder stage is discarded.
# (This also makes `.python-version` unnecessary here: the base image already is 3.13.)
ENV UV_PYTHON_PREFERENCE=only-system
# Precompile .pyc files at install time for faster container start-up
ENV UV_COMPILE_BYTECODE=1

WORKDIR /home/hummingbot

# Install the dependency venv (uv sync does not build hummingbot itself — see
# `[tool.uv] package = false` in pyproject.toml). `--locked` fails the build if uv.lock is missing
# or out of date with pyproject.toml instead of silently re-resolving. `--no-dev --group build`
# installs the runtime dependencies plus only what `setup.py build_ext` needs (cython, setuptools),
# keeping test/lint tooling out of the image.
COPY pyproject.toml uv.lock /home/hummingbot/
RUN uv sync --locked --no-dev --group build

# Copy remaining files
COPY bin/ bin/
COPY hummingbot/ hummingbot/
COPY scripts/ scripts/
COPY controllers/ controllers/
COPY scripts/ scripts-copy/
COPY setup.py .
COPY LICENSE .
COPY README.md .

# activate the uv-managed venv when entering the CT
SHELL [ "/bin/bash", "-lc" ]
RUN echo "source /home/hummingbot/.venv/bin/activate" >> ~/.bashrc

# Call the venv's python directly: `uv run` would first re-sync the default groups, re-adding `dev`.
RUN .venv/bin/python setup.py build_ext --inplace -j 8 && \
    rm -rf build/ && \
    find . -type f -name "*.cpp" -delete


# Build final image using artifacts from builder
FROM python:3.13-slim-bookworm AS release

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

# Install system dependencies (the TA-Lib C library ships bundled inside the `ta-lib` wheel).
# libstdc++6 is what the compiled Cython/C++ extensions link against; the base image already has it
# (apt depends on it), but it is listed so the image does not rely on that.
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0-0 libstdc++6 && \
    rm -rf /var/lib/apt/lists/*

# Create mount points
RUN mkdir -p /home/hummingbot/conf /home/hummingbot/conf/connectors /home/hummingbot/conf/strategies /home/hummingbot/conf/controllers /home/hummingbot/conf/scripts /home/hummingbot/logs /home/hummingbot/data /home/hummingbot/certs /home/hummingbot/scripts /home/hummingbot/controllers

WORKDIR /home/hummingbot

# Copy all build artifacts from builder image
COPY --from=builder /home/ /home/

# Put the venv on PATH so non-login shells (e.g. `docker exec … hbot`) find its python +
# console scripts without activating it, and expose the `hbot` CLI there (mirrors make install).
# This lets the image run as a single-bot container: `docker run … hbot start <config>`,
# `docker exec … hbot status`.
ENV PATH=/home/hummingbot/.venv/bin:$PATH
RUN ln -sf /home/hummingbot/bin/hbot /home/hummingbot/.venv/bin/hbot

# Setting bash as default shell because we have .bashrc with customized PATH (setting SHELL affects RUN, CMD and ENTRYPOINT, but not manual commands e.g. `docker run image COMMAND`!)
SHELL [ "/bin/bash", "-lc" ]

# Set the default command to run when starting the container

CMD source /home/hummingbot/.venv/bin/activate && ./bin/hummingbot_quickstart.py 2>> ./logs/errors.log
