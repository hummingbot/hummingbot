# AI Agent Instructions

This file provides guidance to AI coding assistants when working with the Hummingbot codebase.

## Build & Command Reference
- Install dependencies: `pip install -e .` or `./install`
- Run bot: `./start` or `python bin/hummingbot.py`
- Run specific script: `python scripts/[script_name].py`
- Run tests: `make test`
- Compile Cython: `make` or `python setup.py build_ext --inplace`
- Format code: `make format`
- Lint code: `make lint`
- Clean build: `make clean`
- Documentation: `make docs`
- Docker: `docker compose up -d`

## Architecture Overview

### Core Components
- **Event-Driven Architecture**: Pub/sub pattern for market events and trading signals
- **High-Performance Core**: Critical components written in Cython (.pyx files) for speed
- **Modular Design**: Pluggable connectors, strategies, and data feeds
- **Gateway Integration**: TypeScript-based Gateway service handles blockchain/DEX interactions

### Module Organization
- **Client** (`hummingbot/client/`): Main application, CLI interface, configuration management
  - Entry point: `hummingbot_application.py`
  - Commands, parser, and UI components
  - Configuration and settings management

- **Connectors** (`hummingbot/connector/`): Exchange and protocol integrations
  - `exchange/`: Centralized exchange connectors
  - `derivative/`: Perpetual/futures exchange connectors
  - `gateway/`: Gateway-based DEX connectors
  - Each implements standardized interfaces (order placement, balance queries, etc.)

- **Strategies** (`hummingbot/strategy/` and `hummingbot/strategy_v2/`):
  - V1: Original strategy framework (pure_market_making, cross_exchange_market_making, etc.)
  - V2: Newer modular framework with controllers and executors
  - Base classes in Cython for performance

- **Core** (`hummingbot/core/`): Foundation components
  - Event system and clock
  - Data types (OrderBook, Trade, etc.)
  - Rate limiting and API management
  - Web assistants for HTTP/WebSocket connections

## Coding Style Guidelines
- Python 3.8+ with type hints
- 4-space indentation
- Line length: 120 characters max
- Use f-strings for formatting
- Follow PEP 8 conventions
- Cython files (.pyx) for performance-critical code
- Async/await for I/O operations
- Comprehensive docstrings for public methods

## Project Structure
```
hummingbot/
├── bin/                    # Entry points
├── hummingbot/            # Main application code
│   ├── client/            # CLI and application logic
│   ├── connector/         # Exchange/DEX connectors
│   ├── core/              # Core components
│   ├── data_feed/         # Price and market data feeds
│   ├── strategy/          # Trading strategies (V1)
│   ├── strategy_v2/       # Trading strategies (V2)
│   └── __init__.py
├── gateway/               # TypeScript Gateway service (submodule)
├── test/                  # Test files
├── scripts/               # Example scripts
├── templates/             # Configuration templates
├── setup.py              # Package configuration
└── Makefile              # Build commands
```

## Best Practices
- Write tests for all new functionality (aim for 80%+ coverage)
- Use logging instead of print statements
- Handle exceptions appropriately (don't catch generic Exception)
- Use type hints for all function signatures
- Document complex logic with inline comments
- Follow existing patterns in the codebase
- Use the event system for cross-component communication
- Validate user inputs and API responses

## Working with Connectors
- Inherit from `ConnectorBase` or appropriate exchange type base class
- Implement required abstract methods
- Use `OrderTracker` for order management
- Implement proper error handling and reconnection logic
- Add comprehensive unit tests
- Update `CONNECTOR_SETTINGS` in configuration

## Working with Strategies
### V1 Strategies
- Inherit from `StrategyBase` (Cython)
- Implement `c_tick()` for main logic
- Use market events for reactive behavior
- Define configuration parameters

### V2 Strategies
- Use controllers for trading logic
- Implement executors for specific actions
- Leverage the modular architecture
- Support backtesting framework

## Configuration Management
- User configs: `conf/` directory
- Templates: `templates/` directory
- Strategy configs: YAML format
- Connector settings: Defined in connector modules
- Security: Use encrypted storage for API keys

## Testing Guidelines
- Unit tests in `test/` mirroring source structure
- Use fixtures for test data
- Mock external API calls
- Test both success and failure cases
- Run tests before submitting PRs

## Adding New Features
### New Exchange Connector
1. Create module in `hummingbot/connector/exchange/`
2. Implement required interfaces
3. Add configuration templates
4. Write comprehensive tests
5. Update documentation

### New Strategy
1. Choose V1 or V2 framework
2. Create strategy module
3. Define configuration parameters
4. Implement core logic
5. Add example scripts
6. Document usage

### New Data Feed
1. Create module in `hummingbot/data_feed/`
2. Implement data fetching logic
3. Handle rate limiting
4. Add caching if appropriate
5. Write tests

## Performance Considerations
- Use Cython for performance-critical code
- Implement proper rate limiting
- Cache frequently accessed data
- Use async I/O for network operations
- Profile code for bottlenecks
- Minimize memory allocations in hot paths

## Security Best Practices
- Never log sensitive information (API keys, passwords)
- Use encrypted configuration storage
- Validate all external inputs
- Handle API errors gracefully
- Implement proper authentication
- Follow secure coding practices

## Gateway Integration
- Gateway handles blockchain/DEX interactions
- Communicate via REST API
- Standardized endpoints for all operations
- See `gateway/AGENTS.md` for Gateway-specific instructions

## Environment Variables
- `HUMMINGBOT_CONF_DIR`: Configuration directory path
- `HUMMINGBOT_LOGS_DIR`: Logs directory path
- `HUMMINGBOT_DATA_DIR`: Data directory path
- `HUMMINGBOT_SCRIPTS_DIR`: Scripts directory path

## Common Patterns
- **Singleton**: Used for exchange instances
- **Factory**: Connector creation
- **Observer**: Event system
- **Strategy**: Trading strategies
- **Adapter**: External API integration

## Debugging Tips
- Enable debug logging in configuration
- Use VS Code/Cursor with Python extension
- Set breakpoints in .py files (not .pyx)
- Check logs in `logs/` directory
- Use `pdb` for interactive debugging
- Monitor Gateway logs for DEX issues

## Resources
- Documentation: https://docs.hummingbot.org
- Discord: https://discord.gg/hummingbot
- GitHub: https://github.com/hummingbot/hummingbot
- Contribution guide: See CONTRIBUTING.md
