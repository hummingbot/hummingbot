# Custom Adaptive Market Making Strategy

## Overview

This custom market making strategy combines multiple technical indicators, volatility analysis, trend detection, and sophisticated risk management to create an adaptive market making strategy for cryptocurrency trading.

## Features

- Dynamic spread adjustment based on volatility
- Trend analysis using RSI, EMA, and MACD
- Risk management through inventory control
- Position sizing based on volatility and market regime
- Support and resistance detection

## Requirements

- Hummingbot v2.0.0 or later
- Docker (recommended) or local installation

## Quick Start

### Using Docker (Recommended)

1. Start the Hummingbot container:
   ```
   docker-compose up -d
   ```

2. Connect to the Hummingbot container:
   ```
   docker exec -it hummingbot /bin/bash
   ```

3. Inside the container, start Hummingbot:
   ```
   ./bin/hummingbot.py
   ```

4. Start the strategy with the configuration file:
   ```
   start --script custom_adaptive_market_making --conf conf_custom_adaptive_mm.yml
   ```

### Using Local Installation

1. Ensure the script and configuration file are in the correct directories:
   - Script: `scripts/custom_adaptive_market_making.py`
   - Config: `conf/conf_custom_adaptive_mm.yml`

2. Start Hummingbot:
   ```
   ./start
   ```

3. Start the strategy with the configuration file:
   ```
   start --script custom_adaptive_market_making --conf conf_custom_adaptive_mm.yml
   ```

## Configuration

The strategy is configured through `conf_custom_adaptive_mm.yml`. Key parameters include:

- Exchange and trading pair settings
- Basic trading parameters (order amount, refresh time, spreads)
- Technical indicators parameters
- Volatility parameters
- Risk management parameters
- Market regime detection parameters

## Status Display

The strategy includes a comprehensive status display showing:

- Current market regime and confidence
- Technical indicator values and signals
- Current spreads and order sizes
- Inventory management status
- Active orders and recent trades

## Support

For issues or questions, please refer to the [Hummingbot documentation](https://docs.hummingbot.org) or the [Hummingbot Discord community](https://discord.gg/hummingbot).

## License

This strategy is provided for educational and research purposes under the Apache License 2.0.

## Disclaimer

This strategy is for educational purposes only. Use at your own risk. Always test thoroughly on paper trading before using with real funds. 