# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hummingbot is an open-source Python framework for building automated crypto trading bots. It supports spot and derivative exchanges (CEX and DEX via Gateway), with two strategy frameworks (V1 scripts and V2 controllers/executors).

## Common Commands

### Build & Install
```bash
make install          # Set up conda environment with all dependencies
```

### Running
```bash
make run              # Run hummingbot CLI (quickstart)
bin/hummingbot.py     # Direct entry point
```

### Testing
```bash
make test             # Full test suite (pytest with coverage)
pytest test/path/to/test_file.py                        # Single test file
pytest test/path/to/test_file.py::TestClass::test_method  # Single test method
```
CI requires 80% coverage on new/changed code (enforced via diff-cover).

### Linting & Formatting
```bash
pre-commit run --all-files   # Run all pre-commit hooks
```
- **flake8**: max-line-length=120, config in `.flake8`
- **black**: line-length=120
- **isort**: line-length=120, trailing commas, force-grid-wrap

### Docker
```bash
make build    # Build Docker image
make setup    # Interactive docker-compose setup
make deploy   # Deploy containers
make down     # Stop containers
```

## Architecture

### Strategy Frameworks

**V1 (Script Strategies):** Simpler approach. Subclass `ScriptStrategyBase`, override `on_tick()`, define `markets` class variable. Config extends `ScriptConfigBase`. Located in `scripts/`.

**V2 (Controller + Executor):** More modular. `ControllerBase` manages strategy logic, delegates order execution to typed `ExecutorBase` subclasses (XEMM, DCA, Grid, etc.). Config extends `ControllerConfigBase`. Controllers in `controllers/`, executors in `hummingbot/strategy_v2/executors/`.

The V2 framework is orchestrated by `StrategyV2Base` which manages controllers and uses `ExecutorOrchestrator` to coordinate executors.

### Connector System

Exchange connectors live under `hummingbot/connector/` with three categories:
- `exchange/` — Spot connectors (Binance, Kraken, KuCoin, etc.)
- `derivative/` — Perpetual/futures connectors (binance_perpetual, hyperliquid_perpetual, etc.)
- `gateway/` — DEX connectors via Gateway middleware

Each connector inherits from `ExchangePyBase` (spot) or `PerpetualDerivativePyBase` (derivatives), which both extend `ConnectorBase` (Cython). Connectors use:
- An `Auth` class for authentication
- `APIOrderBookDataSource` for market data (REST + WebSocket)
- `UserStreamDataSource` for account updates
- `WebAssistantsFactory` for HTTP/WS with rate limiting (`AsyncThrottler`)

### Core Infrastructure

- **`hummingbot/core/data_type/`** — OrderBook, InFlightOrder, LimitOrder, TradeFee, etc.
- **`hummingbot/core/event/`** — Pub-sub event system (OrderFilledEvent, BuyOrderCreatedEvent, etc.)
- **`hummingbot/core/api_throttler/`** — Rate limiting for exchange APIs
- **`hummingbot/core/web_assistant/`** — REST and WebSocket client wrappers
- **`hummingbot/data_feed/`** — Candles feeds and market data providers

### Configuration

Uses Pydantic v2 BaseModel for all configs. Client config in `hummingbot/client/config/client_config_map.py`. Exchange connector configs use `json_schema_extra` for interactive prompts. Config files are YAML in `conf/`.

### Key Enums & Types

`hummingbot/core/data_type/common.py` defines `OrderType`, `TradeType`, `PriceType`, `PositionAction`, `PositionMode`.

## Testing Patterns

- Async tests extend `IsolatedAsyncioWrapperTestCase` from `test/isolated_asyncio_wrapper_test_case.py`
- Test structure mirrors source: `test/hummingbot/connector/exchange/binance/` tests `hummingbot/connector/exchange/binance/`
- Mock connectors and network responses for unit tests
- Some tests are excluded from CI (dydx_v4, injective_v2, ndax — see Makefile for full ignore list)

## Build System Notes

- Uses Cython (`.pyx`/`.pxd` files) for performance-critical paths like `ConnectorBase`, `OrderBook`
- Setup.py compiles Cython extensions; `setup/environment.yml` defines the conda environment
- Python 3.10.12+ required

## Branch & PR Conventions

Branch naming: `feat/`, `fix/`, `refactor/`, `doc/` prefixes. PRs target `development` branch, which merges to `master` for releases.
