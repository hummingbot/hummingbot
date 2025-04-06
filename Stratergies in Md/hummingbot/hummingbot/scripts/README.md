# Adaptive Market Making Strategy

A sophisticated market making strategy that combines technical indicators, market regime detection, and risk management to dynamically adjust market making parameters based on current market conditions.

## Files in this Package

- `adaptive_market_making.py` - The main strategy implementation
- `adaptive_market_making_config.py` - Configuration parameters for the strategy

## Installation

1. Ensure you have properly installed Hummingbot from source as directed
2. Verify the script files are in the correct location:
   ```
   ~/hummingbot/hummingbot/scripts/
   ```

## Usage

1. Start Hummingbot:
   ```
   cd ~/hummingbot/hummingbot
   conda activate hummingbot
   bin/hummingbot.py
   ```

2. Import the configuration file:
   ```
   import adaptive_market_making_config
   ```

3. Create a configuration file (you'll be prompted for parameters):
   ```
   create --script-config adaptive_market_making_config
   ```

4. Start the strategy:
   ```
   start --script adaptive_market_making.py --conf [config_file_name]
   ```
   Replace `[config_file_name]` with the name you provided when creating the config file.

## Key Features

- **Dynamic Spread Calculation**: Adjusts bid/ask spreads based on market volatility, technical indicators, and inventory position
- **Smart Order Sizing**: Modifies order sizes based on market conditions and inventory ratio
- **Market Regime Classification**: Detects current market conditions (trending, volatile, ranging)
- **Score-Based Decision Making**: Uses a weighted scoring system to determine trading actions
- **Trailing Stop Protection**: Implements trailing stops for risk management

## Configuration Parameters

### Exchange and Market Parameters
- `connector_name`: Exchange to use (e.g., "binance_paper_trade")
- `trading_pair`: Trading pair (e.g., "ETH-USDT")

### Basic Market Making Parameters
- `order_amount`: Base order amount (denominated in base asset)
- `min_spread`: Minimum spread (e.g., 0.1 for 0.1%)
- `max_spread`: Maximum spread (e.g., 1.0 for 1%)
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

## Monitoring Strategy Performance

Use the Hummingbot `status` command to see the current state of the strategy, including:
- Current signal score
- Market regime
- Active orders
- Inventory balance

## Requirements

- Hummingbot version 1.4.0 or later
- Required Python packages (automatically installed with Hummingbot):
  - NumPy
  - Pandas
  - pandas-ta

## Disclaimer

This strategy is provided for educational and research purposes only. Use at your own risk. Always test thoroughly on paper trading before using with real funds. 