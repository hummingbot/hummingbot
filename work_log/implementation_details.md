# Custom Adaptive Market Making Strategy

## Overview

This document details the implementation of our Custom Adaptive Market Making strategy for the BITS GOA assignment. The strategy combines multiple technical indicators, volatility analysis, trend detection, and sophisticated risk management to create an adaptive market making strategy for cryptocurrency trading.

## Implementation Approach

After reviewing the available scripts in the Hummingbot repository, we selected the following as reference points:

1. `custom_adaptive_market_making.py` - Provides the core structure with volatility-based dynamic spreads and market regime detection
2. `institutional_crypto_framework.py` - Advanced risk management features
3. `precision_market_making.py` - Technical indicator integration
4. `precision_trading_strategy.py` - Multi-timeframe analysis

Instead of creating a new script from scratch, we leveraged the existing `custom_adaptive_market_making.py` script, which already includes many of the features required for this assignment. We enhanced it by creating a custom configuration file that allows for easy parameter tuning.

## Strategy Features

### 1. Technical Indicators

The strategy uses a combination of technical indicators to analyze market conditions:

- **RSI (Relative Strength Index)** - Measures overbought/oversold conditions
- **EMA (Exponential Moving Average)** - Multiple periods (short, medium, long) for trend confirmation
- **MACD (Moving Average Convergence/Divergence)** - Trend direction and strength
- **Bollinger Bands** - Volatility and potential reversal points
- **ATR (Average True Range)** - Volatility measurement for dynamic spread calculation

### 2. Market Regime Detection

The strategy classifies the current market into one of four regimes:

- **Trending** - Strong directional movement (bullish or bearish)
- **Volatile** - High price fluctuations without clear direction
- **Ranging** - Price oscillation between support and resistance
- **Normal** - Moderate volatility with no clear trend

The regime is determined by analyzing technical indicators and volatility measurements, with each regime having a confidence score.

### 3. Dynamic Parameter Adjustment

Based on the detected market regime and conditions, the strategy dynamically adjusts:

- **Bid/Ask Spreads** - Widens during high volatility, narrows during low volatility
- **Order Sizes** - Adjusts based on inventory imbalance and market direction
- **Order Placement** - Considers support/resistance levels for optimal positioning

### 4. Risk Management

The strategy incorporates sophisticated risk management:

- **Inventory Management** - Maintains a target ratio of base to quote asset
- **Position Sizing** - Adjusts order sizes based on volatility and market regime
- **Stop-Loss & Take-Profit** - Implements trailing stops and profit targets
- **Exposure Limits** - Controls maximum position size based on portfolio percentage

## Configuration

The strategy is highly configurable through a YAML configuration file (`conf_custom_adaptive_mm.yml`), allowing for easy parameter tuning without modifying the code. Key configuration parameters include:

- Basic trading parameters (order amount, refresh time, spreads)
- Technical indicator parameters (lengths, thresholds)
- Volatility parameters (multipliers, thresholds)
- Risk management parameters (inventory targets, position limits)
- Market regime detection parameters
- Indicator weights for different market regimes

## Usage

To use the strategy:

1. Ensure the Docker container is running: `docker-compose up -d`
2. Connect to the Hummingbot container: `docker exec -it hummingbot /bin/bash`
3. Inside the container, start Hummingbot: `./bin/hummingbot.py`
4. Start the strategy with the configuration file:
   ```
   start --script custom_adaptive_market_making --conf conf_custom_adaptive_mm.yml
   ```

## Performance Monitoring

The strategy includes a comprehensive status display showing:

- Current market regime and confidence
- Technical indicator values and signals
- Current spreads and order sizes
- Inventory management status
- Active orders and recent trades

This allows for easy monitoring of the strategy's performance and decision-making process.

## Advantages Over Basic PMM

Compared to the basic Pure Market Making strategy, our Custom Adaptive Market Making strategy offers:

1. **Adaptive Behavior** - Adjusts to changing market conditions rather than using fixed parameters
2. **Risk Management** - Sophisticated inventory control and position sizing
3. **Technical Analysis** - Uses multiple indicators for more accurate market analysis
4. **Market Regime Detection** - Tailors strategy to specific market conditions
5. **Support/Resistance Awareness** - Places orders at optimal price levels 