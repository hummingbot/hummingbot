# SPEC: Hummingbot Limitless CLOB Connector

## Goal

Create a Hummingbot V2 exchange connector at `hummingbot/connector/exchange/limitless/` in our fork at `/home/tiger/hummingbot/`. This connector wraps our existing `LimitlessConnector` class from `/home/tiger/.openclaw/workspace/skills/limitless-mm/scripts/connector.py`.

## Reference Implementation

Use `/home/tiger/hummingbot/hummingbot/connector/exchange/hyperliquid/` as the primary reference — it's the closest match (on-chain CLOB, EIP-712 signing, WebSocket orderbook).

## Files to Create

All files go in `/home/tiger/hummingbot/hummingbot/connector/exchange/limitless/`:

### 1. `__init__.py`
Empty init file.

### 2. `limitless_constants.py`
- Exchange name: `"limitless"`
- Domain: `"limitless"`
- Base REST URL: `https://api.limitless.exchange`
- Base WS URL: `wss://ws.limitless.exchange`
- Rate limits (conservative: 10 req/s)
- Order types: `[LIMIT]` (GTC only)

### 3. `limitless_auth.py`
- Extends Hummingbot's `AuthBase`
- Handles API key (`X-API-Key` header) + EIP-712 wallet signing for orders
- Constructor takes `api_key` and `private_key`
- No HMAC — Limitless uses API key for reads, EIP-712 for order signing

### 4. `limitless_utils.py`
- `CONSTANTS` reference
- Trading pair conversion: Hummingbot format `BTC-1H` ↔ Limitless market slug
- `TradingRule` construction from market data (min order size, price decimals, etc.)
- Trading fee schema (Limitless charges on fills)
- Connector config: `LimitlessConfigMap` with fields for `api_key`, `private_key`

### 5. `limitless_order_book.py`
- Extends `OrderBook` if needed, or use default
- Limitless orderbooks have TWO buy sides (BUY YES and BUY NO) — both cost USDC
- Need to map to Hummingbot's single bid/ask model

### 6. `limitless_api_order_book_data_source.py`
- Extends `OrderBookTrackerDataSource`
- Wraps our `LimitlessConnector`'s WebSocket orderbook streaming
- Methods: `_subscribe_channels()`, `_process_websocket_messages()`, `get_new_order_book()`
- Falls back to REST if WS stale (our connector already does this)

### 7. `limitless_api_user_stream_data_source.py`
- Extends `UserStreamTrackerDataSource`
- Tracks order fills, cancellations, balance changes
- Limitless SDK provides order status via REST polling (no user WS stream yet)
- Implement as polling-based initially

### 8. `limitless_exchange.py`
- **Main file** — extends `ExchangePyBase`
- This is the glue between Hummingbot's framework and our `LimitlessConnector`
- Key method mappings:

| Hummingbot method | Implementation |
|---|---|
| `_place_order()` | Call `connector.buy()` or `connector.sell()` |
| `_place_cancel()` | Call `connector.cancel()` |
| `_update_balances()` | Call `connector.get_balance()` |
| `_update_order_status()` | Call `connector.get_order_status()` for in-flight orders |
| `_format_trading_rules()` | Build from `connector.get_market()` data |
| `supported_order_types()` | Return `[OrderType.LIMIT]` |
| `name` / `domain` | `"limitless"` |
| `_create_order_book_data_source()` | Return our orderbook data source |
| `_create_user_stream_data_source()` | Return our user stream source |

### 9. `limitless_web_utils.py`
- HTTP helper utilities (if needed beyond what connector.py provides)

## Registration

After creating the connector files, register it in Hummingbot's connector discovery:
- Add to `hummingbot/connector/exchange/__init__.py` or relevant connector registry
- Check how Hyperliquid registers itself and follow the same pattern

## Trading Pair Convention

Limitless markets are prediction markets with slugs like `btc-above-85000-mar-16-2026-12pm`.
For Hummingbot, we map to: `{TICKER}-{TIMEFRAME}` format (e.g., `BTC-1H`).
The connector resolves these to actual active market slugs at runtime via `get_active_markets()`.

## Orderbook Mapping

Limitless has a unique orderbook structure:
- **BUY YES** book: bids to buy YES tokens (bullish)
- **BUY NO** book: bids to buy NO tokens (bearish)
- When YES + NO prices sum ≥ $1, the exchange mints via CTF split
- **Selling** requires owning tokens

For Hummingbot's bid/ask model:
- **Bids** = BUY YES orders (sorted high to low)
- **Asks** = 1 - BUY NO prices (synthetic asks, sorted low to high)
- This gives a standard orderbook view where bid < ask

## Dependencies

The connector needs access to our `LimitlessConnector` class. Options:
1. **Symlink** `connector.py` into the Hummingbot connector folder
2. **Copy** the file
3. **Add to Python path**

Recommendation: Symlink — keeps single source of truth in our workspace, changes propagate automatically.

Also needs packages in the `hummingbot` conda env:
- `limitless-sdk==1.0.3`
- `eth-account`
- `web3`

Install: `/opt/miniconda3/envs/hummingbot/bin/pip install limitless-sdk eth-account web3`

## Testing

After building:
1. Start Hummingbot: `cd /home/tiger/hummingbot && make run`
2. `connect limitless` → enter API key + private key
3. `balance` → should show USDC balance (~$4)
4. `markets` → should list active Limitless markets
5. `orderbook BTC-1H` → should show live orderbook

## Constraints

- Read the Hyperliquid connector thoroughly before coding — it's the template
- Read our existing `connector.py` (693 lines) — it has everything implemented
- Don't reinvent what our connector already does — wrap it
- GTC limit orders only (no market orders)
- Max order size safety cap from config
- All on Base L2 (chain ID 8453)

## Out of Scope (for this spec)

- Strategy/script — separate spec
- Market lifecycle management (rollover, expiry) — strategy layer concern
- Signal integration from limitless-recon — strategy layer concern
