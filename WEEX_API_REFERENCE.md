# WEEX Spot API Reference (2026-01-30)

This document summarizes the official WEEX Spot API documentation for REST and WebSocket, including authentication, endpoints, request/response formats, error codes, and best practices. It is intended as a local reference for Hummingbot developers and QA.

---

## 1. Authentication

### API Key Management
- Create API keys in the WEEX web platform (up to 10 per user).
- Each key has permissions: Read (market data), Trade (order management).
- API credentials required:
  - `APIKey`: Public identifier
  - `SecretKey`: Private key for HMAC signature
  - `Passphrase`: User-defined, cannot be recovered if lost

### Signature Generation
- **Header fields:**
  - `ACCESS-KEY`: API key
  - `ACCESS-SIGN`: Signature (see below)
  - `ACCESS-TIMESTAMP`: Milliseconds since epoch
  - `ACCESS-PASSPHRASE`: Passphrase
- **Signature string:**
  - For GET: `timestamp + method.toUpperCase() + requestPath + queryString`
  - For POST: `timestamp + method.toUpperCase() + requestPath + queryString + body`
  - If no queryString, omit `?`
- **Signature algorithm:**
  1. Concatenate string as above
  2. HMAC-SHA256 with `SecretKey`
  3. Base64 encode result
- **Timestamp:** Must be within 30s of server time (`/api/v2/public/time`)

---

## 2. REST API Endpoints

### Public Endpoints (No Auth Required)
| Endpoint | Method | Path | Description |
|----------|--------|------|-------------|
| Get Server Time | GET | `/api/v2/public/time` | Returns server time (ms) |
| Get Currencies | GET | `/api/v2/public/currencies` | List all supported coins |
| Get Products | GET | `/api/v2/public/products` | List all trading pairs (symbols) |
| Get Symbol Info | GET | `/api/v2/public/exchangeInfo` | Trading rules, min/max, fees |
| Get Ticker | GET | `/api/v2/market/ticker` | 24h stats for one symbol |
| Get All Tickers | GET | `/api/v2/market/tickers` | 24h stats for all symbols |
| Get Trades | GET | `/api/v2/market/fills` | Recent trades for a symbol |
| Get Candles | GET | `/api/v2/market/candles` | OHLCV data |
| Get Depth | GET | `/api/v2/market/depth` | Order book snapshot |

### Private Endpoints (Auth Required)
| Endpoint | Method | Path | Description |
|----------|--------|------|-------------|
| Get Account Assets | GET | `/api/v2/account/assets` | Balances (available, frozen, equity) |
| Get Spot Bills | POST | `/api/v2/account/bills` | Account transaction history |
| Get Funding Bills | POST | `/api/v2/account/fundingBills` | Funding account history |
| Get Transfer Records | GET | `/api/v2/account/transferRecords` | Internal transfer history |
| Place Order | POST | `/api/v2/trade/orders` | Place a new order |
| Batch Place Orders | POST | `/api/v2/trade/batch-orders` | Place multiple orders |
| Cancel Order | POST | `/api/v2/trade/cancel-order` | Cancel by orderId or clientOid |
| Batch Cancel Orders | POST | `/api/v2/trade/cancel-batch-orders` | Cancel multiple orders |
| Cancel by Symbol | POST | `/api/v2/trade/cancel-symbol-order` | Cancel all for a symbol |
| Get Order Info | POST | `/api/v2/trade/orderInfo` | Query by orderId or clientOrderId |
| Get Open Orders | POST | `/api/v2/trade/open-orders` | List open/partially filled orders |
| Get History Orders | POST | `/api/v2/trade/history` | List historical orders |
| Get Fills | POST | `/api/v2/trade/fills` | List trade fills |

---

## 3. WebSocket API

### Endpoints
- **Public:** `wss://ws-spot.weex.com/v2/ws/public`
- **Private:** `wss://ws-spot.weex.com/v2/ws/private` (header auth required)

### Authentication (Private WS)
- Headers: `ACCESS-KEY`, `ACCESS-PASSPHRASE`, `ACCESS-TIMESTAMP`, `ACCESS-SIGN`
- Signature: HMAC-SHA256 of `timestamp + /v2/ws/private`, base64 encoded

### Subscription Example
```json
{"event": "subscribe", "channel": "orders"}
```

### Channels
| Channel | Description |
|---------|-------------|
| ticker.{symbol} | Real-time ticker updates |
| depth.{symbol}.{level} | Order book depth (15/200 levels) |
| trades.{symbol} | Public trade stream |
| kline.LAST_PRICE.{symbol}.{interval} | Candlestick data |
| account | Account balance updates (private) |
| orders | Order status updates (private) |
| fill | Trade fill updates (private) |

### Heartbeat
- Server sends: `{ "event": "ping", "time": <timestamp> }`
- Client must reply: `{ "event": "pong", "time": <timestamp> }`

---

## 4. Trading Pair Format
- All REST and WS endpoints use symbols like `BTCUSDT_SPBL` (case-sensitive, must match `/products` list)
- Hummingbot strategies should use this format for WEEX

---

## 5. Order Types & Parameters
- `side`: `buy` or `sell`
- `orderType`: `limit` or `market`
- `force`: `normal`, `postOnly`, `fok`, `ioc`
- `price`: required for limit orders
- `quantity`: base asset amount
- `clientOrderId`: user-defined, for idempotency

---

## 6. Error Codes
- 40001: Header "ACCESS_KEY" is required
- 40002: Header "ACCESS_SIGN" is required
- 40003: Header "ACCESS_TIMESTAMP" is required
- 40005: Invalid ACCESS_TIMESTAMP
- 40006: Invalid ACCESS_KEY
- 40008: Request timestamp expired
- 40009: API verification failed
- 429: Too many requests (rate limit)
- 43006: Amount is less than the minimum order amount
- 43007: Amount exceeds maximum order amount
- 43011: The current order price cannot be lower than 0
- ... (see full docs for more)

---

## 7. Rate Limits
- Public endpoints: up to 20 requests per 2 seconds
- Private endpoints: see endpoint-specific weights (typically 2-10 per request)
- 429 error: back off and retry

---

## 8. Best Practices
- Always use the `/products` endpoint to get valid trading pairs
- Timestamps must be in ms and within 30s of server time
- Use correct case for symbols (all uppercase, e.g. `VCCUSDT_SPBL`)
- For order management, use `clientOrderId` for idempotency
- Handle all error codes and back off on 429
- For WebSocket, always respond to ping with pong

---

## 9. Support
- Email: support@weex.com
- Telegram: https://t.me/weex_group
- API Announcements: https://weexsupport.zendesk.com/hc/en-us

---

*This file is a summary of the official WEEX API documentation as of January 30, 2026. For the latest updates, always check the [WEEX API docs](https://www.weex.com/api-doc/spot/introduction/APIBriefIntroduction).*
