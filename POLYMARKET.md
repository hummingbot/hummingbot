# Polymarket Connector for Hummingbot

## Overview
The Polymarket connector enables trading on Polymarket's prediction markets through Hummingbot. It implements the Event connector type for prediction/event-based trading with YES/NO outcomes.

## Features
- ✅ Direct CLOB trading via py-clob-client SDK
- ✅ EIP-712 signature-based authentication
- ✅ Event/prediction market support with YES/NO outcomes
- ✅ Polygon (Chain ID 137) integration
- ✅ Real-time order and balance tracking
- ✅ Market resolution monitoring

## Installation

### Prerequisites
1. Hummingbot installed with conda environment
2. Polygon wallet with private key
3. USDC on Polygon for trading

### Setup
1. Install py-clob-client in hummingbot environment:
```bash
/opt/anaconda3/envs/hummingbot/bin/pip install py-clob-client
```

2. Start Hummingbot:
```bash
./start
```

3. Connect to Polymarket:
```bash
>>> connect polymarket
```

4. Enter credentials when prompted:
- Polygon private key (with 0x prefix)
- Polygon wallet address
- Signature type (0=EOA, 1=PROXY, 2=GNOSIS) - default: 0

## Configuration

### Trading Pairs Format
Polymarket uses the event trading pair format:
```
MARKET-OUTCOME-QUOTE
```
Example: `ELECTION2024-YES-USDC`

### Connector Settings
- **Type**: CLOB_EVENT
- **Centralized**: No
- **Uses Gateway**: No
- **Fees**: 2% maker, 7% taker

## Architecture

### Core Components

#### 1. PolymarketEvent (`polymarket_event.py`)
Main connector class implementing EventPyBase. Handles:
- Order placement and cancellation
- Balance updates
- Position tracking
- Market resolution monitoring

#### 2. PolymarketAuth (`polymarket_auth.py`)
Authentication wrapper for py-clob-client SDK:
- EIP-712 signature generation
- API credential management
- Order signing

#### 3. PolymarketAPIDataSource (`polymarket_api_data_source.py`)
REST API interactions:
- Market data fetching
- Order book updates
- Account positions
- Balance queries

### Order Types Supported
- LIMIT
- LIMIT_MAKER
- IOC (Immediate or Cancel)
- FOK (Fill or Kill)
- PREDICTION_LIMIT
- PREDICTION_MARKET

## Testing

Test scripts are available in the `/scripts` directory:
- `test_polymarket_connection.py` - Test connector connection
- `test_polymarket_trading.py` - Test order placement
- `test_polymarket_balances.py` - Test balance fetching

## Common Commands

### Check Connection
```bash
>>> connect polymarket
```

### View Balances
```bash
>>> balance
```

### Place Order
```python
# In strategy or script
connector.place_prediction_order(
    market_id="ELECTION2024",
    outcome=OutcomeType.YES,
    trade_type=TradeType.BUY,
    amount=Decimal("10"),
    price=Decimal("0.65")
)
```

## Troubleshooting

### Import Error: py-clob-client not found
Install the package in hummingbot environment:
```bash
/opt/anaconda3/envs/hummingbot/bin/pip install py-clob-client
```

### Balance not updating
1. Ensure wallet has USDC on Polygon
2. Check network connectivity
3. Verify API credentials are correct

### Connection Issues
1. Restart hummingbot
2. Re-enter credentials
3. Check Polygon RPC is accessible

## Development

### File Structure
```
hummingbot/
├── connector/
│   └── event/
│       └── polymarket/
│           ├── polymarket_event.py          # Main connector
│           ├── polymarket_auth.py           # Authentication
│           ├── polymarket_api_data_source.py # API client
│           ├── polymarket_constants.py      # Constants
│           └── polymarket_utils.py          # Configuration
└── scripts/
    └── test_polymarket_*.py                 # Test scripts
```

### Key Classes
- `PolymarketEvent` - Main connector class
- `PolymarketAuth` - SDK authentication wrapper
- `PolymarketAPIDataSource` - REST API client
- `EventInFlightOrder` - Order tracking

## Resources
- [Polymarket CLOB Documentation](https://docs.polymarket.com/developers/CLOB)
- [py-clob-client SDK](https://github.com/Polymarket/py-clob-client)
- [Hummingbot Documentation](https://docs.hummingbot.org)

## License
Same as Hummingbot - Apache 2.0
