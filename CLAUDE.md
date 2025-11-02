# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About Hummingbot

Hummingbot is an open-source framework for building and deploying automated trading bots across centralized and decentralized exchanges. The codebase includes:
- Support for 40+ exchange connectors (CEX spot/perpetual, DEX CLOB, AMM DEX)
- Multiple strategy frameworks (legacy strategies, V2 strategies with controllers)
- Gateway middleware for DEX/blockchain integration
- CLI-based client with command system

## Development Setup

### Environment Setup

**Prerequisites**: Anaconda/Miniconda with Python 3.10+

```bash
# Install dependencies and create conda environment
./install                    # Standard installation
./install --dydx            # With dYdX support (alternative environment)

# Activate environment
conda activate hummingbot

# Compile Cython extensions
./compile                   # Runs: python setup.py build_ext --inplace

# Clean compiled files
./clean                     # Removes .cpp, .so, .pyd files and build artifacts
```

### Running Hummingbot

```bash
# Start Hummingbot CLI
./start                                          # Interactive mode
./start -p <password>                            # With password
./start -f <strategy.yml>                        # With strategy config
./start -f <script.py>                          # With Python script
./start -f <script.py> -c <config.yml>          # Script with config

# Or use the entry point directly
./bin/hummingbot_quickstart.py -p <password> -f <file>
```

### Docker Setup

```bash
# Standard Hummingbot
docker compose up -d
docker attach hummingbot

# With Gateway (for DEX connectors)
# Uncomment gateway service in docker-compose.yml, then:
docker compose up -d
```

## Code Quality & Pre-commit Hooks

**IMPORTANT**: All code must pass pre-commit hooks before committing.

### Pre-commit Checks

Hummingbot runs these checks automatically on every commit:
- **flake8**: Python linting (max line length: 120)
- **autopep8**: Auto-formatting to PEP 8 standards
- **isort**: Import sorting and organization
- **Security checks**: Detects private keys and wallet keys

### Quick Reference for Writing Code

1. **Import Order** (for scripts in `scripts/` directory):
   ```python
   import sys
   from pathlib import Path

   # Add hummingbot to path
   sys.path.insert(0, str(Path(__file__).parent.parent))

   # Add noqa: E402 for imports after path manipulation
   from hummingbot import data_path  # noqa: E402
   from reporting.database import DatabaseManager  # noqa: E402
   ```

2. **Utility Script Structure**:
   ```python
   def main():
       """All executable code goes here"""
       # Your code

   if __name__ == "__main__":
       main()
   ```

3. **Common Issues to Avoid**:
   - ❌ `print(f"No variables")` → ✅ `print("No variables")`  (F541: unnecessary f-string)
   - ❌ `result=x/1000` → ✅ `result = x / 1000`  (E226: missing whitespace)
   - ❌ Lines > 120 characters → ✅ Break into multiple lines  (E501)

### Running Checks Manually

```bash
# Check specific file
conda run -n hummingbot flake8 path/to/file.py

# Auto-fix formatting
autopep8 --in-place --max-line-length 120 path/to/file.py
isort path/to/file.py

# Run all pre-commit hooks
pre-commit run --all-files
```

**See `PYTHON_CODE_QUALITY_GUIDE.md` for complete guidelines and examples.**

## Testing

### Run Tests

```bash
# Run all tests (80% coverage required for PRs)
make test

# Run specific test file
pytest test/path/to/test_file.py

# Run specific test function
pytest test/path/to/test_file.py::test_function_name

# Calculate diff coverage for development branch
make development-diff-cover

# Generate coverage reports
make run_coverage          # Runs tests + generates report
make report_coverage       # Just generates report from existing data
```

### Known Test Exclusions

The following tests are currently excluded (see Makefile):
- `test/hummingbot/connector/derivative/dydx_v4_perpetual/`
- `test/hummingbot/remote_iface/`
- `test/connector/utilities/oms_connector/`
- `test/hummingbot/strategy/amm_arb/`
- `test/hummingbot/strategy/cross_exchange_market_making/`

## Code Architecture

### Core System Architecture

**Cython/C++ Performance Layer**: Core trading components use Cython (.pyx files) for performance:
- `connector_base.pyx` - Base connector functionality
- `exchange_base.pyx` - CEX exchange base
- `strategy_base.pyx` - Strategy execution engine
- `clock.pyx`, `network_iterator.pyx` - Timing and async loops
- Compile changes with `./compile`

**Event-Driven System**: The framework uses a pub/sub event system (`core/pubsub.pyx`) with a clock-based timing system (`core/clock.pyx`) that drives all connectors and strategies via time/network iterators.

**Connector Manager**: `core/connector_manager.py` handles lifecycle management of exchange connections. All connectors inherit from `connector_base.pyx` (or `exchange_base.pyx` for CEX).

### Connector Architecture

Connectors are organized by type:

**CLOB CEX** (`connector/exchange/`):
- Central limit order book centralized exchanges
- Examples: `binance/`, `kucoin/`, `okx/`, `bybit/`
- Inherit from `ExchangePyBase` → `ExchangeBase` (Cython)

**CLOB CEX Perpetual** (`connector/derivative/`):
- Perpetual futures on centralized exchanges
- Examples: `binance_perpetual/`, `kucoin_perpetual/`
- Inherit from `PerpetualDerivativePyBase`

**CLOB DEX** (`connector/exchange/` and `connector/derivative/`):
- On-chain limit order book DEXs
- Examples: `hyperliquid/`, `vertex/`, `dexalot/`, `injective_v2/`
- Use `dydx_v4_perpetual` for dYdX v4

**AMM DEX** (`connector/gateway/`):
- Use Gateway middleware (TypeScript API) for DEX connections
- `gateway_base.py` - Base for all Gateway connectors
- `gateway_lp.py` - Liquidity provision
- `gateway_swap.py` - Token swaps
- Examples accessed via Gateway: Uniswap, PancakeSwap, Jupiter, Meteora

### Strategy Architecture

**Legacy Strategies** (`strategy/`):
- Inherit from `StrategyBase` (Cython class)
- Examples: `pure_market_making/`, `cross_exchange_market_making/`, `avellaneda_market_making/`
- Use `ScriptStrategyBase` for script-based strategies (in `scripts/`)

**Strategy V2** (`strategy_v2/`):
- Modern controller-based architecture
- `runnable_base.py` - Base class with async control loop pattern
- `controllers/controller_base.py` - Base for all controllers
- `controllers/market_making_controller_base.py` - Market making logic
- `controllers/directional_trading_controller_base.py` - Directional trading
- `executors/` - Modular execution components (position executors, arbitrage, DCA, TWAP, etc.)
- `models/` - Data models (executors, order levels)
- `backtesting/` - Backtesting framework

**Scripts** (`scripts/`):
- Custom Python strategies placed here
- Inherit from `ScriptStrategyBase`
- Can use V2 controllers (see `v2_with_controllers.py`)
- Loaded with: `./start -f script_name.py`

**Controllers** (root `controllers/`):
- Reusable strategy modules imported by scripts
- `directional_trading/`, `market_making/`, `generic/`

### Client/UI Layer

**Client** (`client/`):
- `hummingbot_application.py` - Main application class
- `command/` - CLI command implementations (start, stop, status, config, etc.)
- `config/` - Configuration and secrets management
- `ui/` - Terminal UI components
- `settings.py` - Global settings and paths

**Entry Point**: `bin/hummingbot_quickstart.py` - Main script that initializes and launches the application

### Core Utilities

- `core/data_type/` - Order books, trade data, common types
- `core/event/` - Event definitions and handling
- `core/utils/` - Async utilities, trading calculations
- `core/rate_oracle/` - Price feed oracle
- `core/api_throttler/` - Rate limiting for API calls
- `core/web_assistant/` - HTTP/WebSocket helpers
- `core/gateway/` - Gateway communication layer

### Data and Configuration

- `data/` - Runtime data (databases, order history)
- `conf/` - Configuration files (strategies, client settings)
- `logs/` - Application logs
- `templates/` - Strategy config templates

## Development Workflow

### Branch Strategy

- **Base branch**: `development` (NOT master)
- **Main branch**: `master` (for PRs and releases)
- Create feature branches from `development`:
  - `feat/feature-name` - New features
  - `fix/bug-name` - Bug fixes
  - `refactor/refactor-name` - Refactoring
  - `doc/doc-name` - Documentation

### Commit Convention

Prefix commits with type:
- `(feat)` - New feature
- `(fix)` - Bug fix
- `(refactor)` - Code refactoring
- `(cleanup)` - Code cleanup
- `(doc)` - Documentation

Example: `(feat) add Jupiter DEX connector support`

### Pre-commit Hooks

Pre-commit hooks run automatically on commit:
- `flake8` - Linting (.py, .pyx, .pxd files)
- `autopep8` - Auto-formatting (max line length 120)
- `isort` - Import sorting
- `trailing-whitespace`, `end-of-file-fixer`
- `detect-private-key`, `detect-wallet-private-key` - Security checks

Install hooks: `pre-commit install` (done automatically by `./install`)

### Pull Request Process

1. Create feature branch from `development`
2. Make changes and commit
3. Rebase with upstream: `git pull --rebase upstream development`
4. Ensure tests pass: `make test`
5. Check diff coverage: `make development-diff-cover` (80% minimum)
6. Push and create PR to `development` branch
7. Check "Allow edits by maintainers"
8. Address review feedback

### Adding New Connectors

- See CONTRIBUTING.md for full guidelines
- Submit a New Connector Proposal (requires HBOT tokens)
- Connectors should follow the base class patterns:
  - CEX spot: Inherit from `ExchangePyBase`
  - CEX perpetual: Inherit from `PerpetualDerivativePyBase`
  - DEX via Gateway: Extend Gateway middleware (separate repo)

## Common Tasks

### Add a New Strategy Script

```bash
# Create script in scripts/ directory
scripts/my_strategy.py

# Script should inherit from ScriptStrategyBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# Run with:
./start -f my_strategy.py
```

### Add a New V2 Controller

```bash
# Create in controllers/ directory
controllers/<category>/<controller_name>.py

# Import RunnableBase or controller base classes
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase

# Use in scripts by importing and initializing
```

### Modify Exchange Connector

```bash
# 1. Find connector in hummingbot/connector/exchange/<exchange_name>/
# 2. Main connector file usually: <exchange_name>_exchange.py
# 3. After changes, run tests:
pytest test/hummingbot/connector/exchange/<exchange_name>/

# 4. If modifying Cython (.pyx), recompile:
./compile
```

### Debug with VS Code/Cursor

See CURSOR_VSCODE_SETUP.md for full IDE configuration including:
- Python interpreter selection (conda hummingbot environment)
- Test discovery setup
- Debug configurations
- Required `.vscode/settings.json` and `.vscode/launch.json`

### Update Dependencies

```bash
# Edit setup/environment.yml (conda packages)
# Edit setup/pip_packages.txt (pip packages)

# Reinstall
./uninstall
./install
```

## Important Notes

- **Gateway Required**: For AMM DEX connectors (Uniswap, PancakeSwap, Jupiter, etc.), you must run Gateway middleware. See README.md Docker setup section.
- **Cython Development**: Changes to .pyx files require `./compile` to take effect
- **Data Paths**: Runtime data stored in `data/`, logs in `logs/`, configs in `conf/`
- **Development Mode**: Bot detects dev mode when not on master branch or when built from source
- **Version**: Check `hummingbot/VERSION` for current version
