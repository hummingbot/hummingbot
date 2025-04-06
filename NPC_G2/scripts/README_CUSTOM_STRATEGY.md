# Advanced Market Making Strategy for BITS GOA Assignment

This custom market making strategy combines volatility indicators, trend analysis, and a risk management framework to create an intelligent trading bot that adapts to market conditions.

## Strategy Overview

The strategy combines several advanced features:

1. **Dynamic Volatility-Based Spreads**: Adjusts spreads based on market volatility using Normalized Average True Range (NATR)
2. **Trend Analysis**: Uses multiple indicators (RSI, EMAs, MACD) to detect market trends and adjust pricing accordingly
3. **Inventory Management**: Automatically balances inventory towards a target ratio
4. **Risk Framework**: Implements stop-loss and take-profit mechanisms to protect capital
5. **Dynamic Order Sizing**: Adjusts order sizes based on market volatility and inventory position

## Key Components

### Volatility Indicators
- Uses NATR (Normalized Average True Range) to measure market volatility
- Dynamically adjusts bid and ask spreads in response to changing volatility
- Reduces order sizes during high volatility periods

### Trend Analysis
- RSI (Relative Strength Index) to identify overbought/oversold conditions
- Multiple EMA (Exponential Moving Average) periods for trend confirmation
- MACD (Moving Average Convergence Divergence) for additional trend signals
- Contrarian approach: buys during downtrends, sells during uptrends

### Risk Management Framework
- Target inventory ratio with dynamic rebalancing
- Stop-loss triggers to prevent significant losses
- Take-profit mechanisms to secure gains
- Maximum position limits to control exposure
- Order size adjustment based on volatility and inventory position

## Configuration Parameters

The strategy offers extensive configuration options:

- **Spread Parameters**: Base spreads and volatility scalar adjustments
- **Trend Analysis**: Windows for RSI and EMAs, overbought/oversold thresholds
- **Inventory Management**: Target ratio and adjustment factors
- **Risk Parameters**: Stop-loss percentage, take-profit targets, max position sizes

## Performance Considerations

This strategy is designed to:

- Maintain a balanced inventory while capitalizing on short-term price movements
- Protect capital during adverse market conditions
- Adapt to changing market volatility
- Provide liquidity while managing risk

## Usage Instructions

1. Set up your Hummingbot instance
2. Configure the strategy parameters for your desired trading pair
3. Start the script using the Hummingbot interface
4. Monitor performance through the detailed status display

## Future Improvements

Potential enhancements:
- Machine learning integration for parameter optimization
- Additional risk metrics like Value at Risk (VaR)
- Adaptive parameter tuning based on market regime detection
- Portfolio-level risk management across multiple trading pairs
