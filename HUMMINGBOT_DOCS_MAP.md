# Hummingbot Documentation Map

This document provides a systematic map of the Hummingbot documentation to help understand the entire framework.

## Documentation Home
- **Main Site**: https://hummingbot.org
- **Repository**: https://github.com/hummingbot/hummingbot-site

---

## 1. GETTING STARTED

### Installation & Setup
- **Installation Overview**: https://hummingbot.org/installation/
  - Hummingbot Client Quickstart: https://hummingbot.org/installation/hummingbot-client/
  - Hummingbot API Quickstart: https://hummingbot.org/installation/hummingbot-api/
  - Updating to New Versions: https://hummingbot.org/installation/update/
  - Bot Orchestration: https://hummingbot.org/installation/broker/

### First Steps
- **Guides**: https://hummingbot.org/guides/
- **FAQ**: https://hummingbot.org/faq/
- **Troubleshooting**: https://hummingbot.org/troubleshooting/
- **Glossary**: https://hummingbot.org/glossary/

---

## 2. CORE COMPONENTS

### 2.1 Hummingbot Client (CLI)
- **Main Page**: https://hummingbot.org/client/
- **Installation**: https://hummingbot.org/client/installation/

#### Basic Operations
- User Interface Guide: https://hummingbot.org/client/user-interface/
- Commands and Shortcuts: https://hummingbot.org/client/commands-shortcuts/
- Launch and Exit Hummingbot: https://hummingbot.org/client/launch-exit/
- Create and Delete Password: https://hummingbot.org/client/password/
- Connect Exchange API Keys: https://hummingbot.org/client/connect/
- Create Config Files: https://hummingbot.org/client/config-files/
- Find Log Files: https://hummingbot.org/client/log-files/
- Check Balances: https://hummingbot.org/client/balance/
- Start and Stop Strategy: https://hummingbot.org/client/start-stop/
- Check Bot and Market Status: https://hummingbot.org/client/status/
- Check Trading Performance: https://hummingbot.org/client/history/
- Export Trades/Keys: https://hummingbot.org/client/export/

#### Advanced Features
- Auto-start from Command Line: https://hummingbot.org/client/global-configs/strategy-autostart/
- Balance Limit: https://hummingbot.org/client/global-configs/balance-limit/
- Clock Tick Size: https://hummingbot.org/client/global-configs/clock-tick/
- Color Settings: https://hummingbot.org/client/global-configs/color-settings/
- Connect External Database: https://hummingbot.org/client/global-configs/external-db/
- Debug Console: https://hummingbot.org/client/debug-console/
- Kill Switch: https://hummingbot.org/client/global-configs/kill-switch/
- Market Data Collector: https://hummingbot.org/client/global-configs/data-collector/
- Override Fees: https://hummingbot.org/client/global-configs/override-fees/
- Paper Trading Mode: https://hummingbot.org/client/global-configs/paper-trade/
- Rate Oracle: https://hummingbot.org/strategies/v1-strategies/strategy-configs/rate-oracle/
- Rate Limits Share Pct: https://hummingbot.org/client/global-configs/rate-limits-share-pct/

### 2.2 Hummingbot API
- **Main Page**: https://hummingbot.org/hummingbot-api/
- **Quickstart Guide**: https://hummingbot.org/hummingbot-api/quickstart/
- REST API backend for managing multiple bots
- Best for production environments and cloud deployment

### 2.3 Gateway DEX Middleware
- **Main Page**: https://hummingbot.org/gateway/
- **Installation & Setup**: https://hummingbot.org/gateway/installation/
- **Configuration**: https://hummingbot.org/gateway/configuration/
- **Commands**: https://hummingbot.org/gateway/commands/
- **Chains**: https://hummingbot.org/gateway/chains/
- **DEX Connectors**: https://hummingbot.org/gateway/connectors/
- **RPC Providers**: https://hummingbot.org/gateway/rpc/
- **Strategies & Scripts**: https://hummingbot.org/gateway/strategies/

#### Gateway Architecture
- Router: DEX aggregators finding optimal swap routes
- AMM: Traditional V2-style constant product pools (x*y=k)
- CLMM: V3-style concentrated liquidity market makers

### 2.4 User Interfaces

#### Condor (Telegram Bot)
- **Main Page**: https://hummingbot.org/condor/
- Telegram interface for monitoring and controlling Hummingbot instances
- Works with Hummingbot API

#### Dashboard (Deprecated)
- **Main Page**: https://hummingbot.org/dashboard/
- Web-based UI (deprecated, use Condor instead)

### 2.5 Other Components

#### Hummingbot MCP (Model Context Protocol)
- **Main Page**: https://hummingbot.org/mcp/
- Enables AI assistants (Claude, Gemini, ChatGPT) to interact with Hummingbot

#### Quants Lab
- **Main Page**: https://hummingbot.org/quants-lab/
- Jupyter notebooks for data collection, backtesting, and research
- Python framework for quantitative trading research

---

## 3. STRATEGIES

### Strategy Overview
- **Main Page**: https://hummingbot.org/strategies/

### 3.1 V2 Framework (Recommended)
- **Architecture**: https://hummingbot.org/strategies/v2-strategies/

#### Strategy Types
- **Scripts**: https://hummingbot.org/strategies/scripts/
  - Simple Python files containing all strategy logic
  - Good for prototyping and simple strategies

- **Controllers**: https://hummingbot.org/strategies/v2-strategies/controllers/
  - Abstracted strategy logic with Executors
  - Can be backtested and deployed via Dashboard
  - Multiple controllers per bot instance
  - Best for complex, multi-pair strategies

#### V2 Components
- **Market Data Provider**: https://hummingbot.org/strategies/v2-strategies/data/
- **Executors**: https://hummingbot.org/strategies/v2-strategies/executors/
- **Examples**: https://hummingbot.org/strategies/v2-strategies/examples/

### 3.2 V1 Framework (Legacy)
- **Main Page**: https://hummingbot.org/strategies/v1-strategies/
- Traditional configurable templates (Avellaneda & Stoikov, etc.)
- Still supported but not actively developed

---

## 4. EXCHANGE CONNECTORS

### Connector Overview
- **Main Page**: https://hummingbot.org/exchanges/
- **All Connectors**: https://hummingbot.org/connectors/
- **Reporting Dashboard**: https://hummingbot.org/reporting/

### 4.1 CLOB Connectors
- **CLOB Overview**: https://hummingbot.org/connectors/clob/
- Central Limit Order Book exchanges (CEX and DEX)

#### Sponsored Exchanges (Foundation Partners)
- **Binance** (Spot + Perpetual): https://hummingbot.org/exchanges/binance/
- **Bitmart** (Spot + Perpetual): https://hummingbot.org/exchanges/bitmart/
- **Bitget** (Spot + Perpetual): https://hummingbot.org/exchanges/bitget/
- **Derive** (Spot + Perpetual): https://hummingbot.org/exchanges/derive/
- **dYdX** (Perpetual): https://hummingbot.org/exchanges/dydx/
- **Gate.io** (Spot + Perpetual): https://hummingbot.org/exchanges/gate-io/
- **HTX/Huobi** (Spot): https://hummingbot.org/exchanges/htx/
- **Hyperliquid** (Spot + Perpetual): https://hummingbot.org/exchanges/hyperliquid/
- **KuCoin** (Spot + Perpetual): https://hummingbot.org/exchanges/kucoin/
- **OKX** (Spot + Perpetual): https://hummingbot.org/exchanges/okx/
- **XRP Ledger** (Spot): https://hummingbot.org/exchanges/xrpl/

#### Other CLOB Connectors
- AscendEx, BingX, Bitrue, Bitstamp, BTC Markets, Bybit, Coinbase, Cube, Dexalot, Foxbit, Injective Helix, Kraken, MEXC, NDAX, Vertex

### 4.2 Gateway DEX Connectors
- **Gateway DEX Overview**: https://hummingbot.org/gateway/connectors/

#### Router DEXs
- 0x Protocol: https://hummingbot.org/exchanges/gateway/0x/
- Jupiter (Solana): https://hummingbot.org/exchanges/gateway/jupiter/

#### AMM DEXs
- Balancer: https://hummingbot.org/exchanges/gateway/balancer/
- Curve: https://hummingbot.org/exchanges/gateway/curve/
- PancakeSwap: https://hummingbot.org/exchanges/gateway/pancakeswap/
- QuickSwap: https://hummingbot.org/exchanges/gateway/quickswap/
- Raydium: https://hummingbot.org/exchanges/gateway/raydium/
- SushiSwap: https://hummingbot.org/exchanges/gateway/sushiswap/
- Trader Joe: https://hummingbot.org/exchanges/gateway/traderjoe/
- Uniswap: https://hummingbot.org/exchanges/gateway/uniswap/

#### CLMM DEXs
- Meteora (Solana): https://hummingbot.org/exchanges/gateway/meteora/
- Orca (Solana): https://hummingbot.org/exchanges/gateway/orca/

### 4.3 Building Connectors
- **Building CLOB Connectors**: https://hummingbot.org/connectors/connectors/
- **Building Gateway Connectors**: https://hummingbot.org/connectors/gateway-connectors/
- **Debugging & Testing**: https://hummingbot.org/connectors/connectors/debug/

---

## 5. GOVERNANCE & COMMUNITY

### Governance
- **About Foundation**: https://hummingbot.org/about/
- **Governance Process**: https://hummingbot.org/about/governance/
- **Proposals (HGP)**: https://hummingbot.org/about/proposals/
- **HBOT Token**: Required for creating proposals
- **Snapshot Voting**: https://snapshot.org/#/hbot.eth
- **HBOT Tracker**: https://docs.google.com/spreadsheets/d/1UNAumPMnXfsghAAXrfKkPGRH9QlC8k7Cu1FGQVL1t0M/

### Community
- **Community Page**: https://hummingbot.org/community/
- **Discord**: https://discord.gg/hummingbot
- **YouTube**: https://www.youtube.com/c/hummingbot
- **Twitter**: https://twitter.com/_hummingbot
- **Newsletter**: https://hummingbot.substack.com
- **Certification**: https://hummingbot.org/community/certification/

### Bounties
- **Bounties Page**: https://hummingbot.org/bounties/
- Community developers maintain connectors
- Connector development starting at $10,000

---

## 6. DEVELOPMENT RESOURCES

### GitHub Repositories
- **Hummingbot Client**: https://github.com/hummingbot/hummingbot
- **Gateway**: https://github.com/hummingbot/gateway
- **Hummingbot API**: https://github.com/hummingbot/hummingbot-api
- **Condor**: https://github.com/hummingbot/condor
- **MCP Server**: https://github.com/hummingbot/mcp
- **Quants Lab**: https://github.com/hummingbot/quants-lab
- **Documentation Site**: https://github.com/hummingbot/hummingbot-site

### Contributing
- **Contributing Guide**: CONTRIBUTING.md in repo
- **Pull Request Template**: .github/pull_request_template.md
- **Code of Conduct**: CODE_OF_CONDUCT.md

---

## 7. LEARNING RESOURCES

### Official Training
- **Botcamp**: https://www.botcamp.xyz/
  - Official training and certification
  - Bootcamps and courses for V2 framework
  - Strategy examples and presentations

### Blog & Content
- **Blog**: https://hummingbot.org/blog/
- **Release Notes**: https://hummingbot.org/release-notes/
- **Strategy Guides** (from blog):
  - Grid Strike Strategy
  - Funding Rate Arbitrage on Hyperliquid
  - Liquidation Sniper Strategy
  - Gateway V2 Architecture (Part 1 & 2)

### Data & Analytics
- **Reported Volumes Dashboard**: https://p.datadoghq.com/sb/a96a744f5-a15479d77992ccba0d23aecfd4c87a52
  - Real-time trading volume across all Hummingbot instances
  - Filterable by exchange and version

---

## 8. KEY CONCEPTS TO UNDERSTAND

### Architecture Components
1. **Hummingbot Client** - Core Python trading engine with CLI
2. **Gateway** - TypeScript middleware for DEX connectivity
3. **Hummingbot API** - REST API server for managing multiple bots
4. **Connectors** - Standardized exchange/blockchain integrations
5. **Strategies** - Automated trading logic (V1 vs V2 frameworks)
6. **Executors** - V2 building blocks for order management
7. **Controllers** - V2 abstraction layer for complex strategies

### Exchange Types
1. **CLOB CEX** - Centralized exchanges (Binance, OKX, etc.)
2. **CLOB DEX** - Decentralized order book exchanges (Hyperliquid, dYdX)
3. **AMM DEX** - Automated market makers (Uniswap, PancakeSwap)
   - Router: DEX aggregators
   - AMM: V2 constant product pools
   - CLMM: V3 concentrated liquidity

### Strategy Frameworks
1. **V2 Framework** (Recommended)
   - Scripts: Simple, self-contained Python files
   - Controllers: Modular, testable, multi-instance capable
   - Executors: Position management building blocks

2. **V1 Framework** (Legacy)
   - Pure Market Making
   - Cross-Exchange Market Making
   - Template-based configurations

---

## 9. SYSTEMATIC LEARNING PATH

### Phase 1: Foundations (Week 1-2)
1. Read Installation Overview and install Hummingbot Client
2. Review User Interface Guide and Commands
3. Understand basic operations (connect exchange, check balance, etc.)
4. Study Glossary for terminology
5. Review FAQ and Troubleshooting

### Phase 2: Core Concepts (Week 3-4)
1. Study Connector architecture (CLOB vs Gateway)
2. Understand exchange types and supported platforms
3. Learn about V2 vs V1 strategy frameworks
4. Review Clock Tick concept and execution model
5. Study Config Files and Paper Trading

### Phase 3: Strategy Development (Week 5-8)
1. Start with V2 Scripts - simple strategy examples
2. Understand Market Data Provider
3. Study Executors and how they work
4. Progress to Controllers for complex strategies
5. Review example strategies in the repo
6. Learn backtesting and optimization

### Phase 4: Advanced Topics (Week 9-12)
1. Gateway integration for DEX trading
2. Building custom connectors
3. External database integration
4. Multi-bot orchestration with Hummingbot API
5. Condor for remote management
6. MCP for AI integration

### Phase 5: Production & Community (Ongoing)
1. Production deployment best practices
2. Risk management and kill switches
3. Performance monitoring and optimization
4. Contributing to open source
5. Governance participation
6. Botcamp certification

---

## 10. IMPORTANT FILES IN REPO

### Configuration
- `conf/` - Strategy and connector configurations
- `conf/conf_client.yml` - Client global settings
- `conf/conf_fee_overrides.yml` - Custom fee configurations
- `conf/hummingbot_logs.yml` - Logging configuration

### Core Code
- `hummingbot/` - Main source directory
  - `client/` - CLI client implementation
  - `connector/` - Exchange connector implementations
  - `strategy/` - V1 strategy implementations
  - `strategy_v2/` - V2 strategy framework
  - `core/` - Core trading engine
  - `data_feed/` - Market data handling

### Scripts & Controllers
- `scripts/` - Example V2 scripts
- `controllers/` - Example V2 controllers
  - `directional_trading/`
  - `market_making/`
  - `generic/`

### Development
- `test/` - Test suite
- `setup.py` - Package setup
- `pyproject.toml` - Modern Python project config
- `Dockerfile` - Container image definition
- `docker-compose.yml` - Multi-container setup

---

## NEXT STEPS

To systematically learn Hummingbot:

1. **Start with basics**: Install and run a simple strategy in paper trading mode
2. **Read architecture docs**: Understand how components fit together
3. **Study examples**: Review scripts in `scripts/` directory
4. **Join community**: Discord for Q&A and learning from others
5. **Build incrementally**: Start with scripts, progress to controllers
6. **Contribute**: Fix bugs, improve docs, build connectors
7. **Consider Botcamp**: For structured learning and certification

This map provides a comprehensive overview of Hummingbot documentation. Use it as a reference to navigate the ecosystem systematically.
