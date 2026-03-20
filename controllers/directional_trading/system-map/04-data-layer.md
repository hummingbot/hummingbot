# 04 — Data Layer (Client, Fair Value, Pyth, Price Tracker)

Full extraction from `limitless_client.py` (664 lines), `fair_value.py` (504 lines),
`pyth_client.py` (356 lines), `price_tracker.py` (363 lines).

---

## 1. LimitlessClient

Source: `scripts/limitless_client.py`

Extends `dr_manhattan.exchanges.limitless.Limitless` with public API access,
rate limiting, orderbook caching, and ATM market selection.

### Rate Limiter
```python
class TokenBucketLimiter:
    rate: float = 3.0          # tokens/sec sustained (Limitless allows ~3.3)
    burst: int = 3             # max burst capacity
    retry_429: int = 3         # auto-retry with exponential backoff

    def acquire():             # blocks until token available
    def on_429():              # record for stats
    def stats() -> dict:       # {total_waits, total_wait_secs, total_429s, rate, burst}
```

### RateLimitedSession
Wraps `requests.Session` — every HTTP call goes through `limiter.acquire()`.
Auto-retries 429 with `2^(attempt+1)` second backoff, up to `retry_429` attempts.

### LimitlessClient

```python
class LimitlessClient(Limitless):
    BASE_URL = "https://api.limitless.exchange"

    def __init__(config: dict):
        # Optional keys: private_key, api_key, rate_limit, rate_burst
        # API key → X-API-Key header
        # Private key → wallet auth for trading (via dr_manhattan)
        # Singleton pattern via get_client()

    # Orderbook cache: slug → (monotonic_ts, result), TTL 3.0s
    # Dead slug cache: slugs that 400'd (expired) → skip retrying
    # WebSocket cache: set via set_ws_cache(OrderbookCache) — instant, no HTTP
```

### Key Methods

#### `fetch_markets(params=None) -> list[Market]`
- Paginated GET `/markets/active` (PAGE_SIZE=25, sorted by ending_soon)
- Returns parsed Market objects

#### `fetch_orderbook(slug) -> dict | None`
```python
# Returns:
{
    "bid": float,          # best bid price
    "ask": float,          # best ask price
    "bid_depth": float,    # total USDC liquidity (bids) — sum(size)/1e6
    "ask_depth": float,    # total USDC liquidity (asks) — sum(size)/1e6
    "bids_levels": [{"price": float, "size": float}],  # all levels, size in USDC
    "asks_levels": [{"price": float, "size": float}],
}
```
Priority: WS cache → HTTP cache (3s TTL) → API call. Dead slugs (400) skipped.

#### `fetch_hourly_crypto(spot_prices, pyth_client, locked_markets, known_coins, max_expiry_minutes=360) -> dict`
Returns `{ticker: market_dict}` — one market per ticker (ATM selected).

**Pipeline:**
1. **Fast path**: If `locked_markets` has slug dicts → per-slug direct fetch (1 API call each). Falls back to full pagination if any slug fails.
2. **Full discovery**: Paginate `/markets/active`, collect ALL valid candidates per ticker
3. **ATM selection**: For each ticker, pick market closest to spot price (Pyth) or |yes_price - 0.50| fallback

**Filters:**
- Title regex: `$TICKER above $STRIKE on DATE`
- CLOB only (skip AMM)
- Expiry > now AND ≤ `hour_end + max_expiry_minutes`
- Sub-hourly markets filtered by `include_subhourly` flag (default: hourly only)

**Early termination**: Stop pagination when all `known_coins` found in candidates.

**Market dict structure:**
```python
{
    "coin": str,              # e.g. "BTC"
    "yes_price": float,       # 0-1
    "no_price": float,        # 0-1
    "strike": float,          # from openPrice metadata or title
    "market_id": str,
    "slug": str,
    "title": str,
    "expiry": datetime(UTC),
    "pyth_address": str,      # oracle feed ID
    "pyth_symbol": str,       # oracle symbol
    "expiration_ts": int,     # unix timestamp
    "max_spread": float,      # from market settings (default 0.035)
    "volume": float,          # formatted volume as float
}
```

#### `_atm_select_ticker(ticker, mkts, spots, best, dropped)`
- Static method, handles both hourly and sub-hourly filtering
- ATM distance: `|spot - strike| / spot` if spot known, else `|yes_price - 0.50|`
- Tie-break: earlier expiry wins
- Drops non-selected to `dropped` list for logging

#### Singleton
```python
_client = None
def get_client(private_key=None, api_key=None) -> LimitlessClient:
    # Creates once, returns same instance
```

---

## 2. Fair Value Model

Source: `scripts/fair_value.py`

Binary option pricing via Black-Scholes + mispricing statistics.

### Core Functions

#### `compute_model_prob(spot, strike, hours_to_expiry, hourly_vol) -> float`
```
P(S_T > K) = Φ(d2)
d2 = (ln(S/K) - (σ²/2)τ) / (σ√τ)

S = Pyth oracle spot price
K = market strike price
τ = hours to expiry
σ = hourly volatility
Φ = standard normal CDF via math.erf

Returns: probability in [0.001, 0.999]
Edge cases: vol=0 → binary (spot > strike → 1.0, else 0.0)
```

#### `compute_edge(model_prob, market_yes) -> float`
```
edge = model_prob - market_yes
edge > 0 → YES underpriced (BUY YES)
edge < 0 → YES overpriced (BUY NO)
```

#### `compute_hourly_volatility(deltas, interval_secs) -> float`
```
std = sqrt(variance(deltas))  # sample variance (n-1)
hourly_vol = std * sqrt(3600 / interval_secs)
Requires len(deltas) >= 5
```

#### `halflife_to_alpha(halflife_secs, interval_secs) -> float`
```
alpha = 1 - exp(-ln(2) * interval / halflife)
Clamped to [0.0001, 0.5]
Decouples smoothing from polling interval
```

### MispricingProfile (per-coin)

Tracks distribution of `model_prob - market_yes` over time.

```python
@dataclass
class MispricingProfile:
    mispricing_ema: float = 0.0        # EMA of (fair - market)
    mispricing_var_ema: float = 0.0    # EMA of (mispricing - ema)²
    mispricing_history: list           # last 100 raw values
    spot_price: float = 0.0
    model_prob: float = 0.0
    volatility: float = 0.0
    delta_history: list                # spot log returns (for min_vol_obs gate)
    last_spot: float = 0.0
    total_ticks: int = 0
    delta_ema: float = 0.0            # Welford online EMA of log returns
    delta_var_ema: float = 0.0        # Welford online variance
    vol_tick_count: int = 0
    _z_history: deque(maxlen=30)      # (timestamp, z_score) ring buffer

    @property mispricing_std -> sqrt(mispricing_var_ema)
```

#### `feed(model_prob, market_yes, spot, alpha, max_history=100, vol_ema_alpha=0.01)`
1. Compute `mispricing = model_prob - market_yes`
2. Track spot log returns: `delta = ln(spot / last_spot)`
3. Update Welford online variance: `delta_var_ema = (1-α)(delta_var_ema + α·d²)`
4. Update mispricing EMA: `ema += α · (mispricing - ema)`
5. Update mispricing variance: `var = (1-α)(var + α · diff²)`

#### `ema_hourly_volatility(interval_secs) -> float`
```
per_tick_std = sqrt(delta_var_ema)
hourly_vol = per_tick_std * sqrt(3600 / interval_secs)
```

#### `should_trade(min_history, z_threshold, min_mispricing, min_vol_obs) -> (bool, mispricing, z_score)`
**Gate hierarchy (ALL must pass):**
1. `total_ticks >= min_history`
2. `vol_tick_count >= min_vol_obs` (uses uncapped counter, NOT buffer length)
3. `mispricing_std > 0.001`
4. `|current_mispricing| >= min_mispricing`
5. `z_score = |current - ema| / std > z_threshold`

#### `edge_direction() -> "YES" | "NO" | None`
Current mispricing > 0 → YES (underpriced), < 0 → NO (overpriced)

#### `z_velocity(window_secs=5.0) -> float`
Rate of z-score change per second. Positive = divergence growing.

#### `conflicts_with(direction) -> bool` / `agrees_with(direction) -> bool`
Edge direction vs divergence signal agreement/conflict check.

### BtcImpliedProfile (per-coin)

BTC-implied mispricing: where the coin SHOULD be based on BTC movement.

```python
@dataclass
class BtcImpliedProfile:
    btc_return_ema: float = 0.0        # EMA of BTC log returns
    coin_return_ema: float = 0.0       # EMA of coin log returns
    btc_mispricing_ema: float = 0.0    # EMA of BTC-implied mispricing
    btc_mispricing_var_ema: float = 0.0
    btc_mispricing_history: list
    implied_spot: float = 0.0          # where coin should be if tracking BTC
    residual: float = 0.0             # beta * btc_return - coin_return
    btc_fair_prob: float = 0.0        # B-S from implied_spot
```

#### `feed(btc_spot, coin_spot, beta, strike, hours_left, vol, market_yes, return_alpha, mispricing_alpha, ...)`
1. Compute log returns: `btc_ret = ln(btc_spot / prev)`, `coin_ret = ln(coin_spot / prev)`
2. Update return EMAs: `btc_return_ema += α · (btc_ret - ema)`
3. Compute residual: `residual = beta * btc_return_ema - coin_return_ema`
4. Implied spot: `coin_spot * exp(residual)`
5. B-S fair prob from implied spot (reuses Spot Score's when residual ≈ 0)
6. BTC mispricing: `btc_fair_prob - market_yes`
7. Update mispricing EMA/variance (same Welford pattern)

#### `should_trade(min_history, z_threshold, min_mispricing) -> (bool, btc_mispricing, z_score)`
Same gate hierarchy as MispricingProfile.

#### `btc_direction() -> "YES" | "NO" | None`
Positive BTC mispricing → YES (coin should be higher), negative → NO.

---

## 3. PythClient

Source: `scripts/pyth_client.py`

Batch spot price fetcher from Pyth Network Hermes API with Binance fallback.

### PythClient

```python
class PythClient:
    hermes_url = "https://hermes.pyth.network/v2/updates/price/latest"
    cache_ttl = 3.0           # seconds
    timeout = (0.3, 0.7)      # (connect, read) — fast-fail for 1s tick loops

    # Circuit breaker: 2 consecutive failures → skip 10 ticks
    CB_FAIL_THRESHOLD = 2
    CB_SKIP_TICKS = 10

    # Fallback: retry Pyth every 50 ticks for Binance-routed coins
    PYTH_RETRY_INTERVAL = 50
```

#### `fetch_spot_prices(pyth_addresses: {ticker: feed_id}) -> {ticker: price_usd}`
1. Check cache (3s TTL)
2. Batch query Pyth: `GET /v2/updates/price/latest?ids[]=0x...` (all coins in one call)
3. Parse: `price = int(price_raw) * 10^expo`
4. On 404: route to Binance fallback (likely Chainlink feed IDs in pythAddress)
5. Circuit breaker on network errors: skip Pyth, route to Binance temporarily
6. Recovery: retry Pyth periodically, recover if working again

#### Binance Fallback
- `GET https://api.binance.com/api/v3/ticker/price?symbol={TICKER}USDT`
- Own circuit breaker (independent from Pyth)
- Unknown symbols cached and skipped

### PythFetcher (background daemon)

```python
class PythFetcher:
    # Daemon thread — non-blocking Pyth price fetching
    # Main loop calls get_prices() which returns instantly from cache
    # Background thread fetches continuously

    def start()                          # launch daemon thread
    def stop()                           # signal shutdown
    def update_addresses(addrs)          # update feed IDs from main thread
    def get_prices() -> {ticker: price}  # instant return from cache
    # Returns empty dict if stale (> 5.0s)
```

---

## 4. Price Tracker (Standalone Tool)

Source: `scripts/price_tracker.py`

Independent CLI tool — polls Limitless API, logs YES/NO prices to CSV, displays dashboard.
**NOT part of live trading** — used for data collection/analysis.

- Polls every N ms (configurable)
- Logs: timestamp, tick, coin, yes_price, no_price, yes_no_sum, strike, market_id, title
- ATM selection: picks market closest to |yes_price - 0.50| per ticker
- On exit: auto-runs `analyze_prices.py`

---

## 5. Utilities (Summary)

### alerts.py (1132 lines)
- Telegram notification formatting for trade events and eval summaries
- Two channels: Alerts thread (trade open/close), Status thread (eval/system)
- `TelegramAlerts` class used by trader for per-trade notifications
- `send_status(text)`, `send_eval_status(eval_type, analysis, recommender)` module functions
- Handles tier labels, param shortening, Optuna result formatting
- **NOT trading logic** — pure output formatting

### cross_arb_scanner.py (452 lines)
- Scans for cross-market arbitrage (YES+NO > 1.0 across different markets)
- Standalone CLI tool, not integrated into live trading

### analyze_bounds.py (438 lines) / analyze_prices.py (564 lines)
- Offline analysis tools for price CSVs
- Bound deviation, ATM tracking, arbitrage detection

### fetch_markets.py (136 lines)
- Simple market listing CLI

### recalc_pnl.py (142 lines)
- Recalculate PnL from trade CSVs (cleanup tool)

---

## 6. V2 Hummingbot Mapping

| Component | V2 Mapping | Notes |
|---|---|---|
| LimitlessClient | **Already replaced** by Hummingbot connector | `limitless_exchange.py` handles all API calls |
| fetch_hourly_crypto() | `ControllerBase.update_processed_data()` | Market discovery + ATM selection → controller method |
| fetch_orderbook() | Connector's order book data source | Already in `limitless_api_order_book_data_source.py` |
| TokenBucketLimiter | Connector's rate limiter | Already in `limitless_web_utils.py` |
| MispricingProfile | `ControllerBase.processed_data` | Per-coin state, updated each tick |
| BtcImpliedProfile | `ControllerBase.processed_data` | Per-coin state, updated each tick |
| compute_model_prob() | Controller utility function | Could be in `binary_options/fair_value.py` |
| PythClient/Fetcher | `MarketDataProvider` or controller | Spot price source — could use Hummingbot's candles or separate feed |
| ATM selection | Controller's `update_processed_data()` | Filter markets before generating executor actions |
| Alerts | Controller's `to_format_status()` + external | Dashboard display + optional Telegram integration |

**Key insight**: The fair value model (`compute_model_prob`, `MispricingProfile`, `BtcImpliedProfile`) is the **core signal engine**. It MUST move into the controller, not stay external. The client/API layer is already replaced by the Hummingbot connector.
