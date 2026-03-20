# Bithumb Exchange Connector

This connector integrates [Bithumb](https://www.bithumb.com) — South Korea's largest cryptocurrency exchange — with Hummingbot.

## Overview

| Property | Value |
|---|---|
| Exchange | Bithumb |
| Exchange type | Centralized (CEX) |
| Country | South Korea 🇰🇷 |
| API version | v1 |
| Supported order types | Limit, Market |
| Default payment currency | KRW |
| Default fees | 0.25% maker / 0.25% taker |
| REST API | `https://api.bithumb.com` |
| Public WebSocket | `wss://pubwss.bithumb.com/pub/ws` |
| API documentation | [Bithumb API Docs](https://apidocs.bithumb.com) |

---

## Features

- **Real-time order book** via Bithumb public WebSocket
- **Real-time trade feed** via Bithumb public WebSocket
- **Limit and market orders** (buy/sell)
- **Order cancellation**
- **Balance tracking** via REST polling
- **Order status tracking** via REST polling
- **Trade fill history** per order

> **Note:** Bithumb does not provide a private WebSocket API. Order and balance updates are handled through Hummingbot's built-in REST polling loop (every ~10 seconds).

---

## Prerequisites

1. Create an account at [bithumb.com](https://www.bithumb.com)
2. Go to **My Page → API Management** and create an API key pair
3. Enable the following permissions on your API key:
   - Order inquiry
   - Order placement
   - Order cancellation
   - Balance inquiry

---

## Configuration

### Step 1: Connect via Hummingbot CLI

```
>>> connect bithumb
```

You will be prompted to enter:

| Field | Description |
|---|---|
| `bithumb_api_key` | Your Bithumb API key |
| `bithumb_secret_key` | Your Bithumb secret key |

### Step 2: Verify connection

```
>>> balance
>>> status
```

---

## Supported Trading Pairs

All KRW and BTC base pairs listed on Bithumb are supported. Examples:

- `BTC-KRW`
- `ETH-KRW`
- `XRP-KRW`
- `SOL-KRW`
- `DOGE-KRW`

To use BTC-denominated pairs (e.g., `ETH-BTC`), configure `payment_currency="BTC"` when instantiating the connector programmatically.

---

## Using in a Strategy Script

```python
from hummingbot.connector.exchange.bithumb import BithumbExchange
from decimal import Decimal

connector = BithumbExchange(
    bithumb_api_key="YOUR_API_KEY",
    bithumb_secret_key="YOUR_SECRET_KEY",
    trading_pairs=["BTC-KRW", "ETH-KRW"],
    trading_required=True,
)
```

---

## Authentication Details

Bithumb uses **HMAC-SHA512** authentication for all private REST endpoints.

Each private request requires three HTTP headers:

| Header | Value |
|---|---|
| `Api-Key` | Your API key |
| `Api-Nonce` | Current timestamp in milliseconds |
| `Api-Sign` | `Base64(HMAC-SHA512(secret, endpoint + \0 + body + \0 + nonce))` |

All private endpoints use `POST` with `Content-Type: application/x-www-form-urlencoded`.

---

## API Endpoints Used

### Public (no authentication)

| Endpoint | Purpose |
|---|---|
| `GET /public/ticker/ALL_KRW` | Fetch all KRW trading pairs and prices |
| `GET /public/orderbook/{symbol}` | Order book snapshot |
| `GET /public/transaction_history/{symbol}` | Recent trade history |

### Private (HMAC-SHA512 required)

| Endpoint | Purpose |
|---|---|
| `POST /info/balance` | Account balances |
| `POST /info/order_detail` | Order status and fill details |
| `POST /trade/place` | Place a limit order |
| `POST /trade/cancel` | Cancel an order |
| `POST /trade/market_buy` | Place a market buy order |
| `POST /trade/market_sell` | Place a market sell order |

---

## WebSocket Channels

| Channel | Event type | Description |
|---|---|---|
| `orderbooksnapshot` | `orderbooksnapshot` | Full order book snapshot |
| `transaction` | `transaction` | Real-time trade feed |

Subscribe example payload:
```json
{"type": "orderbooksnapshot", "symbols": ["BTC_KRW", "ETH_KRW"]}
{"type": "transaction", "symbols": ["BTC_KRW", "ETH_KRW"]}
```

---

## Trading Rules

Bithumb does not expose per-pair min/max size constraints via its public API. The connector uses the following conservative defaults:

| Rule | Default |
|---|---|
| Min price increment | 1 KRW |
| Min base amount increment | 0.00000001 |
| Min notional size | 1,000 KRW |

---

## Known Limitations

| Limitation | Reason |
|---|---|
| No private WebSocket | Bithumb does not offer a private WebSocket stream; state is updated via REST polling |
| Polling interval | Order and balance state reflects approximately every 10 seconds |
| KRW-only by default | Other payment currencies (BTC) require explicit `payment_currency` configuration |

---

## File Structure

```
hummingbot/connector/exchange/bithumb/
├── __init__.py                           # Package export
├── bithumb_constants.py                  # API URLs, endpoints, rate limits, order states
├── bithumb_utils.py                      # Pydantic config model, default fees
├── bithumb_auth.py                       # HMAC-SHA512 authentication handler
├── bithumb_web_utils.py                  # URL builders, WebAssistantsFactory
├── bithumb_api_order_book_data_source.py # Order book REST + WebSocket handling
├── bithumb_api_user_stream_data_source.py# User stream (heartbeat / REST polling)
├── bithumb_exchange.py                   # Main exchange connector class
└── README.md                             # This file
```

---

## Contributing

Bug reports and pull requests are welcome. Please open an issue before submitting a large PR.

---

## Disclaimer

This connector is provided for informational and educational purposes. Cryptocurrency trading carries significant financial risk. Always test with small amounts before deploying any automated strategy with real funds.
