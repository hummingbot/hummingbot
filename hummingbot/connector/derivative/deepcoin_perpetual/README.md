# Deepcoin Perpetual Integration for Hummingbot

This directory contains the integration for Deepcoin Perpetual trading on Hummingbot, implemented following the same patterns as Bybit Perpetual integration.

## Files Structure

### Core Files
- `deepcoin_perpetual_derivative.py` - Main derivative exchange class
- `deepcoin_perpetual_constants.py` - Constants and configuration
- `deepcoin_perpetual_auth.py` - Authentication handling
- `deepcoin_perpetual_utils.py` - Utility functions for data conversion
- `deepcoin_perpetual_web_utils.py` - Web utilities and URL builders

### Data Sources
- `deepcoin_perpetual_api_order_book_data_source.py` - Order book data source
- `deepcoin_perpetual_user_stream_data_source.py` - User stream data source

### Test Files
- `test_deepcoin_perpetual_integration.py` - Integration test script

## Features Implemented

### Exchange Integration
- ✅ Basic exchange connection setup following Bybit patterns
- ✅ Authentication with API key, secret, and passphrase (HMAC-SHA256)
- ✅ Rate limiting configuration with proper throttling
- ✅ Trading rules management
- ✅ Order management (place, cancel, status updates)
- ✅ Position management
- ✅ Balance tracking
- ✅ Response validation and error handling

### Trading Features
- ✅ Support for LIMIT and MARKET orders
- ✅ Position actions (OPEN, CLOSE)
- ✅ Position sides (LONG, SHORT)
- ✅ Position modes (ONEWAY, HEDGE)
- ✅ Leverage setting
- ✅ Fee calculation
- ✅ Funding fee polling

### Data Management
- ✅ Order book data source (REST API polling)
- ✅ User stream data source (WebSocket - TODO)
- ✅ Trading pair management
- ✅ Symbol mapping
- ✅ Time synchronization
- ✅ Web assistant factory with proper pre-processors

## API Endpoints Used

### Public Endpoints
- `/api/v1/market/symbols` - Exchange info and trading rules
- `/api/v1/market/depth` - Order book snapshots
- `/api/v1/market/ticker` - Price tickers
- `/api/v1/market/ping` - Network check

### Private Endpoints
- `/api/v1/account/balance` - Account balances
- `/api/v1/account/positions` - Position information
- `/api/v1/trade/order` - Order management
- `/api/v1/trade/leverage` - Leverage setting
- `/api/v1/trade/positionMode` - Position mode setting
- `/api/v1/trade/fills` - Trade history

## Authentication

The integration uses Deepcoin's HMAC-SHA256 signature authentication:
- `DC-ACCESS-KEY` - API key
- `DC-ACCESS-SIGN` - HMAC-SHA256 signature
- `DC-ACCESS-TIMESTAMP` - Request timestamp
- `DC-ACCESS-PASSPHRASE` - API passphrase

## Configuration

### Required Parameters
- `deepcoin_perpetual_api_key` - Your Deepcoin API key
- `deepcoin_perpetual_api_secret` - Your Deepcoin API secret
- `deepcoin_perpetual_passphrase` - Your Deepcoin API passphrase

### Optional Parameters
- `trading_pairs` - List of trading pairs to track
- `trading_required` - Whether trading is enabled
- `domain` - Exchange domain (default: "deepcoin_perpetual")

## Usage Example

```python
from hummingbot.connector.derivative.deepcoin_perpetual import DeepcoinPerpetualDerivative

# Initialize the exchange
exchange = DeepcoinPerpetualDerivative(
    deepcoin_perpetual_api_key="your_api_key",
    deepcoin_perpetual_api_secret="your_secret",
    deepcoin_perpetual_passphrase="your_passphrase",
    trading_pairs=["BTC-USDT", "ETH-USDT"],
    trading_required=True
)

# Set leverage
await exchange.set_leverage("BTC-USDT", 10)

# Set position mode
await exchange.set_position_mode(PositionMode.ONEWAY)

# Place an order
order_id = await exchange.place_order(
    trading_pair="BTC-USDT",
    amount=Decimal("0.01"),
    order_type=OrderType.LIMIT,
    trade_type=TradeType.BUY,
    price=Decimal("50000"),
    position_action=PositionAction.OPEN
)
```

## TODO Items

- [ ] Implement WebSocket connections for real-time data
- [ ] Complete order book message parsing
- [ ] Add comprehensive error handling
- [ ] Implement user stream event processing
- [ ] Add unit tests
- [ ] Add integration tests with real API

## Rate Limits

The integration respects Deepcoin's rate limits:
- 1200 requests per minute for general API calls
- 100 orders per 10 seconds
- 100,000 orders per day
- 10,000 raw requests per 5 minutes

## Error Handling

Common error codes handled:
- 40001: Order does not exist
- 40002: Unknown order sent
- 40003: Insufficient balance
- 40004: Invalid leverage

## Notes

- This integration follows Hummingbot's standard patterns for derivative exchanges
- All monetary values use Decimal for precision
- The integration supports both testnet and mainnet environments
- Position management includes both one-way and hedge modes
