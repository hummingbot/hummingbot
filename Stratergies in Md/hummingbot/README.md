# Adaptive Market Making Strategy

## Overview
This project implements an advanced market making strategy for cryptocurrency exchanges using the Hummingbot framework. The strategy incorporates:

- Volatility indicators
- Multi-timeframe trend analysis 
- Comprehensive risk framework for inventory management
- Machine learning integration for market regime detection
- Adaptive parameter adjustment

## Key Features

### Technical Indicator Framework
The strategy employs a weighted scoring system across different timeframes:

| Indicator | Short-Term Weight | Medium-Term Weight | Long-Term Weight |
|-----------|-------------------|--------------------|--------------------|
| RSI | 20 | 15 | 10 |
| MACD | 20 | 25 | 20 |
| EMA50 | 15 | 20 | 25 |
| Bollinger Bands | 15 | 15 | 10 |
| Volume Analysis | 20 | 15 | 15 |
| Support/Resistance | 10 | 10 | 20 |

### Multi-Timeframe Confirmation System
Analyzes multiple timeframes with different weights:
- Primary timeframe (1h): 60% weight - Main decision-making
- Secondary timeframe (15m/4h): 30% weight - Confirmation
- Tertiary timeframe (1d): 10% weight - Trend filtering

### Adaptive Spread Calculation
Dynamically adjusts spreads based on:
- Market volatility (ATR-based)
- Indicator signals
- Market regime
- Inventory position

### Risk Management Framework
- Dynamic position sizing based on market conditions
- Inventory management to maintain target allocation
- Trailing stop implementation
- Volatility-based risk adjustment

### Market Regime Detection
Uses statistical methods to classify market conditions:
- Trending markets
- Ranging/sideways markets
- Volatile markets
- Transitioning markets

## Directory Structure
- `/scripts`: Strategy implementation scripts
  - `/strategies`: Core strategy components
- `/conf`: Configuration files
- `/logs`: Log output
- `/data`: Historical data and model files
- `/notebooks`: Jupyter notebooks for analysis and visualization

## Setup Instructions

### Prerequisites
- Python 3.8+
- Git
- Hummingbot installation

### Installation

1. Clone the Hummingbot repository (if not already done):
```bash
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
```

2. Run the setup script:
```bash
chmod +x setup_adaptive_strategy.sh
./setup_adaptive_strategy.sh
```

3. Configure your strategy:
```
cp conf/adaptive_market_making_config.yml conf/adaptive_market_making_config_custom.yml
# Edit the config file with your preferred parameters
```

4. Run the strategy:
```bash
./scripts/run_strategy.py --config conf/adaptive_market_making_config_custom.yml
```

### Backtesting

To backtest the strategy:

1. Prepare historical data (place in the data directory)
2. Configure backtest parameters:
```
cp conf/backtest_config.yml conf/backtest_config_custom.yml
# Edit the config file with your backtest parameters
```

3. Run the backtest:
```bash
./scripts/backtest.py --config conf/backtest_config_custom.yml
```

## Configuration Parameters

### Basic Market Making
- `connector_name`: Exchange connector
- `trading_pair`: Trading pair
- `order_amount`: Base order size
- `min_spread`: Minimum spread
- `max_spread`: Maximum spread
- `order_refresh_time`: How often to refresh orders

### Technical Indicators
- `rsi_length`: RSI period
- `rsi_overbought`: RSI overbought threshold
- `rsi_oversold`: RSI oversold threshold
- `ema_short`: Fast EMA period
- `ema_long`: Slow EMA period
- `bb_length`: Bollinger Bands period
- `bb_std`: Bollinger Bands standard deviation

### Risk Management
- `max_inventory_ratio`: Maximum inventory ratio
- `min_inventory_ratio`: Minimum inventory ratio
- `volatility_adjustment`: Volatility adjustment factor
- `trailing_stop_pct`: Trailing stop percentage

### Advanced Features
- `use_ml`: Enable machine learning components
- `primary_timeframe`: Main timeframe for analysis
- `secondary_timeframe`: Confirmation timeframe
- `signal_threshold`: Minimum signal strength for order placement

## Requirements
- Python 3.8+
- Hummingbot
- NumPy, Pandas, SciPy
- (Optional) Scikit-learn, PyTorch for ML components

## Credits and References
This strategy is based on the following papers and resources:
- "Optimal Market Making in the Presence of Market Impact" by Cartea, Á., et al.
- "High-Frequency Trading: A Practical Guide to Algorithmic Strategies and Trading Systems" by Aldridge, I.
- Hummingbot documentation and example strategies

## License
This project is licensed under the MIT License - see the LICENSE file for details.
