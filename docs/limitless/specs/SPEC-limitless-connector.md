# SPEC: Limitless Exchange Connector

## Output
**File:** `skills/limitless-mm/scripts/connector.py`

## Goal

Build a standalone `LimitlessConnector` class that:
1. Works immediately as the core of a simple MM Python script
2. Maps cleanly to Hummingbot's `ExchangePyBase` interface for future integration

## Architecture

```
limitless-mm/
  scripts/
    connector.py          # LimitlessConnector class (this spec)
    mm_bot.py             # MM strategy that uses the connector (separate spec)
  config/
    mm_config.json        # Strategy params
```

**Dependencies:** `limitless-sdk`, `eth-account`, `web3`
**Python:** 3.9+ (async/await throughout)

## LimitlessConnector Class

### Constructor

```python
class LimitlessConnector:
    def __init__(
        self,
        api_key: str,           # lmts_... (or from LIMITLESS_API_KEY env)
        private_key: str,       # wallet private key for EIP-712 signing
        markets: list[str],     # list of market slugs to track
    )
```

Internally creates:
- `HttpClient` (from limitless-sdk)
- `MarketFetcher` (from limitless-sdk)
- `OrderClient` (from limitless-sdk)
- `WebSocketClient` (from limitless-sdk)
- `Account` (from eth-account)

### Core Methods (Hummingbot-compatible names)

#### Market Data

```python
async def start(self):
    """Initialize SDK clients, fetch market data, cache venues, start WS."""

async def stop(self):
    """Cancel all open orders, close WS, close HTTP client."""

async def get_order_book(self, market_slug: str) -> dict:
    """Return current orderbook: {bids: [{price, size}], asks: [{price, size}]}
    Uses WS cache, falls back to REST."""

async def get_mid_price(self, market_slug: str) -> float:
    """Return midpoint price from best bid/ask."""

async def get_best_bid_ask(self, market_slug: str) -> tuple[float, float]:
    """Return (best_bid, best_ask) prices."""
```

#### Trading

```python
async def buy(
    self,
    market_slug: str,
    price: float,           # price per share in dollars (0.01-0.99)
    size: float,            # number of shares
    order_type: str = "GTC", # "GTC" or "FOK"
    token: str = "YES",     # "YES" or "NO"
) -> dict:
    """Place a buy order. Returns order result from API.
    Maps to: order_client.create_order(side=Side.BUY, ...)"""

async def sell(
    self,
    market_slug: str,
    price: float,
    size: float,
    order_type: str = "GTC",
    token: str = "YES",
) -> dict:
    """Place a sell order. Returns order result from API.
    Maps to: order_client.create_order(side=Side.SELL, ...)"""

async def cancel(self, order_id: str) -> dict:
    """Cancel a single order by ID.
    Maps to: order_client.cancel(order_id)"""

async def cancel_all(self, market_slug: str) -> dict:
    """Cancel all open orders on a market.
    Maps to: order_client.cancel_all(market_slug)"""
```

#### Account / Portfolio

```python
async def get_balance(self) -> dict:
    """Return USDC balance (available + locked).
    Uses: portfolio.get_positions() or dedicated balance endpoint."""

async def get_positions(self) -> list[dict]:
    """Return all open positions with PnL.
    Maps to: portfolio.get_positions()"""

async def get_open_orders(self, market_slug: str) -> list[dict]:
    """Return all open orders for a market.
    Uses: GET /orders/user/{marketSlug}"""

async def get_order_status(self, order_id: str) -> dict:
    """Return status of a specific order (open, filled, cancelled, etc.)."""
```

#### Market Discovery

```python
async def get_active_markets(self, ticker: str = None) -> list[dict]:
    """Return active markets, optionally filtered by ticker (BTC, ETH, etc.).
    Maps to: market_fetcher.get_active_markets()"""

async def get_market(self, market_slug: str) -> dict:
    """Return full market data including venue, positionIds, prices.
    Maps to: market_fetcher.get_market(slug)"""
```

### Internal State

```python
self._orders: dict[str, dict]       # tracked orders {order_id: order_data}
self._orderbooks: dict[str, dict]   # WS-updated orderbooks {slug: {bids, asks}}
self._markets: dict[str, dict]      # cached market data {slug: market_data}
self._venues: dict[str, str]        # cached venue addresses {slug: exchange_addr}
```

### WebSocket Integration

On `start()`:
1. Connect WS with auto-reconnect
2. Subscribe to all configured market slugs
3. On `orderbookUpdate` event → update `self._orderbooks`
4. `get_order_book()` reads from `self._orderbooks` (zero latency)
5. Falls back to REST if WS data is stale (>30s no update)

### Error Handling

- All methods raise `ConnectorError` on failure (wraps SDK's `APIError`)
- Network errors trigger automatic retry (SDK has built-in retry)
- Order failures logged with full context (market, price, size, error)

### Logging

- All order creates/cancels logged with timestamp
- WS connect/disconnect events logged
- Balance changes logged

## Hummingbot Mapping

When we build the Hummingbot connector later, this class becomes the inner engine:

| Hummingbot ExchangePyBase | LimitlessConnector |
|---|---|
| `_place_order()` | `buy()` / `sell()` |
| `_place_cancel()` | `cancel()` |
| `_create_order_book_data_source()` | WS orderbook stream |
| `_update_balances()` | `get_balance()` |
| `_update_order_status()` | `get_order_status()` |
| `_format_trading_rules()` | `get_market()` → extract rules |
| `supported_order_types()` | `[LIMIT]` (GTC) |
| `name` | `"limitless"` |
| `domain` | `"limitless"` |
| `trading_pairs` | market slugs |

### Hummingbot-specific additions needed later:
- `AuthBase` subclass (API key header injection)
- `OrderBookTrackerDataSource` subclass (wraps our WS)
- `UserStreamTrackerDataSource` subclass (order fill events)
- `TradingRule` construction from market data
- Symbol mapping (Hummingbot uses "BASE-QUOTE" format)
- `InFlightOrder` state management
- Rate limit rules

## Trading Pair Convention

Limitless doesn't have traditional "BASE-QUOTE" pairs. Markets are identified by slug.
For Hummingbot compatibility, we'll use: `{TICKER}-{TIMEFRAME}` (e.g., `BTC-1H`, `ETH-15M`)
The connector maps these to actual market slugs at runtime.

## Token Approvals (One-Time Setup)

Before first trade, need on-chain approvals on Base:
- USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) → `venue.exchange`
- Conditional Tokens (`0xC9c98965297Bc527861c898329Ee280632B76e18`) → `venue.exchange`

```python
async def approve_venue(self, market_slug: str):
    """One-time approval for trading on a venue. Requires ETH for gas."""
```

## Config

```json
{
  "api_key": "lmts_...",
  "private_key": "0x...",
  "markets": ["btc-above-*"],
  "rpc_url": "https://mainnet.base.org",
  "max_order_size_usd": 20.0,
  "log_file": "data/connector.log"
}
```

## Safety

- **Max order size**: configurable, default $20
- **Kill switch**: `cancel_all()` on all tracked markets on shutdown
- **No market orders initially**: GTC only (limit orders, no slippage surprise)
- **Paper mode**: log orders without submitting (for testing without capital)

## Implementation Order

1. Constructor + SDK client init
2. `start()` / `stop()` lifecycle
3. `get_order_book()` + WS streaming
4. `buy()` / `sell()` with GTC orders
5. `cancel()` / `cancel_all()`
6. `get_balance()` / `get_positions()` / `get_open_orders()`
7. `get_active_markets()` / `get_market()`
8. Paper mode
9. Token approval helper
10. Logging + error handling
