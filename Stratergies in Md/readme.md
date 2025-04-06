# Adaptive Market Making Strategy for Hummingbot

A sophisticated market making strategy that combines technical indicators, multi-timeframe analysis, and risk management to dynamically adjust market making parameters based on current market conditions.

## Overview

This repository contains a Hummingbot implementation of an adaptive market making strategy. It improves upon the basic Pure Market Making algorithm by adding:

1. **Technical Analysis Integration**: Uses RSI, MACD, EMA, and Bollinger Bands to analyze market conditions
2. **Dynamic Parameter Adjustment**: Automatically modifies spreads and order sizes based on market conditions
3. **Market Regime Detection**: Identifies trending, ranging, and volatile market conditions
4. **Score-Based Signal System**: Employs a weighted scoring system to guide trading decisions
5. **Risk Management Framework**: Implements inventory management and position sizing controls

## Repository Structure

```
hummingbot/
├── client/                 # Client-side code
│   ├── config/             # Configuration framework
│   └── settings/           # Client settings
├── conf/                   # Configuration files
│   └── strategies/         # Strategy-specific configurations
├── connector/              # Exchange connectors
│   └── exchange/           # Exchange-specific connectors
├── core/                   # Core functionality
│   ├── clock.py            # Time synchronization
│   ├── data_type/          # Data structure definitions
│   └── event/              # Event handling
├── model/                  # Data models
├── scripts/                # Strategy scripts
│   └── adaptive_market_making.py  # Adaptive Market Making Strategy
├── strategy/               # Strategy framework
│   └── script_strategy_base.py    # Base class for strategies
├── templates/              # Template files
└── util/                   # Utility functions
    └── indicators.py       # Technical indicator implementations
```

## Features

- **Dynamic Spread Calculation**: Adjusts bid/ask spreads based on market volatility, technical indicators, and inventory position
- **Smart Order Sizing**: Modifies order sizes based on market conditions and inventory ratio
- **Market Regime Classification**: Detects current market conditions (trending, volatile, ranging)
- **Score-Based Decision Making**: Uses a weighted scoring system to determine trading actions
- **Status Dashboard**: Provides comprehensive status display with indicator scores and regime information

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/adaptive-market-making.git
   cd adaptive-market-making
   ```

2. Set up environment (requires Python 3.7+ and conda):
   ```
   conda create -n hummingbot python=3.8
   conda activate hummingbot
   pip install -r requirements.txt
   ```

3. Copy the configuration files to your Hummingbot installation:
   ```
   cp -r hummingbot/* ~/hummingbot/
   ```

## Usage

1. Start Hummingbot:
   ```
   cd ~/hummingbot
   ./start.sh
   ```

2. Import the configuration file:
   ```
   import adaptive_market_making_config
   ```

3. Create a configuration file:
   ```
   create --script-config adaptive_market_making_config
   ```

4. Start the strategy:
   ```
   start --script adaptive_market_making --conf [CONFIG_FILE_NAME]
   ```

5. Monitor the strategy using the `status` command to see indicator scores, market regime, and active orders.

## Configuration Parameters

### Exchange and Market Parameters
- `connector_name`: Exchange to use (e.g., "binance_paper_trade")
- `trading_pair`: Trading pair (e.g., "ETH-USDT")

### Basic Market Making Parameters
- `order_amount`: Base order amount (denominated in base asset)
- `min_spread`: Minimum spread (e.g., 0.001 for 0.1%)
- `max_spread`: Maximum spread (e.g., 0.01 for 1%)
- `order_refresh_time`: How often orders are refreshed (in seconds)
- `max_order_age`: Maximum order age (in seconds)

### Technical Indicator Parameters
- `rsi_length`: Period length for RSI calculation
- `rsi_overbought`: RSI threshold for overbought condition
- `rsi_oversold`: RSI threshold for oversold condition
- `ema_short`: Short EMA period
- `ema_long`: Long EMA period
- `bb_length`: Period length for Bollinger Bands
- `bb_std`: Standard deviation multiplier for Bollinger Bands

### Risk Management Parameters
- `target_inventory_ratio`: Target ratio of base to quote assets
- `min_order_amount`: Minimum order size
- `volatility_adjustment`: Multiplier for volatility-based spread adjustments
- `trailing_stop_pct`: Percentage for trailing stop orders
- `signal_threshold`: Minimum signal score (0-100) required to place orders

## How It Works

### Market Data Collection
The strategy collects and maintains price and volume data from the market, building a historical dataset for technical analysis.

### Technical Indicator Calculation
Multiple technical indicators are calculated from the collected data:
- **RSI**: Measures overbought/oversold conditions
- **MACD**: Identifies trend direction and strength
- **EMA**: Provides trend confirmation
- **Bollinger Bands**: Measures volatility and potential reversal points

### Scoring System
Each indicator contributes to a total score (0-100) with the following weights:
- RSI: 20%
- MACD: 25%
- EMA: 20%
- Bollinger Bands: 35%

### Market Regime Detection
The strategy classifies the current market into one of seven regimes:
- **Trending Bullish**: Strong upward movement
- **Trending Bearish**: Strong downward movement
- **Trending Volatile Bullish**: Strong uptrend with high volatility
- **Trending Volatile Bearish**: Strong downtrend with high volatility
- **Volatile**: High uncertainty without clear direction
- **Ranging**: Oscillation between support and resistance
- **Neutral**: Low volatility without clear direction

### Adaptive Parameter Adjustment
Based on the technical scores and market regime:
- Spreads widen during volatile or uncertain conditions
- Spreads tighten during strong trends
- Order sizes adjust based on inventory position and market direction
- Orders are only placed when signal strength exceeds the threshold

## Dependencies

- Python 3.7+
- NumPy
- Pandas
- Hummingbot 1.4.0+

## License

Apache License 2.0

## Disclaimer

This strategy is provided for educational and research purposes only. Use at your own risk. Always test thoroughly on paper trading before using with real funds.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.