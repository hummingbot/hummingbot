# WEEX Spot Exchange Connector

## Overview

This connector integrates Hummingbot with the WEEX spot exchange, enabling automated trading strategies including market making, arbitrage, and volume generation.

### Exchange Basics

- **Name**: WEEX (Crypto Exchange Platform)
- **Trading Pair Format**: Hummingbot uses `BASE-QUOTE` (e.g., `VCC-USDT`); WEEX uses `BASEQUOTE-SPBL` (e.g., `VCCUSDT-SPBL`)
- **Account Types**: Spot trading only (no perpetuals/derivatives in this connector)
- **API**: REST + WebSocket (separate endpoints for public/private)

## Setup

### 1. API Keys

Generate API keys at [https://www.weex.com/api-keys](https://www.weex.com/api-keys) with:

- **For market making/trading**: Full permissions (read, trade)
- **For monitoring only**: Read-only permission

Store credentials in environment variables:

```bash
export WEEX_API_KEY="your_api_key"
export WEEX_API_SECRET="your_api_secret"
export WEEX_API_PASSPHRASE="your_passphrase"
```

Or use Hummingbot's config prompt when initializing the connector.

### 2. Supported Order Types

- **LIMIT**: Standard limit order
- **LIMIT_MAKER**: Post-only limit order (never takes liquidity)
- **MARKET**: Market order

### 3. Rate Limits

WEEX enforces rate limits per account:

- **Public endpoints**: 20 requests per 2 seconds (IP-based)
- **Private endpoints**: 500 requests per 10 seconds (UID-based)

The connector respects these limits via `AsyncThrottler`.

## Trading Pairs

### Format Convention

**Critical**: Hummingbot uses `BASE-QUOTE` format (e.g., `VCC-USDT`). The connector automatically converts to WEEX format (`VCCUSDT-SPBL`) for API calls.

### Available Pairs

Query available pairs via REST:

```bash
curl -s https://api-spot.weex.com/api/v2/public/exchangeInfo | jq '.data[] | select(.enableTrade==true) | .symbol'
```

Common pairs:
- `VCC-USDT` (VCC/USDT)
- `BTC-USDT` (Bitcoin/USDT)
- `ETH-USDT` (Ethereum/USDT)

## API Quirks & Known Issues

### 1. Signature Format

All REST and WebSocket requests require HMAC-SHA256 signatures:

```
Signature = Base64(HMAC-SHA256(secret_key, timestamp + method + path + query + body))
```

Fields:
- **ACCESS-KEY**: Your API key
- **ACCESS-TIMESTAMP**: Current time in milliseconds
- **ACCESS-SIGN**: Base64-encoded signature
- **ACCESS-PASSPHRASE**: Your passphrase

### 2. Order Cancellation

When canceling an order, provide **both**:
- `clientOrderId`: The order ID you assigned
- `orderId`: The exchange-assigned order ID

Missing either can fail the cancellation.

### 3. User Stream (Private WebSocket)

Authentication is via **headers**, not subscription messages:

```javascript
{
  "ACCESS-KEY": "...",
  "ACCESS-TIMESTAMP": "...",
  "ACCESS-SIGN": "...",
  "ACCESS-PASSPHRASE": "..."
}
```

Channels:
- `account`: Balance updates
- `orders`: Order state changes
- `fill`: Trade fills

### 4. Order Book Depth

Public market data uses:
- **Trades channel**: `trades.{symbol}` (real-time execution data)
- **Depth channel**: `depth.{symbol}.15` or `.200` (15 or 200 levels)

Depth updates arrive as:
- `depthType: SNAPSHOT` — full book
- `depthType: CHANGED` — incremental updates

### 5. Fee Deduction

Fees are **deducted from the quote asset** (returns). For a BUY order:

```
Received: amount - (amount * fee_rate)
```

### 6. Time Synchronization

WEEX enforces strict timestamp validation (±5 seconds). The connector syncs time via:

```
GET /api/v2/public/time -> returns serverTime in milliseconds
```

If your system clock drifts >5s, orders will be rejected. Use NTP to keep time synchronized.

## Bot Scripts

### 1. `weex_status.py` — Quick Connector Check

Verifies connector readiness and fetches mid-price:

```bash
hummingbot> import weex_status
```

### 2. `weex_monitor.py` — Account Monitoring

Displays balances, open orders, and 24h activity for a read-only account:

```bash
hummingbot> import weex_monitor
```

### 3. `weex_vcc_pmm.py` — Pure Market Making

Places symmetric buy/sell orders at configurable spread levels:

```python
order_amount: Decimal = 12500  # 12.5k VCC per level
number_of_orders: int = 4  # 4 levels per side
order_levels: [
    {bid_spread: 0.0066, ask_spread: 0.0066},  # 0.66%
    {bid_spread: 0.0131, ask_spread: 0.0131},  # 1.31%
    ...
]
```

### 4. `weex_volume_generator.py` — Volume Generation

Executes trades at intervals to meet daily volume targets (minimum 10k USDT/day):

```python
daily_volume_target_usdt: 10000
trade_interval_seconds: 300  # 5 min = 288 trades/day
order_size_usdt: 35  # ~$35 per trade
```

## Authentication Flow

### REST Requests

1. Generate timestamp (milliseconds): `ts = str(int(time.time() * 1000))`
2. Build signature payload: `timestamp + METHOD + path + [query] + [body]`
3. Sign: `sig = Base64(HMAC-SHA256(secret_key, payload))`
4. Add headers: `ACCESS-KEY`, `ACCESS-TIMESTAMP`, `ACCESS-SIGN`, `ACCESS-PASSPHRASE`

Example (Python):

```python
import hmac, hashlib, base64, json

def sign_request(api_secret, ts, method, path, body=None):
    message = ts + method + path + (json.dumps(body) if body else "")
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()
    return signature
```

### WebSocket (Private)

Same signature format, sent as **handshake headers** during connection.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `40001` | Missing `ACCESS-KEY` header | Verify API key is correct |
| `40002` | Invalid signature | Check secret key and signature logic |
| `40008` | Timestamp out of range | Sync system clock (NTP) |
| `40010` | Invalid passphrase | Verify passphrase is set correctly |
| `429` | Rate limit exceeded | Wait or reduce request frequency |
| `Order not found` | Order was already filled/canceled | Don't retry; log and move on |
| `Min order amount` | Order size too small | Check trading rules for minimum |

## Order State Machine

```
PENDING_CREATE
    ↓
  OPEN (partially filled or waiting)
    ├→ PARTIALLY_FILLED
    │   ↓
    └→ FILLED

OPEN → CANCELED (if user cancels)
OPEN → FAILED (if rejected by exchange)
```

## Testing

### Unit Tests

Run all WEEX connector tests:

```bash
python -m pytest test/hummingbot/connector/exchange/weex/ -v
```

Tests cover:
- Authentication (signing, header building)
- Order book parsing (snapshots, diffs, trades)
- User stream (fills, order updates, balances)
- Exchange methods (order placement, cancellation, state tracking)

### Integration Tests (Manual)

Before running on mainnet, test with:
1. Paper trading (if available)
2. Small orders with read-only API first
3. One bot at a time (monitor → MM → volume generator)

## Performance Notes

- **WS Reconnect**: ~2–5 seconds (handshake + subscription)
- **Order Latency**: 50–200ms (REST)
- **Fill Latency**: User stream updates arrive within 1–2 seconds
- **Recommended Tick**: 0.5–1.0s (Hummingbot default)

## Troubleshooting

### Connector Won't Connect

```
ERROR: Connector is not ready; missing market data
```

**Causes**:
- API credentials invalid
- Exchange API down
- Network issues

**Fix**: Check `hummingbot logs` and verify connectivity.

### Orders Don't Fill

**Causes**:
- Spread too wide (no takers)
- Insufficient balance
- Order size below exchange minimum

**Fix**: Check trading rules and increase order size/reduce spread.

### High Latency

**Causes**:
- Network congestion
- Server load
- WS disconnections forcing re-auth

**Fix**: Reduce order refresh rate or check server status.

## Reference

- **WEEX API Docs**: https://www.weex.com/api-doc/spot
- **REST Endpoints**: `/api/v2/public/*`, `/api/v2/trade/*`, `/api/v2/account/*`
- **WS Public**: `wss://ws-spot.weex.com/v2/ws/public`
- **WS Private**: `wss://ws-spot.weex.com/v2/ws/private`

## Contributing

Issues, improvements, and pull requests are welcome. Ensure:
- New code includes unit tests (>80% coverage)
- Docstrings follow existing patterns
- API changes are backward-compatible where possible
