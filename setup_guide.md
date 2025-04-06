# Hummingbot Custom Adaptive Market Making Strategy Setup Guide

This guide provides step-by-step instructions to set up and run the Custom Adaptive Market Making strategy in Hummingbot using Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your system
- Basic knowledge of terminal/command line operations

## Installation Steps

### 1. Pull the Hummingbot Docker Image

```bash
docker pull hummingbot/hummingbot:latest
```

### 2. Create and Start the Docker Container

```bash
docker run -it --name hummingbot \
-v /Users/manuhegde/hummingbot/conf:/home/hummingbot/conf \
-v /Users/manuhegde/hummingbot/logs:/home/hummingbot/logs \
-v /Users/manuhegde/hummingbot/data:/home/hummingbot/data \
-v /Users/manuhegde/hummingbot/scripts:/home/hummingbot/scripts \
hummingbot/hummingbot:latest
```

This command creates a container named "hummingbot" with the following volume mappings:
- Local configuration files → Container's conf directory
- Local logs → Container's logs directory
- Local data → Container's data directory
- Local scripts → Container's scripts directory

### 3. If the Container Already Exists But Is Stopped

If you've previously created the container but it's not running:

```bash
docker start hummingbot
```

### 4. Connect to the Running Container

```bash
docker exec -it hummingbot /bin/bash
```

This command gives you a bash shell inside the running container.

### 5. Start Hummingbot

Once inside the container, start Hummingbot with:

```bash
./bin/hummingbot.py
```

### 6. Run the Custom Adaptive Market Making Strategy

After Hummingbot starts, run the strategy with:

```
start --script custom_adaptive_market_making --conf conf_custom_adaptive_mm.yml
```

## File Locations

Ensure your files are in the correct locations:

- Strategy script: `/home/hummingbot/scripts/custom_adaptive_market_making.py`
- Configuration file: `/home/hummingbot/conf/conf_custom_adaptive_mm.yml`

## Configuration Options

The `conf_custom_adaptive_mm.yml` file contains various configuration options:

- Exchange and trading pair settings
- Basic trading parameters (order amount, refresh time, spreads)
- Technical indicators parameters
- Volatility parameters
- Risk management parameters
- Market regime detection parameters

## Monitoring Your Strategy

Once running, the strategy will display:
- Current market regime and confidence
- Technical indicator values
- Current orders and spreads
- Inventory status
- Recent trades

## Stopping the Strategy

To stop the strategy while in Hummingbot:
1. Press `CTRL+C` to stop the current strategy
2. Type `exit` to exit Hummingbot
3. Type `exit` again to exit the Docker container

## Troubleshooting

If you encounter issues:
1. Verify file locations and permissions
2. Check logs in the `/home/hummingbot/logs` directory
3. Ensure your Docker container has internet connectivity
4. Verify the exchange API keys are properly configured

For more detailed troubleshooting, refer to the [official Hummingbot documentation](https://docs.hummingbot.org/). 