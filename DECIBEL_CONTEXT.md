# Decibel Perpetual Connector - Build Instructions

## Goal
Build a complete Hummingbot perpetual derivatives connector for Decibel exchange.
This is for GitHub bounty issue #8028 (https://github.com/hummingbot/hummingbot/issues/8028) paying $3,000 USDC.

## What to Build
Create `hummingbot/connector/derivative/decibel_perpetual/` with these files:
1. `__init__.py` (empty)
2. `dummy.pxd` (copy from hyperliquid_perpetual)
3. `dummy.pyx` (copy from hyperliquid_perpetual)
4. `decibel_perpetual_constants.py`
5. `decibel_perpetual_auth.py`
6. `decibel_perpetual_web_utils.py`
7. `decibel_perpetual_api_order_book_data_source.py`
8. `decibel_perpetual_user_stream_data_source.py`
9. `decibel_perpetual_utils.py`
10. `decibel_perpetual_derivative.py` (main connector class)

Also create tests in `test/hummingbot/connector/derivative/decibel_perpetual/`.

## Primary Reference
Use `hummingbot/connector/derivative/hyperliquid_perpetual/` as the primary template.
Read ALL files there before starting. Adapt them for Decibel.

## Decibel API Details

### REST API
- Testnet: `https://api.testnet.aptoslabs.com/decibel`
- Mainnet: `https://api.mainnet.aptoslabs.com/decibel`
- Auth: `Authorization: Bearer <API_KEY>` + `Origin: https://netna-app.decibel.trade/trade`
- All endpoints are GET requests with query params

### Key REST Endpoints
```
GET /api/v1/markets          - List all trading markets
GET /api/v1/depth?market=X   - Order book snapshot
GET /api/v1/prices           - Current prices (oracle, mark, mid, funding)
GET /api/v1/asset_contexts   - Market contexts (volume, 24h change, etc.)
GET /api/v1/candlesticks?market=X&interval=1m
GET /api/v1/trades?market=X  - Recent trades

GET /api/v1/account_positions?account=X  - Open positions
GET /api/v1/open_orders?account=X        - Open orders
GET /api/v1/orders?order_id=X            - Single order details
GET /api/v1/account_overviews?account=X  - Equity, margin, balances
GET /api/v1/order_history?account=X      - Historical orders
GET /api/v1/trade_history?account=X      - Historical trades
GET /api/v1/funding_rate_history?account=X
```

### WebSocket API
- URL: `wss://ws.mainnet.aptoslabs.com/decibel` (infer from context)
- Auth: `Sec-Websocket-Protocol: decibel, <API_KEY>`
- Subscribe: `{"method":"subscribe","topic":"depth:0x<market_address>"}`
- Topics:
  - `depth:<market>` - Order book updates
  - `prices:<market>` - Price updates
  - `trades:<market>` - Trade updates
  - `market_price` (global) - All market prices
  - `account_open_orders:<account>` - User open orders
  - `account_positions:<account>` - User positions
  - `order_update:<account>` - Order status updates
  - `account_overview:<account>` - Account equity/margin

### Order Placement (On-Chain via Aptos)
Orders are placed via Aptos blockchain transactions using `aptos-sdk` Python library.

```python
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

PACKAGE = "0x<decibel_package_address>"

# Place order
transaction = await rest_client.build_transaction(
    sender=account.address(),
    payload={
        "function": f"{PACKAGE}::dex_accounts_entry::place_order_to_subaccount",
        "type_arguments": [],
        "function_arguments": [
            subaccount_addr,   # Trading Account object address
            market_addr,       # PerpMarket object address
            price_u64,         # price with 9 decimals (e.g., 97250 * 10^9)
            size_u64,          # size with 9 decimals
            is_buy,            # True for buy (long), False for sell (short)
            0,                 # timeInForce: 0=GTC, 1=PostOnly, 2=IOC
            False,             # isReduceOnly
            client_order_id,   # Optional string
            None,              # stopPrice
            None,              # tpTriggerPrice
            None,              # tpLimitPrice
            None,              # slTriggerPrice
            None,              # slLimitPrice
            None,              # builderAddr
            None,              # builderFee
        ],
    },
)
```

### Cancel Order (On-Chain)
```
{package}::dex_accounts_entry::cancel_order
Parameters: signer, subaccount, market, order_id
```

### Price/Size Formatting
- Prices use 9 decimal places (multiply by 10^9)
- Sizes use 9 decimal places (multiply by 10^9)

## Constants to Define
```python
DECIBEL_MAINNET_REST = "https://api.mainnet.aptoslabs.com/decibel"
DECIBEL_TESTNET_REST = "https://api.testnet.aptoslabs.com/decibel"
DECIBEL_MAINNET_WS = "wss://ws.mainnet.aptoslabs.com/decibel"
DECIBEL_TESTNET_WS = "wss://ws.testnet.aptoslabs.com/decibel"
APTOS_MAINNET_NODE = "https://api.mainnet.aptoslabs.com/v1"
APTOS_TESTNET_NODE = "https://api.testnet.aptoslabs.com/v1"
```

## Connector Credentials
The connector needs:
- `decibel_api_key`: Bearer token from Geomi (https://geomi.dev)
- `decibel_api_secret`: Not needed (Bearer token auth)
- `decibel_account_address`: Aptos wallet address (0x...)
- `decibel_subaccount_address`: Trading Account object address
- `decibel_private_key`: Ed25519 private key for signing Aptos transactions

## Required Hummingbot v2.1+ Interface
The main `DecibelPerpetualDerivative` class must extend `PerpetualDerivativePyBase` and implement:
- `place_order` / `cancel_order`
- `get_order_price_quantum` / `get_order_size_quantum`
- `get_order_book_data_source` / `get_user_stream_data_source`
- `supported_position_modes` → [PositionMode.ONEWAY]
- `get_funding_info`
- `_trading_pair_fee_rules`
- `_initialize_trading_pair_symbol_map`

## Tests Required
Create comprehensive unit tests using mock responses. Reference:
`test/hummingbot/connector/derivative/hyperliquid_perpetual/`

Tests must cover:
- `test_decibel_perpetual_auth.py` - Auth header generation
- `test_decibel_perpetual_api_order_book_data_source.py` - Order book parsing
- `test_decibel_perpetual_derivative.py` - Main connector (place/cancel orders, positions, balances)
- `test_decibel_perpetual_user_stream_data_source.py` - WebSocket user streams

## Registration
After building the connector, register it in:
1. `hummingbot/connector/connector_status.py` - Add `decibel_perpetual: ConnectorStatus.SILVER`
2. `setup.py` - Add `hummingbot.connector.derivative.decibel_perpetual` to packages
3. `hummingbot/templates/conf_global_TEMPLATE.yml` - If needed
4. `conf/connectors/` - Create `decibel_perpetual.yml` template

## Important Notes
- This is an on-chain DEX (Aptos blockchain), not a CEX
- Order placement is via blockchain transactions, not REST POST
- Use `aptos-sdk` for transaction building and signing
- The REST API is read-only (market data + account data queries)
- Market addresses are 0x-prefixed Aptos object addresses
- Always handle the `aptos-sdk` dependency in `pyproject.toml`

## Quality Bar
- No shortcuts — implement ALL required methods properly
- Comprehensive test coverage with realistic mock data
- Proper error handling for network failures, transaction errors
- Correct price/size decimal conversion (9 decimals)
- Handle both testnet and mainnet configuration
