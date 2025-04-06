# Adaptive Market Making Strategy

An advanced market making strategy using technical indicators and adaptive parameters for optimal performance.

## Features

- Technical indicator-based spread adjustment (RSI, MACD, EMA, Bollinger Bands)
- Adaptive inventory management
- Risk management with position limits and trailing stops
- Advanced performance metrics including Sharpe ratio

## Backtesting

To backtest the strategy against historical data:

1. Install Hummingbot
2. Place the `main.py` file in your Hummingbot scripts directory
3. Use the provided `backtest_config.yml` file:

```bash
hummingbot backtest --config backtest_config.yml --strategy adaptive_market_making
```

This will run a backtest on 1 year of ETH-BTC data from September 2022 to September 2023.

## Paper Trading

To run the strategy in paper trading mode:

1. Start Hummingbot
2. Import the strategy:
   ```
   import_strategy adaptive_market_making
   ```
3. Create your configuration:
   ```
   create_config paper_trade_config.yml
   ```
   Or use the provided `paper_trade_config.yml` file.
4. Start the strategy:
   ```
   start --config paper_trade_config.yml
   ```

## Important Commands

- `status` - Check the current status and performance metrics
- `history` - View detailed trade history and PnL
- `stop` - Stop the strategy
- `exit` - Exit Hummingbot

## Performance Analysis

Use the `history` command to see detailed performance metrics:
- Total P&L
- Return %
- Comparison to HODL strategy
- Win rate
- Sharpe ratio

## Adjusting Parameters

Key parameters to adjust for optimization:
- `min_spread` / `max_spread`: Control bid-ask spread
- `order_amount`: Size of each order
- `max_inventory_ratio` / `min_inventory_ratio`: Control inventory balance
- `volatility_adjustment`: How much to adjust spreads based on market volatility
- `trailing_stop_pct`: Risk management stop-loss percentage

## Strategy Overview

This strategy improves upon the basic Pure Market Making (PMM) strategy by:

1. **Technical Indicator Integration**:
   - RSI (Relative Strength Index)
   - MACD (Moving Average Convergence Divergence)
   - EMA (Exponential Moving Average)
   - Bollinger Bands
   - Volume analysis

2. **Dynamic Spread Adjustment**:
   - Spreads widen during high volatility or bearish conditions
   - Spreads tighten during low volatility or bullish conditions

3. **Inventory Management**:
   - Adjusts order sizes based on current inventory ratio
   - Prevents excessive accumulation of base or quote assets

4. **Multiple Timeframe Analysis**:
   - Uses 1-hour candles for trend identification
   - Analyzes different market phases (trending, volatile, sideways)

## Installation

1. Make sure you have Hummingbot installed (follow the instructions at https://hummingbot.org/installation/)
2. Copy `main.py` to `hummingbot/strategy/adaptive_market_making/`
3. Create an empty `__init__.py` file in the same directory
4. Add the strategy to `hummingbot/strategy/__init__.py` by adding:
   ```python
   from hummingbot.strategy.adaptive_market_making.main import AdaptiveMarketMakingStrategy
   ```

## Configuration

1. Copy the `adaptive_market_making_config.yml` file to your Hummingbot config directory
2. Modify the parameters as needed:
   - Exchange and trading pair
   - Order sizes and spreads
   - Technical indicator settings
   - Risk management parameters

## Usage

To start the strategy:

1. Start Hummingbot
2. In the Hummingbot CLI, type:
   ```
   import adaptive_market_making_config
   start
   ```

## Strategy Parameters

| Parameter | Description |
|-----------|-------------|
| `order_amount` | Base order amount |
| `min_spread` | Minimum bid-ask spread |
| `max_spread` | Maximum bid-ask spread |
| `order_refresh_time` | Time between order updates (seconds) |
| `max_inventory_ratio` | Maximum inventory ratio (0 to 1) |
| `volatility_adjustment` | Volatility impact multiplier |

## Risk Management

- The strategy adapts to changing market conditions by modifying spread and inventory targets
- During bearish conditions, spreads widen and maximum inventory levels decrease
- During bullish conditions, spreads tighten and maximum inventory levels increase

## Performance Metrics

Monitor the strategy's performance through the status command, which shows:
- Current indicator scores
- Adaptive spread calculation
- Inventory balance
- Active orders

## Author

This strategy was created for the BITS GOA take-home assignment.

## License

This project is licensed under the MIT License - see the LICENSE file for details 