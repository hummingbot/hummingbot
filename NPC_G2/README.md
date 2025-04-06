# Adaptive Market Making Strategy

An advanced market making strategy using technical indicators and adaptive parameters for optimal performance.

## Repository Organization

- **src/** - Main source code
  - **src/strategies/** - Strategy implementations
  - **src/models/** - Machine learning models
  - **src/utils/** - Utility functions
  - **src/backtest/** - Backtesting framework
- **config/** - Configuration files for different modes
- **docs/** - Documentation files
  - **docs/project/** - Project requirements and specifications
- **examples/** - Example code and usage patterns

## Features

- Technical indicator-based spread adjustment (RSI, MACD, EMA, Bollinger Bands)
- Adaptive inventory management
- Risk management with position limits and trailing stops
- Advanced performance metrics including Sharpe ratio
- Machine learning enhanced trading strategies

## Getting Started

### Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Running the Strategy

#### Backtesting

To backtest the strategy against historical data:

```bash
python src/main.py --config config/backtest_config.yml --strategy adaptive_market_making
```

#### Paper Trading

To run the strategy in paper trading mode:

```bash
python src/main.py --config config/paper_trade_config.yml
```

## Configuration

Configuration files are stored in the `config/` directory:

- `backtest_config.yml` - Backtesting configuration
- `paper_trade_config.yml` - Paper trading configuration
- `adaptive_market_making_config.yml` - Strategy-specific configuration
- `ML.yaml` - Machine learning model configuration

## Documentation

See the `docs/` directory for detailed documentation:

- `strategy_explanation.md` - Details on the adaptive market making strategy
- `ml_strategy_explanation.md` - Machine learning strategy documentation

## Project Status

This project contains two implementations:
1. A traditional adaptive market making strategy (src/main.py)
2. A machine learning enhanced strategy (src/main2.py, src/models/*)

## License

This project is licensed under the MIT License - see the LICENSE file for details 