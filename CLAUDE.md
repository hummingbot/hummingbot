# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Gateway Fee Units for Blockchain Transactions
- **Solana**: `priorityFeePerCU` is in **lamports per compute unit** (not microlamports)
  - Example: 1000 lamports/CU means 1000 lamports per compute unit
  - Gateway returns denomination: "lamports" in EstimateGasResponse
- **Ethereum**: `priorityFeePerCU` is in **Gwei** (not Wei)
  - Example: 50 Gwei means 50 * 10^9 Wei
  - Gateway returns denomination: "gwei" in EstimateGasResponse
  - Gateway routes internally convert Gwei to Wei for ethers.js

## Common Development Commands

### Setup and Installation
```bash
# Clone and setup development environment
./install  # Interactive setup script
conda env create -f setup/environment.yml
conda activate hummingbot

# Manual installation
pip install -r setup/pip_packages.txt
./compile  # Compile Cython modules
```

### Build and Compilation
```bash
# Compile Cython extensions (required after any .pyx/.pxd changes)
./compile

# Clean and rebuild
./clean && ./compile

# Windows compilation
compile.bat
```

### Running Hummingbot
```bash
# Start the bot
./start

# Run with specific config
./start --config-file-name my_config.yml

# Run in headless mode
./start --auto-set-permissions
```

### Testing
```bash
# Run all tests
make test

# Run specific test file
python -m pytest test/hummingbot/connector/test_connector_base.py

# Run with coverage
make test-cov

# Run specific test with verbose output
python -m pytest -v test/hummingbot/strategy/test_strategy_base.py::TestStrategyBase::test_method_name
```

### Code Quality
```bash
# Run linters and formatters
make lint
make format

# Pre-commit hooks
pre-commit install
pre-commit run --all-files

# Type checking
mypy hummingbot/
```

### Docker
```bash
# Build and run with Docker
docker-compose up -d

# Build specific target
docker build -t hummingbot:latest .

# Run with volume mounts
docker run -it -v $(pwd)/conf:/home/hummingbot/conf hummingbot:latest
```

## High-Level Architecture

### Directory Structure
```
hummingbot/
├── client/           # CLI interface and user interaction
│   ├── command/      # Command handlers (balance, config, start, stop, etc.)
│   ├── ui/           # Terminal UI components
│   └── hummingbot_application.py  # Main application class
├── connector/        # Exchange and protocol integrations
│   ├── exchange/     # CEX connectors (Binance, Coinbase, etc.)
│   ├── derivative/   # Perpetual/futures connectors
│   └── gateway/      # Gateway-based DEX connectors
├── strategy/         # Trading strategies (V1)
│   ├── pure_market_making/
│   ├── cross_exchange_market_making/
│   └── script_strategy_base.py  # Base for custom scripts
├── strategy_v2/      # New strategy framework (V2)
│   ├── controllers/  # Strategy controllers
│   ├── executors/    # Order execution management
│   └── models/       # Data models
├── core/            # Core functionality
│   ├── data_type/   # Order books, trades, etc.
│   ├── event/       # Event system
│   └── cpp/         # C++ performance components
├── data_feed/       # Market data providers
└── model/           # Database models (SQLAlchemy)

conf/                # User configurations
├── strategies/      # Strategy config templates
├── connectors/      # Connector-specific configs
└── scripts/         # Script strategy configs

scripts/             # Example strategy scripts
├── simple_pmm.py
├── simple_xemm.py
└── v2_with_controllers.py
```

### Core Components

**HummingbotApplication** (`hummingbot/client/hummingbot_application.py`)
- Main application controller
- Manages strategy lifecycle
- Handles user commands
- Coordinates connectors and strategies

**ConnectorBase** (`hummingbot/connector/connector_base.pyx`)
- Abstract base for all exchange connectors
- Implements order management, balance tracking
- Event-driven architecture
- Cython implementation for performance

**StrategyBase** (`hummingbot/strategy/strategy_base.pyx`)
- Base class for all V1 strategies
- Market event handling
- Order lifecycle management
- Performance tracking

**StrategyV2Base** (`hummingbot/strategy_v2/runnable_base.py`)
- Modern strategy framework
- Controller-Executor pattern
- Better composability and testing

## Key Architectural Patterns

### Cython Performance Layer
- Critical paths use Cython (.pyx/.pxd files)
- C++ backing for order books and matching
- Compile required after changes

### Event-Driven Architecture
```python
# Events flow: Connector -> Strategy -> Application
class Events(Enum):
    MarketEvent = auto()      # Base market events
    OrderBookEvent = auto()   # Order book updates
    TradeEvent = auto()       # Trades executed
    OrderFilledEvent = auto() # Order completions
```

### Connector Abstraction
- All connectors inherit from `ConnectorBase`
- Standardized interface for different exchange APIs
- WebSocket for real-time data
- REST for trading operations

### Strategy Framework (V2)
```python
# Controller defines logic
class MyController(ControllerBase):
    def determine_actions(self) -> List[ExecutorAction]:
        # Strategy logic here
        pass

# Executor handles execution
class ExecutorOrchestrator:
    def execute_actions(self, actions: List[ExecutorAction]):
        # Order management here
        pass
```

### Gateway Integration
- Separate Gateway service for DEX interactions
- HTTP/WebSocket communication
- Supports Ethereum, Polygon, other EVM chains

## Important Development Notes

### Working with Cython
- Always run `./compile` after modifying .pyx/.pxd files
- Use `cdef` for performance-critical methods
- Python objects need `PyRef` wrapper in C++

### Testing Connectors
- Use `MockPaperExchange` for unit tests
- `NetworkMockingAssistant` for API response mocking
- Test both REST and WebSocket paths

### Strategy Development
- V1: Inherit from strategy type base (e.g., `PureMarketMakingStrategy`)
- V2: Create Controller + use ExecutorOrchestrator
- Scripts: Inherit from `ScriptStrategyBase` for simplicity

### Configuration Management
- YAML configs in `conf/`
- Pydantic models for validation (V2 strategies)
- `ConfigVar` for V1 strategies

### Database and Persistence
- SQLite for trade history and performance
- SQLAlchemy ORM models in `hummingbot/model/`
- Automatic migrations on startup

### Security Considerations
- API keys encrypted with password
- Never commit credentials
- Use `Security.secrets_manager` for key storage

### Gateway Development
- Gateway runs as separate process
- TypeScript/Node.js codebase
- Communicates via localhost HTTP/WS

### Performance Optimization
- Order book updates are performance-critical
- Use Cython for hot paths
- Batch database operations
- Minimize Python object creation in loops

### Common Troubleshooting
- Compilation errors: Check Cython syntax, run `./clean` first
- Import errors: Ensure `./compile` completed successfully
- Gateway connection: Check gateway is running on correct port
- Order book issues: Verify WebSocket connection stability

### DEX Strategies
- For DEX strategies, users need to use the companion Gateway repo which exposes standard endpoints for DEX and chain interactions. See this branch  https://github.com/hummingbot/hummingbot/tree/feat/gateway-2.6
```
