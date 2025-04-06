# Precision Trading Strategy

A sophisticated algorithmic trading strategy that combines multiple weighted indicators, multi-timeframe analysis, and advanced trap detection for high-probability trading signals in crypto markets.

## Files in this Package

- `precision_trading.py` - The main strategy implementation
- `precision_trading_config.py` - Configuration parameters for the strategy (located in `~/hummingbot/hummingbot/conf/strategies/`)

## Portable Installation

This strategy implementation has been made portable, meaning it can work even if you move the outer hummingbot folder to a different location. The strategy uses relative paths and imports that adapt to wherever the hummingbot installation is located.

1. Ensure you have properly installed Hummingbot from source
2. Verify the script files are in the correct relative locations:
   ```
   <your-hummingbot-location>/hummingbot/scripts/precision_trading.py
   <your-hummingbot-location>/hummingbot/conf/strategies/precision_trading_config.py
   ```

## Usage

1. Start Hummingbot (from any location where the hummingbot installation is accessible):
   ```
   cd <your-hummingbot-location>/hummingbot
   conda activate hummingbot
   bin/hummingbot.py
   ```

2. Import the configuration file:
   ```
   import precision_trading_config
   ```

3. Create a configuration file (you'll be prompted for parameters):
   ```
   create --script-config precision_trading_config
   ```

4. Start the strategy:
   ```
   start --script precision_trading.py --conf [config_file_name]
   ```
   Replace `[config_file_name]` with the name you provided when creating the config file.

## Moving Hummingbot Installation

If you need to move your Hummingbot installation to a different location:

1. Move the entire hummingbot directory to the new location
2. No changes to configuration files are needed - all paths are relative
3. Start Hummingbot from the new location following the steps in the Usage section above

## Key Features

- **Weighted Indicator Analysis**: Combines multiple technical indicators with dynamic weighting based on market conditions
- **Multi-Timeframe Analysis**: Analyzes price action across different timeframes for confirmation
- **Dynamic Position Sizing**: Adjusts position size based on risk level and market conditions
- **Market Regime Detection**: Identifies current market structure (trending, ranging, volatile)
- **Bull/Bear Trap Detection**: Identifies potential trap setups to avoid false breakouts
- **Score-Based Signal Generation**: Uses a weighted scoring system to generate high-probability trading signals

## Configuration Parameters

### Exchange and Market Parameters
- `exchange`: Exchange to use (e.g., "binance_perpetual")
- `trading_pair`: Trading pair (e.g., "BTC-USDT")

### Strategy Parameters
- `risk_level`: Risk profile - "high", "medium", or "low"
- `time_horizon`: Trading time horizon - "short", "medium", or "long"
- `position_size_pct`: Percentage of available balance for each trade
- `leverage`: Leverage to use on supported exchanges

### Technical Indicator Parameters
- `rsi_length`: Period length for RSI calculation
- `macd_fast`, `macd_slow`, `macd_signal`: MACD parameters
- `ema_short_len`, `ema_long_len`: EMA period lengths
- `bb_length`, `bb_std`: Bollinger Bands parameters
- `atr_length`: ATR period length
- `sr_window`: Window for finding swing highs/lows for support/resistance
- `sr_group_threshold`: Threshold for grouping support/resistance levels

### Execution Parameters
- `update_interval`: How often to fetch data and recalculate (in seconds)
- `secondary_tf_update_multiplier`: Multiplier for secondary timeframe updates
- `long_tf_update_multiplier`: Multiplier for long timeframe updates

## Monitoring Strategy Performance

Use the Hummingbot `status` command to see the current state of the strategy, including:
- Current market regime and confidence level
- Total signal score
- Support and resistance levels
- Active positions and orders
- Current P&L

## Requirements

- Hummingbot version 1.4.0 or later
- Required Python packages: `numpy`, `pandas`, `scipy` 