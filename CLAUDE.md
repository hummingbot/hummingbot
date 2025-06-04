# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hummingbot is an open-source framework for building automated trading strategies ("bots") that can trade on both centralized (CEX) and decentralized (DEX) cryptocurrency exchanges. The framework provides connectors to standardize exchange APIs, and allows users to create, backtest, and deploy trading strategies.

## Key Components

1. **Exchange Connectors** - Standardized interfaces to exchanges:
   - `connector/exchange/` - Spot market connectors (CEX)
   - `connector/derivative/` - Perpetual futures connectors
   - `connector/gateway/` - Gateway connectors for DEXs

2. **Strategies** - Trading algorithms:
   - `strategy/` - Contains various strategy implementations
   - `strategy_v2/` - V2 architecture with controllers and executors

3. **Controllers** - Higher-level decision-making components:
   - `controllers/` - Contains various controllers for different trading approaches
   - Can be composed with strategies to customize behavior

4. **Core** - Core infrastructure components:
   - `core/` - Contains clock, event system, order book, data types

5. **Client** - CLI interface:
   - `client/` - Command handlers, config management, UI

## Development Commands

### Environment Setup

```bash
# Create conda environment
conda env create -f setup/environment.yml

# Activate environment
conda activate hummingbot

# Install additional dependencies
pip install -r setup/pip_packages.txt
```

### Building the Project

```bash
# Compile Cython modules
./compile

# Alternatively, for more verbose output:
python setup.py build_ext --inplace
```

### Running Hummingbot

```bash
# Start with default settings
./start

# Start with specific config file
./start -c conf/strategies/your_config.yml

# Start with a script
./start -f scripts/your_script.py
```

### Running Tests

```bash
# Run all tests
python -m pytest test/

# Run specific test module
python -m pytest test/hummingbot/connector/test_connector_base.py

# Run specific test class
python -m pytest test/hummingbot/connector/test_connector_base.py::ConnectorBaseUnitTest

# Run specific test method
python -m pytest test/hummingbot/connector/test_connector_base.py::ConnectorBaseUnitTest::test_in_flight_asset_balances

# Run tests with detailed output
python -m pytest test/hummingbot/connector/test_connector_base.py -v
```

## Architecture Details

### Event-Driven Architecture

The codebase is built around an event-driven architecture, with several key components:

1. **Clock** - Central timing mechanism that issues clock ticks
2. **Events** - System for passing messages between components
3. **Strategy** - Executes trading logic on each clock tick

### Strategy Development

Strategies are built using a combination of:

1. **StrategyBase** - Abstract base class for strategies
2. **Controllers** - Make trading decisions (when/what to trade)
3. **Executors** - Handle order placement and management

For V2 strategies:
- Controllers determine what actions to take
- Executors handle the actual order placement and management
- Market data providers supply pricing information

### Key Patterns

1. **Configuration using Pydantic Models** - Most components use Pydantic classes for configuration
2. **ConnectorBase** - Common interface for all exchange connectors
3. **InFlightOrder** - Tracks orders from creation to completion
4. **MarketTradingPairTuple** - Encapsulates trading pair information

## Code Style Conventions

- Python code follows PEP 8 with 120 character line limits
- Imports are organized with isort
- Black is used for code formatting
- Cython is used for performance-critical components
- C++ is used for core order book functionality

## Project File Structure

- `bin/` - Command-line entry points
- `conf/` - Configuration templates and examples
- `controllers/` - Controller implementations
- `hummingbot/` - Main project code
  - `client/` - CLI application
  - `connector/` - Exchange connectors
  - `core/` - Core systems (clock, events, etc.)
  - `strategy/` - Strategy implementations
  - `strategy_v2/` - V2 strategy architecture
- `scripts/` - Example and utility scripts
- `test/` - Test suite
