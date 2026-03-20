# 02 — Orchestration & Execution Layer — Full Code Extraction

**Files extracted:**
- `supervisor.py` (525 lines) — process orchestrator
- `trader.py` (1993 lines) — trade execution engine
- `ws_manager.py` (450 lines) — WebSocket orderbook streaming

---

## Table of Contents

1. [WebSocket Manager (ws_manager.py)](#1-websocket-manager)
2. [Trader (trader.py)](#2-trader)
3. [Supervisor (supervisor.py)](#3-supervisor)
4. [Data Flow](#4-data-flow)
5. [V2 Mapping](#5-v2-mapping)

---

## 1. WebSocket Manager

### 1.1 Constants

```python
WS_URL = "wss://ws.limitless.exchange"
WS_NAMESPACE = "/markets"
RESUB_INTERVAL = 60.0        # resubscribe keepalive (server drops idle subs)
STALE_RECONNECT_S = 120.0    # force reconnect if no OB updates for this long
```

### 1.2 OrderbookCache

Thread-safe cache storing orderbook snapshots from WebSocket. Data format matches `LimitlessClient.fetch_orderbook()` exactly: `{bid, ask, bid_depth, ask_depth, bids_levels, asks_levels}`.

```python
class OrderbookCache:
    def __init__(self, stale_seconds=30.0, hard_stale_seconds=300.0):
        self._data: Dict[str, Dict]           # slug → orderbook dict
        self._positions: Dict[str, Dict]      # market_address → position data
        self._lock: threading.Lock
        self._connected: bool = False
        self._subscribed_slugs: List[str] = []
        self._stale_seconds = stale_seconds   # from config: ws_orderbook_stale_seconds
        self._hard_stale_seconds = hard_stale_seconds  # ws_orderbook_hard_stale_seconds
        self._update_count: int = 0
        self._first_update_at: Optional[float] = None
        self._changed: threading.Event        # wakes tick loop on OB update
        self._slugs_seen: set = set()         # slugs that have received OB updates
```

**3-state validity model (`_is_valid`):**

| State | Condition | Valid? |
|-------|-----------|--------|
| FRESH | `age <= stale_seconds` | Always |
| QUIET | `stale < age <= hard_stale` | Only if connected AND subscribed |
| STALE | `age > hard_stale` OR not subscribed OR disconnected | Never |

**Key methods:**

- **`put(slug, ob)`** — Store OB snapshot. Adds `_updated_at = time.monotonic()`. Sets `_changed` event to wake tick loop immediately.
- **`get(slug) → Optional[Dict]`** — Returns OB dict if valid (per 3-state model), else None. Strips internal `_` keys.
- **`get_best_bid(slug) → Optional[float]`** — Best bid price (used as `yes_price` for signals). Returns None if stale/missing/zero.
- **`put_position(key, data)`** — Store position update from WS.
- **`get_positions() → Dict`** — All cached position data.
- **`update_subscriptions(slugs)`** — Replace subscription list (called by MarketSelector on discovery/evaluation).
- **`get_subscription_health() → dict`** — Compare subscribed vs actually receiving: `{subscribed, receiving, dead}`.
- **`reset_slugs_seen()`** — Clear seen-slugs tracker (on reconnect).
- **`wait_for_change(timeout) → bool`** — Block until OB update or timeout. Returns True if woken by update. Used by tick loop to sleep efficiently.
- **`get_book_quality(slug, depth_band=0.05) → Optional[(spread, near_depth_usd)]`** — Computes spread and near-depth within `depth_band` of midpoint. Used by Layer 2 market evaluation.
  ```
  near_depth = Σ(price × size) for all levels where |price - mid| <= depth_band
  ```
- **`stats() → Dict`** — Cache statistics: `{connected, cached_slugs, subscribed_slugs, update_count, avg_age_s, max_age_s}`.

### 1.3 OB Parsing

**`_parse_ob_levels(raw_levels) → List[Dict]`**

Handles two formats from the WS API:
- Format 1 (array-of-arrays): `[[price, size], ...]` → `[{"price": float, "size": float/1e6}, ...]`
- Format 2 (array-of-dicts): `[{"price": 0.72, "size": 1500000}, ...]` → same, `size / 1e6`

**Size normalization:** Raw WS sizes are in micro-tokens (×10⁶). Divided by 1e6 to get actual token count.

**`_build_ob_dict(bids_levels, asks_levels) → Dict`**

```python
{
    "bid": bids_levels[0]["price"],     # best bid
    "ask": asks_levels[0]["price"],     # best ask
    "bid_depth": sum(l["size"]),        # total bid depth in tokens
    "ask_depth": sum(l["size"]),        # total ask depth in tokens
    "bids_levels": bids_levels,         # [{price, size}, ...]
    "asks_levels": asks_levels,
}
```

### 1.4 LimitlessWSManager

Background daemon thread running Socket.IO async client.

```python
class LimitlessWSManager:
    def __init__(self, cache: OrderbookCache, api_key: Optional[str] = None):
        self._cache = cache
        self._api_key = api_key
        self._thread: Optional[threading.Thread]
        self._stop_event: threading.Event
        self._loop: Optional[asyncio.AbstractEventLoop]
        self._ob_format_logged: bool = False
```

**Lifecycle:**
- `start()` — Creates daemon thread (`limitless-ws`) running `_run()`.
- `stop()` — Sets stop event, joins thread (5s timeout).
- `_run()` — Creates new asyncio event loop, runs `_ws_loop()`, cleans up tasks on exit.

**Socket.IO Configuration:**
```python
sio = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=0,      # infinite
    reconnection_delay=1,
    reconnection_delay_max=5,
)
```
Transport: `websocket` only (no long-polling).

**Event Handlers:**

| Event | Action |
|-------|--------|
| `connect` | Set connected, subscribe to current slugs via `subscribe_market_prices`, reset slugs_seen, subscribe to positions (if authenticated) |
| `disconnect` | Set disconnected |
| `orderbookUpdate` | Parse slug from `data.marketSlug` or `data.slug`. Extract `data.orderbook.bids/asks` (or top-level). Parse levels, build OB dict, `cache.put()` |
| `positions` | Store position data keyed by `marketAddress` |
| `authenticated` | Log |
| `exception` | Log server error |

**Main WS Loop (`_ws_loop`):**

```
while not stopped:
    connect to WS_URL with namespace /markets
    while connected and not stopped:
        sleep 5s
        if subscriptions changed OR 60s since last resub:
            emit subscribe_market_prices with current slugs
        if no OB updates for 120s:
            force disconnect → outer loop reconnects
    on connection error: set disconnected, wait 5s, retry
```

**Headers:** `X-API-Key` sent if `api_key` provided.

---

## 2. Trader (trader.py)

### 2.1 Trade CSV Schema

```python
TRADE_CSV_FIELDS = [
    "timestamp", "coin", "signal_type", "direction", "market_id",
    "entry_strike", "entry_price", "exit_price", "size", "pnl", "hold_secs",
    "exit_reason", "stop_timeout", "tier",
    "entry_z_score", "entry_vol", "entry_confidence",
    "entry_correction_rate", "entry_lag_rate", "entry_lag_z_score",
    "entry_spread", "entry_mispricing", "entry_mispricing_std", "entry_decay_exp",
    "entry_path", "entry_spot_z_score", "entry_btc_z_score", "entry_btc_mispricing",
    "peak_pnl", "exit_btc_delta",
    "best_entry_price", "best_exit_price",
    "entry_z_velocity",
    "entry_exec_cost", "entry_edge_raw", "entry_edge_ratio",
]
```

### 2.2 Position Dataclass

```python
@dataclass
class Position:
    # Identity
    coin: str
    signal_type: str              # always "EDGE"
    direction: str                # "YES" or "NO"
    entry_price: float            # ask price at entry (walk-the-book fill)
    entry_timestamp: float        # time.monotonic()
    entry_utc: str                # ISO UTC
    market_id: str
    entry_strike: float
    event_id: int
    stop_timeout: float           # seconds — from coin's correction_time distribution

    # Sizing
    size: float = 0.0             # position size in dollars

    # Smart exit
    btc_direction: int = 0              # +1 or -1
    magnitude_threshold: float = 0.0    # take-profit threshold
    max_timeout: float = 0.0            # hard ceiling for adaptive timeout
    extensions: int = 0                 # number of timeout extensions applied
    market_expiry: float = 0.0          # UTC timestamp of market resolution
    entry_coin_price: float = 0.0       # YES price at entry (for trending check)
    btc_entry_price: float = 0.0        # BTC YES price at entry (legacy CSV)
    btc_entry_spot_price: float = 0.0   # BTC spot dollar price (for btc_reversal)
    edge_mispricing: float = 0.0        # abs(mispricing) at entry
    decay_exponent: float = 2.0         # exponential time decay exponent

    # Entry metadata (for backtesting/CSV)
    entry_z_score: float = 0.0
    entry_vol: float = 0.0
    entry_confidence: str = ""
    entry_correction_rate: float = 0.0
    entry_lag_rate: float = 0.0
    entry_lag_z_score: float = 0.0
    entry_spread: float = 0.0
    entry_mispricing_std: float = 0.0
    entry_decay_exp: float = 2.0
    entry_path: str = ""              # "COMBINED", "SPOT", "BTC"
    entry_spot_z_score: float = 0.0
    entry_btc_z_score: float = 0.0
    entry_btc_mispricing: float = 0.0

    # Roster
    roster_tier: str = "main"

    # Trailing stop
    stop_loss_pct: float = 0.30
    peak_pnl: float = 0.0
    trailing_active: bool = False
    stop_loss_confirm_ticks: int = 0
    stop_loss_breach_started_at: float = 0.0
    stop_loss_breach_elapsed_secs: float = 0.0

    # Walk-the-book
    best_entry_price: float = 0.0     # top-of-book entry
    best_exit_price: float = 0.0      # top-of-book exit

    # Z-velocity and execution cost
    entry_z_velocity: float = 0.0
    entry_exec_cost: float = 0.0
    entry_edge_raw: float = 0.0
    entry_edge_ratio: float = 0.0

    # Last known price (for rollover P&L)
    last_known_price: float = 0.0

    # Filled on close
    btc_exit_price: float = 0.0
    exit_price: float = 0.0
    exit_timestamp: float = 0.0
    exit_reason: str = ""
    pnl: float = 0.0
```

### 2.3 Helper Functions (module-level)

**`_percentile(data, pct) → float`** — Percentile from sorted data (linear interpolation, no numpy).

**`compute_stop_timeout(profile, signal_type, fallback_timeout, ema_multiplier=1.5) → float`**
- Always returns `fallback_timeout` (EDGE signals use model-based timeout, no correction time history).
- `fallback_timeout = market_duration_seconds × stop_fallback_pct` (typically 3600 × 0.0833 ≈ 300s).

**`compute_max_timeout(profile, signal_type, fallback_timeout, max_timeout_multiplier, max_hold_seconds=None) → float`**
- `max_timeout = fallback_timeout × max_timeout_multiplier`
- If `max_hold_seconds` set: `min(max_timeout, max_hold_seconds)`.

**`compute_timeout_extension(profile, signal_type, default_factor=1.5) → float`**
- Returns `default_factor` for EDGE.

**`compute_trailing_distance(profile, default_pct=0.3) → float`**
- If `len(profile.ratios) < 5`: return `default_pct`.
- Otherwise: `distance = 0.10 - (magnitude_consistency × 0.07)`, clamped [0.03, 0.10].
- High consistency → tight trail (0.03), low → wide (0.10).

**`compute_magnitude_threshold(profile, std_factor, fallback_baseline_pct, fallback_vol_pct, fallback_floor) → float`**

Take-profit threshold from coin's Type 2 magnitudes:
```
if len(type2.magnitudes) >= 3:
    threshold = mean(magnitudes) - std_factor × std(magnitudes)
    return max(threshold, 0.0)
elif baseline.magnitude > 0:
    return baseline.magnitude × fallback_baseline_pct
elif mispricing.volatility > 0:
    return volatility × fallback_vol_pct
else:
    return fallback_floor
```

**`dynamic_min_events(profile, signal_type, base, max_events) → int`** — Returns `base` for EDGE.

**`compute_position_size(profile, signal_type, base_size, t1_lag_weight, t1_follow_weight) → float`** — Returns `base_size` for EDGE.

**`should_trade(signal_type, profile, confidence, ...) → bool`** — Returns `True` only for EDGE.

### 2.4 PaperTrader Class

#### Constructor

```python
class PaperTrader:
    def __init__(self, output_dir, fallback_timeout=180, ema_multiplier=1.5,
                 capital=100, risk_per_trade=0.02, client=None, alerts=None,
                 min_btc_delta=10.0, freeze_minutes=5, close_minutes=2,
                 max_open_positions=5, max_total_exposure_pct=0.30, max_spread=0.15,
                 min_correction_rate=0.5, min_observations_full_size=5,
                 btc_reversal_multiplier=5.2405,
                 trailing_stop_trigger_pct=0.3, trailing_stop_distance_pct=0.225,
                 timeout_extension_factor=1.2, max_timeout_multiplier=2.905,
                 max_hold_seconds=None,
                 t1_lag_weight=0.4, t1_follow_weight=0.6,
                 magnitude_threshold_std_factor=1.0,
                 max_scale_in_entries=3, scale_in_cooldown_seconds=30,
                 scale_in_size_decay=0.7,
                 min_events_base=3, min_events_max=10,
                 edge_base_size_multiplier=1.5, edge_decay_exponent=2.15,
                 edge_stop_loss_pct=0.29, tp_squeeze_factor=0.75,
                 stop_loss_grace_secs=20,
                 tp_fallback_baseline_pct=0.5, tp_fallback_vol_pct=0.5,
                 tp_fallback_floor=0.01,
                 stop_loss_confirm_required=2, stop_loss_confirm_secs=0.0,
                 min_book_depth=100.0, max_depth_pct=1.0, signal_log_fn=None):
```

**Key state:**

```python
self.positions = []           # open positions
self.closed = []              # closed positions
self.base_size = capital × risk_per_trade
self.max_total_exposure = capital × max_total_exposure_pct
self.freeze_secs = freeze_minutes × 60
self.close_secs = close_minutes × 60

# Dynamically set (safety defaults, overridden by runtime.json):
self.edge_z_threshold = 1.5
self.coin_z_thresholds = {}     # per-coin: {COIN: threshold}
self.decay_exponents = {}       # per-coin: {COIN_edge_decay_exponent: val}
self.tp_min_roi = 0.08
self.fv_timeout_extension_factor = 1.3
self.max_timeout_extensions = 3
self.min_edge_profit_ratio = 0.35
self.min_stop_room_ratio = 1.5
self.protocol_fee_pct = 0.0
self.max_edge_mispricing = 0.10
self.min_edge_entry_price = 0.15
self.max_edge_entry_price = 0.93
self.min_position_size = 5.0
self.min_entry_vol = 0.0
self.entry_vol_range = (0.0, 0.2)

# Streak tracking
self._streak_tracker = {}       # coin → {"losses": int, "paused_until": float}
self._coin_last_exit_time = {}  # coin → monotonic timestamp of last close

# Circuit breaker (main trades only)
self.cb_max_losses = 99         # disabled by default
self.cb_window_secs = 300
self._cb_loss_times = deque()   # monotonic timestamps

# Runtime overrides storage
self._runtime_overrides = {}
self._edge_sigma_telemetry = {}

# CSV writer
self._csvf = open(output_dir/trades_TIMESTAMP.csv)
self._wr = csv.DictWriter(self._csvf, fieldnames=TRADE_CSV_FIELDS)
```

#### apply_runtime_overrides(overrides)

Hot-reloads ALL tunable parameters from runtime.json overrides dict. Every parameter listed in `_tunables` can be overridden. Sets instance attributes directly. Per-coin z-thresholds extracted from `{COIN}_edge_z_threshold` keys. Per-coin decay exponents from `{COIN}_{signal}_decay_exponent` keys.

#### _resolve_coin_param(coin, key, default)

Resolution order:
1. `{COIN}_{key}` in `_runtime_overrides`
2. `{key}` in `_runtime_overrides`
3. `default`

Used for ALL per-coin Optuna-tuned parameters.

#### _resolve_edge_reject_sigma(coin) → float

Resolution order:
1. `{COIN}_edge_reject_sigma` in runtime overrides
2. `param_space.edge_reject_sigma` midpoint: `(low + high) / 2`
3. Raises RuntimeError if missing

Logs on first use or change per coin.

#### _walk_book(levels, size_tokens) → (avg_fill_price, slippage, filled_tokens)

Static method. Walks orderbook levels (sorted best-first) for given token count:
```
for each level:
    take = min(remaining, level.size)
    cost += take × level.price
    filled += take
avg_fill = cost / filled
slippage = |avg_fill - levels[0].price|
```

#### _decay_squeeze(pos) → float

```
squeeze = (elapsed / max_timeout) ^ decay_exponent
```
Returns 0.0–1.0. Higher exponent = slower start, faster squeeze near timeout.

#### estimate_execution_cost(slug, direction, ref_size_usd=20.0) → Optional[Dict]

Lightweight cost estimation (no entry evaluation):
```python
tokens = ref_size_usd / entry_price
buy_slip = walk_book(buy_side_levels, tokens).slippage
sell_slip = walk_book(sell_side_levels, tokens).slippage
total = buy_slip + sell_slip
return {depth_yes_usd, depth_no_usd, depth_relevant_usd,
        buy_slip_est, sell_slip_est, total_exec_cost_est}
```

### 2.5 Entry Pipeline (on_signal)

```python
def on_signal(self, signal_type, coin, profile, btc_delta, prices, confidence,
              btc_price=0.0, roster_mult=1.0, roster_tier="main",
              edge_boost=1.0, edge_z_score=0.0, edge_max_size_mult=2.0,
              lag_z=0.0, btc_z_score=0.0, btc_mispricing=0.0,
              entry_path="", spot_z_score=0.0, z_velocity=0.0,
              btc_spot_price=0.0) → bool
```

**Direction:** `"YES"` if `btc_delta > 0`, `"NO"` if `btc_delta < 0`.

**Gate cascade (in order, first rejection stops):**

1. **should_trade** — only EDGE passes
2. **Hour-start blackout** — skip first 10s of each hour (minute=0, second<10)
3. **Resolve per-coin params** — all via `_resolve_coin_param`:
   - `edge_z_threshold`, `edge_stop_loss_pct`, `max_timeout_multiplier`, `edge_decay_exponent`
   - `tp_fallback_*`, `streak_cooldown`
4. **Position cap** — `len(real_positions) >= max_open_positions` (main tier only)
5. **Exposure cap** — `sum(real_sizes) >= max_total_exposure` (main tier only)
6. **Market freeze** — `secs_to_expiry < freeze_secs`
7. **Entry cooldown** — `time.monotonic() - last_exit_time < edge_cooldown_seconds` (per-coin)
8. **Scale-in check** — `_can_scale_in()`: max entries + cooldown between entries
9. **Signal type** — must be "EDGE"
10. **Orderbook fetch** — get real bid/ask from WS cache
11. **Spread check** — `ask - bid > max_spread`
12. **Payout ceiling** — `1.0 - entry_price < 0.02` (max profit < 2 cents)
13. **Mispricing reject (Nσ)** — per-path noise floor:
    - SPOT/COMBINED: `abs(mispricing) > min(edge_reject_sigma × mispricing_std, max_edge_mispricing)`
    - BTC: `abs(mispricing) > min(edge_reject_sigma × btc_mispricing_std, max_edge_mispricing)`
    - COMBINED also gates BTC leg independently
    - Requires ≥50 ticks for dynamic reject; fallback to `max_edge_mispricing`
14. **Entry price floor** — `entry_price < min_edge_entry_price` (deep OTM, B-S unreliable)
15. **Entry price ceiling** — `entry_price > max_edge_entry_price` (deep ITM, tiny upside)
16. **Streak cooldown** — per-coin losses count → pause period
17. **Circuit breaker** — account-wide loss count in time window (main only)
18. **Entry vol range** — `vol ∉ [vol_range_min, vol_range_max]` (per-coin Optuna)
19. **Z-threshold gate** — per entry path:
    - `SPOT` → `edge_z_score < edge_z_threshold`
    - `COMBINED` → `edge_z_score < combined_z_threshold`
    - `BTC` → `edge_z_score < btc_z_threshold`
20. **Z-max gate** — per entry path (upper tunnel bound):
    - `edge_z_score > {path}_z_max`
    - COMBINED: enforces per-leg upper caps on `spot_z` and `btc_z` individually
21. **Compute stop/max timeout** — `fallback_timeout`, `fallback × max_timeout_multiplier`
22. **EDGE sizing:**
    ```
    edge_mult = min(1.0 + (edge_z_score - 1.0) × 0.5, edge_max_size_mult)
    size = base_size × edge_base_size_multiplier × max(edge_mult, 1.0)
    size *= roster_mult
    ```
    Scale-in decay: `size *= scale_in_size_decay ^ existing_entries`
    Observation ramp: `size *= (btc_move_seen / min_observations_full_size)` if low obs
    Exposure cap: `size = min(size, remaining_exposure)` (main only)
23. **Book depth gate** — `relevant_depth < min_book_depth`
24. **Walk both sides of orderbook:**
    ```
    size_tokens = size / entry_price
    avg_fill, buy_slip = walk_book(buy_levels, size_tokens)
    _, sell_slip = walk_book(sell_levels, size_tokens)
    total_slippage = buy_slip + sell_slip + spread
    ```
25. **Edge/max_profit ratio gate:**
    ```
    edge = abs(mispricing)
    max_profit = 1.0 - fill_price
    edge = min(edge, max_profit)
    ratio = edge / max_profit
    reject if ratio < min_edge_profit_ratio OR ratio > param_space.high
    ```
26. **Override entry_price with walked fill price** (real cost, not top-of-book)
27. **Final fill-aware edge/max_profit re-check** (with fill price)
28. **Stop-room/slippage gate:**
    ```
    stop_room = entry_price × stop_loss_pct
    survive_ratio = stop_room / total_slippage
    reject if survive_ratio < min_stop_room_ratio
    ```
29. **Minimum position size** — `size < min_position_size`
30. **Compute magnitude threshold** (for TP)
31. **Create Position** — all fields populated from signal + resolved params
32. **Telegram alert** — `alerts.trade_opened(...)`
33. **Persist execution diagnostics** to `_last_execution_diag` and Position fields

### 2.6 Exit Logic (check_positions)

Called every tick by divergence_tracker. Smart exit with 7 conditions, first wins.

```python
def check_positions(self, all_prices, btc_delta=0.0, profiles=None, btc_spot_price=0.0):
```

**Per-position per-tick:**

1. Compute `upnl = _unrealized_pnl(pos, prices)` once per tick
2. Track `peak_pnl = max(peak_pnl, upnl)`
3. Track `last_known_price` (for rollover)

**Exit priority:**

#### 1a. Market Expiry
```
if market_expiry > 0 and secs_left < close_secs: → close("market_expiry")
```

#### 1b. Market Rollover (safety net)
```
if current_market_id != pos.market_id: → close("market_rollover")
```
Uses `last_known_price` as exit price (wrong market's OB would give wrong price).

#### 2. BTC Reversal (`_btc_reversed`)
```python
def _btc_reversed(pos, btc_delta, btc_spot_price) → bool:
    if elapsed < stop_loss_grace_secs: return False
    net_btc_delta = btc_spot_price - pos.btc_entry_spot_price
    reversal_threshold = min_btc_delta × _resolve_coin_param(coin, "btc_reversal_multiplier")
    if |net_btc_delta| < reversal_threshold: return False
    if pos.direction == "YES": return net_btc_delta < -reversal_threshold
    else: return net_btc_delta > reversal_threshold
```
Uses cumulative BTC **spot dollar** movement (not single-tick, not YES price).

#### 2b. Hard Stop Loss
```
max_loss = -(pos.size × pos.stop_loss_pct)
if upnl < max_loss:
    start breach timer
    increment breach ticks
    if stop_loss_confirm_secs > 0:
        close when both breach_secs >= confirm_secs AND ticks >= confirm_required
    else:
        close when ticks >= confirm_required (legacy tick mode)
else:
    reset breach timer + counter
```
Grace period: `stop_loss_grace_secs` after entry before SL activates.

Per-coin: `stop_loss_pct` set at entry from `_resolve_coin_param("edge_stop_loss_pct")`.

#### 2c. Arm Trailing Stop (`_try_arm_trailing`)
```python
trigger = pos.size × _resolve_coin_param(coin, "trailing_stop_trigger_pct")
if upnl >= trigger and not trailing_active:
    pos.trailing_active = True
```
Runs BEFORE TP check so `trailing_active` gates TP (lets winners run).

#### 3. Take Profit (`_take_profit_reached`)
**Only fires if `not pos.trailing_active`** (trailing stop takes over).
```python
squeeze = _decay_squeeze(pos)  # 0→1 over position lifetime
squeeze_factor = max(1.0 - squeeze × tp_squeeze_factor, 0.0)
min_profit = pos.size × tp_min_roi × squeeze_factor
return upnl >= min_profit
```
Both `tp_min_roi` and `tp_squeeze_factor` are per-coin Optuna-tuned.

At max_timeout: `squeeze_factor → 0`, any positive P&L accepted.

#### 4. Trailing Stop (`_trailing_stop_hit`)
```python
if not trailing_active: return False
drawdown = peak_pnl - upnl
dist_pct = _resolve_coin_param(coin, "trailing_stop_distance_pct")
trail_distance = peak_pnl × dist_pct
return drawdown >= trail_distance
```
If profile available: `dist_pct = compute_trailing_distance(profile, coin_dist_pct)` adapts to magnitude consistency.

#### 5. Adaptive Timeout
```python
if elapsed >= stop_timeout:
    can_extend = stop_timeout < max_timeout AND extensions < max_timeout_extensions
    if can_extend and _coin_trending(pos, prices):     # 5a behavioral
        stop_timeout = min(stop_timeout × timeout_extension_factor, max_timeout)
        extensions += 1
    elif can_extend and _fair_value_supports(pos, profile):  # 5b mathematical
        stop_timeout = min(stop_timeout × fv_timeout_extension_factor, max_timeout)
        extensions += 1
    else:                                                # 5c close
        close("timeout")
```

**`_coin_trending(pos, prices) → bool`:**
```
coin_delta = current_yes - entry_coin_price
YES: trending if coin_delta > 0
NO: trending if coin_delta < 0
```

**`_fair_value_supports(pos, profile) → bool`:**
```
if no profile or no mispricing or < 10 ticks: return False
return mispricing.edge_direction() == pos.direction
```

### 2.7 Unrealized P&L (`_unrealized_pnl`)

```python
def _unrealized_pnl(pos, prices) → float:
    # Walk orderbook for realistic exit price
    slug = prices.get("slug")
    ob = _fetch_ob(slug)
    if ob:
        if YES: exit_price = walk_book(bids, size_tokens).avg_fill or bid or yes_price
        if NO: exit_price = 1 - walk_book(asks, size_tokens).avg_fill or 1-ask or no_price
    else:
        exit_price = yes_price or no_price

    num_tokens = size / entry_price
    if protocol_fee_pct > 0:
        return num_tokens × (exit_price × (1-fee) - entry_price × (1+fee))
    return (exit_price - entry_price) × num_tokens
```

### 2.8 Position Close (`_close_position`)

```python
def _close_position(pos, prices, reason):
    # Record exit time for per-coin cooldown
    _coin_last_exit_time[coin] = time.monotonic()

    # Price determination:
    if reason == "market_rollover":
        exit_price = last_known_price or entry_price  # DON'T use new market's OB
    elif prices:
        walk orderbook (same logic as _unrealized_pnl)
    else:
        exit_price = entry_price  # no data = flat

    # P&L:
    num_tokens = size / entry_price
    if fee > 0:
        pnl = num_tokens × (exit_price × (1-fee) - entry_price × (1+fee))
    else:
        pnl = num_tokens × (exit_price - entry_price)

    # Write CSV row
    # Update streak tracker
    if pnl < 0:
        streak_tracker[coin].losses += 1
        if losses >= eff_streak_max: pause for eff_streak_pause seconds
        if main tier: append to circuit_breaker_loss_times
    else:
        streak_tracker[coin] = {losses: 0, paused_until: 0}

    # Telegram alert
    alerts.trade_closed(...)
```

### 2.9 Summary & Session Stats

**`summary(event_count, tick_count) → dict`:**
- Closes all remaining open positions with reason "shutdown"
- Sends Telegram final summary
- Prints per-tier summary (MAIN/PROBATION/REHAB)
- Prints per-coin quality table (trades, WR%, P&L, avg z-score, paths)
- Prints entry path breakdown (COMBINED/SPOT/BTC)
- Prints exit reason distribution
- Returns `{total, wins, losses, win_rate, total_pnl, avg_pnl, avg_hold_secs, by_type, log_path}`

**`get_session_stats() → dict`** — Per-coin `{wins, losses, pnl}` from closed positions. Used by ticker display.

---

## 3. Supervisor (supervisor.py)

### 3.1 File Paths

```python
SKILL_DIR = Path(__file__).resolve().parent.parent  # limitless-recon/
SCRIPTS_DIR = SKILL_DIR / "scripts"
DATA_DIR = SKILL_DIR / "data"
RUNTIME_PATH = DATA_DIR / "runtime.json"
LOG_PATH = DATA_DIR / "supervisor.log"
PID_PATH = DATA_DIR / "supervisor.pid"
CONFIG_PATH = SKILL_DIR / "config.json"
```

### 3.2 PID Locking

**`acquire_lock()`** — Write PID to `supervisor.pid`. If file exists, check if old PID is actually a supervisor (reads `/proc/{pid}/cmdline` for "supervisor.py"). If running supervisor found → exit. If stale → take over.

**`release_lock()`** — Remove PID file only if it contains our PID. Registered via `atexit`.

**`_is_supervisor_process(pid) → bool`** — Reads `/proc/{pid}/cmdline`, returns True if "supervisor.py" found.

### 3.3 Tracker Management

**`start_tracker(trade_mode, extra_args) → Popen`**
```
cmd = [python, divergence_tracker.py, --trade, {paper|live}] + extra_args
stdout+stderr → supervisor.log (merged)
```

**`stop_tracker(proc, timeout=30)`**
1. SIGTERM
2. Wait `timeout` seconds
3. If still alive → SIGKILL → wait 5s

### 3.4 Evaluator Management

**`start_cold_eval(trade_mode) → Popen`**
- Runs `cold_eval_parallel.sh` which splits coins across 2 evaluator processes
- Background, fire-and-forget
- Sends merged Telegram notification

**`start_hot_eval(trade_mode, eval_depth="quick", notify=True) → Popen`**
```
cmd = [python, evaluator.py, --apply, --all, --eval-type, hot,
       --eval-depth, {quick|full}, --trade, {paper|live}]
if notify: cmd.append("--notify")
```
Hot evals: heuristic tuning only (no Optuna, no roster mode changes).

**`check_hot_eval(proc) → Optional[Popen]`** — Poll completion, return None when done.

### 3.5 Data Cleanup

**`cleanup_old_data()`** — Runs at startup:

| Target | Retention | Destination |
|--------|-----------|-------------|
| `supervisor.log` lines | `trade_lookback_hours` (default 24) | `data/archive/supervisor.log.archived` |
| `divergence_*.csv`, `trades_*.csv` | `trade_lookback_hours` | `data/archive/` (moved) |
| `tick_snapshots_*.csv` | `snapshot_lookback_hours` (default 2) | `data/archive/` (moved) |

Timestamps parsed from filenames: `_{YYYY-MM-DD}_{HHMMSS}.` pattern.

### 3.6 Main Loop

```python
def main():
    # Parse args: --stop, --trade, --no-eval, --no-hot-eval, --watchdog-interval, --tracker-args
    if args.stop: stop_supervisor()  # sends SIGTERM to running supervisor, waits 60s

    acquire_lock()
    cleanup_old_data()
    start_tracker(trade_mode)

    # Signal handlers: SIGINT/SIGTERM → set running=False
    # Schedule state:
    HOT_EVAL_MINUTES = {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 59}
    NOTIFY_MINUTES = {10, 20, 30, 40, 50, 59}
```

**Main loop (1s tick):**

| Trigger | Action |
|---------|--------|
| Every 5 min (`HOT_EVAL_MINUTES`) | Hot eval (quick). Telegram summary only at `NOTIFY_MINUTES` |
| `:03` then every `cold_eval_interval_minutes` | Cold eval (parallel, background). Interval read from runtime.json each cycle |
| `:00:10` each hour | SIGUSR1 to tracker → forces market rediscovery |
| Every `watchdog_interval` min | Check if tracker crashed → auto-restart |

**Cold eval timing:** Starts at `:03` (delayed from `:01` so tracker's 60s ban confirmation window completes first). Interval from `runtime.json["cold_eval_interval_minutes"]` (default 15, currently 30).

**Watchdog:** If tracker has exited (poll() returns), restart immediately. Sends Telegram alert on crash (non-zero exit code).

### 3.7 Shutdown Sequence

```
1. Terminate running hot eval (SIGTERM, wait 10s, SIGKILL if needed)
2. stop_tracker (SIGTERM → 30s → SIGKILL)
3. release_lock
4. Telegram: "Supervisor exited"
```

### 3.8 Stop Command

`supervisor.py --stop`:
1. Read PID from `supervisor.pid`
2. Verify it's actually a supervisor process
3. Send SIGTERM
4. Wait up to 60s for clean shutdown
5. If still running after 60s → print "try kill -9"

---

## 4. Data Flow

### 4.1 Signal → Order Pipeline

```
divergence_tracker.py (tick loop)
  │
  ├── Pyth spot prices → Black-Scholes → MispricingProfile → z-score
  ├── BtcImpliedProfile → btc_z_score
  │
  └── trader.on_signal(
        signal_type="EDGE", coin, profile,
        btc_delta=mispricing,      # positive = buy YES
        prices={yes_price, no_price, slug, market_id, expiry, strike},
        confidence, btc_price, roster_mult, roster_tier,
        edge_z_score, btc_z_score, btc_mispricing,
        entry_path, spot_z_score, z_velocity, btc_spot_price
      )
      │
      ├── 30 gate cascade (see §2.5)
      │
      ├── Walk orderbook (WS cache → asks/bids levels)
      │   ├── Buy side: avg_fill, buy_slippage
      │   └── Sell side: projected sell_slippage
      │
      ├── Create Position dataclass
      └── Telegram alert
```

### 4.2 Orderbook Data Flow

```
Limitless WS API
  │ (wss://ws.limitless.exchange/markets)
  │
  └── orderbookUpdate events
      │
      └── LimitlessWSManager._ws_loop
          │ (background daemon thread)
          │
          ├── _parse_ob_levels (normalize formats)
          ├── _build_ob_dict (match HTTP format)
          └── OrderbookCache.put(slug, ob)
              │
              ├── cache._changed.set()  →  tick loop wakes
              │
              └── consumers:
                  ├── MarketSelector.build_cd()   → yes_price via get_best_bid()
                  ├── MarketSelector.evaluate()   → get_book_quality() for scoring
                  ├── trader.on_signal()           → _fetch_ob() for spread/depth/slippage
                  ├── trader._unrealized_pnl()     → walk book for exit price
                  ├── trader._close_position()     → walk book for fill price
                  └── trader.estimate_execution_cost()  → lightweight depth/slippage
```

### 4.3 Position State

All position state is **in-memory** (Python lists `self.positions`, `self.closed`). No persistence between restarts — all positions close with reason "shutdown" on exit.

On shutdown: `summary()` force-closes remaining positions at last known prices, writes final CSV rows.

### 4.4 Config Reads

| File | When | What reads it |
|------|------|---------------|
| `config.json` | Startup only | Tracker, supervisor (`_load_config`) |
| `runtime.json` | stat() every 30s by `RuntimeConfig.check()` | Tracker → `trader.apply_runtime_overrides()`, supervisor (cold_eval_interval), evaluator |
| `runtime.json` → `coins` block | Hot-reload | `CoinRoster`, `RuntimeConfig` → per-coin params become `{COIN}_{key}` overrides |

### 4.5 Logging

| Output | Path | Format |
|--------|------|--------|
| Trade CSV | `data/trades_{timestamp}.csv` | One row per closed position (TRADE_CSV_FIELDS) |
| Supervisor log | `data/supervisor.log` | `[YYYY-MM-DD HH:MM:SS UTC] message` — includes tracker stdout/stderr |
| Ticker display | `data/ticker_display` | Plain text grid (written by TickerDisplay for remote viewing) |
| Tick snapshots | `data/tick_snapshots_{timestamp}.csv` | Per-tick per-coin (from divergence_tracker) |
| Event CSV | `data/divergence_{timestamp}.csv` | Per-event (from divergence_tracker) |

---

## 5. V2 Mapping

### 5.1 supervisor.py → Not directly mapped

The supervisor is a process manager, not trading logic. In V2:
- **Tracker lifecycle** → Hummingbot's `StrategyV2Base` with its built-in async control loop (`RunnableBase`)
- **Evaluator scheduling** → External service or controller's `update_processed_data()` running Optuna periodically
- **Watchdog** → Hummingbot has its own process management
- **SIGUSR1 market refresh** → Controller's `update_processed_data()` detects hour boundaries
- **Data cleanup** → DB-backed persistence, no CSV archival needed

### 5.2 trader.py → ControllerBase + PositionExecutor

| Current Component | V2 Equivalent |
|-------------------|---------------|
| `PaperTrader.on_signal()` (30 gate cascade) | `ControllerBase.determine_executor_actions()` |
| `Position` dataclass | `PositionExecutorConfig` + executor state |
| `positions[]` / `closed[]` | `ExecutorOrchestrator.active_executors` / `MarketsRecorder` DB |
| `_unrealized_pnl()` walk-the-book | `PositionExecutor.net_pnl_quote` (connector handles fills) |
| `apply_runtime_overrides()` | `ControllerConfigBase` updatable fields |

**Gate cascade → `determine_executor_actions()`:**
```python
def determine_executor_actions(self) -> List[ExecutorAction]:
    actions = []
    for coin, signal in self.processed_data["signals"].items():
        if not self._passes_all_gates(coin, signal):
            continue
        actions.append(CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=PositionExecutorConfig(
                trading_pair=f"{coin}-USDC",
                connector_name="limitless",
                side=TradeType.BUY if signal.direction == "YES" else TradeType.SELL,
                amount=Decimal(str(self._compute_size(coin, signal))),
                triple_barrier_config=TripleBarrierConfig(
                    stop_loss=Decimal(str(signal.stop_loss_pct)),
                    take_profit=None,  # Custom TP via controller (squeeze-based)
                    time_limit=int(signal.stop_timeout),
                    trailing_stop=TrailingStop(
                        activation_price=Decimal(str(signal.trailing_trigger)),
                        trailing_delta=Decimal(str(signal.trailing_distance)),
                    ),
                ),
            ),
        ))
    return actions
```

**Custom exit logic not native to V2:**

These require a **custom executor** (subclass of `PositionExecutor`):

| Custom Exit | Why Not Native |
|-------------|----------------|
| BTC reversal | Cross-asset logic — needs BTC spot price from another data source |
| TP squeeze (decay-based ROI) | TP in V2 is fixed percentage, not time-decaying |
| Fair value timeout extension | V2 time_limit is fixed, no extensions |
| Trending timeout extension | Same |
| Stop-loss confirmation window | V2 stop loss is immediate, no tick/time confirmation |
| Market rollover handling | Binary options market lifecycle doesn't exist in V2 |

### 5.3 ws_manager.py → Connector Data Source

| Current | V2 Equivalent |
|---------|---------------|
| `LimitlessWSManager` | `ConnectorBase._user_stream_tracker` + `_order_book_tracker` |
| `OrderbookCache` | `ConnectorBase.get_order_book()` / `get_price()` |
| `orderbookUpdate` events | Connector's `OrderBookDataSource._parse_order_book_snapshot_message()` |
| `positions` events | Connector's `UserStreamDataSource._parse_position_message()` |
| WS reconnection | Built into Hummingbot's `WebSocketAssistant` |
| 60s keepalive resubscription | Connector's WS ping/pong mechanism |

### 5.4 Key Architecture Differences

| Current System | V2 |
|----------------|-----|
| Single process (tracker + trader in-process) | Multi-component (strategy → controller → executor) |
| Walk-the-book for fill estimation | Connector handles real fills with events |
| Paper trading (simulated fills) | Paper trading connector provided by Hummingbot |
| CSV logging | DB persistence via `MarketsRecorder` |
| runtime.json hot-reload | `ControllerConfigBase` updatable fields + YAML |
| Evaluator as separate process | Could be part of controller or external service |
| Per-coin Optuna in evaluator | External optimization or V2 backtesting framework |

### 5.5 State Migration Requirements

| Current State | V2 Location |
|---------------|-------------|
| `self.positions[]` | `ExecutorOrchestrator.active_executors[controller_id]` |
| `self.closed[]` | `MarketsRecorder` DB |
| `self._streak_tracker` | Controller's `processed_data` |
| `self._coin_last_exit_time` | Controller's `processed_data` |
| `self._cb_loss_times` | Controller's `processed_data` |
| Per-coin Optuna params | Controller YAML config (updatable) |
| Walk-the-book slippage | Connector's order execution (real fills) |
| `peak_pnl` tracking | Custom executor state |
| `trailing_active` | `TripleBarrierConfig.trailing_stop` (native) |

### 5.6 Custom Executor Specification

A `LimitlessBinaryExecutor` extending `PositionExecutor` would need:

```python
class LimitlessBinaryExecutorConfig(PositionExecutorConfig):
    type: Literal["limitless_binary"]
    # Binary options specific
    market_expiry: float
    btc_entry_spot_price: float
    stop_loss_confirm_secs: float
    stop_loss_confirm_required: int
    stop_loss_grace_secs: float
    decay_exponent: float
    tp_min_roi: Decimal
    tp_squeeze_factor: Decimal
    fv_timeout_extension_factor: float
    max_timeout_extensions: int
    btc_reversal_multiplier: float
    min_btc_delta: float

class LimitlessBinaryExecutor(PositionExecutor):
    async def control_barriers(self):
        # 1. Market expiry → early_stop
        # 2. BTC reversal (needs external BTC price feed)
        # 3. Confirmed stop loss (time + tick window)
        # 4. Arm trailing (modifies TP behavior)
        # 5. Squeeze-based TP (time-decaying ROI threshold)
        # 6. Trailing stop (native, but with adaptive distance)
        # 7. Timeout with extensions (trending + fair value)
```

---

## Appendix: Key Formulas

### P&L Calculation
```
num_tokens = size / entry_price
if fee > 0:
    pnl = num_tokens × (exit_price × (1 - fee) - entry_price × (1 + fee))
else:
    pnl = num_tokens × (exit_price - entry_price)
```
Where `fee = protocol_fee_pct` (currently 0.0025 = 0.25%).

### EDGE Sizing
```
edge_mult = min(1.0 + (z_score - 1.0) × 0.5, edge_max_size_mult)
size = base_size × edge_base_size_multiplier × max(edge_mult, 1.0) × roster_mult
size × scale_in_size_decay ^ existing_entries  (for scale-ins)
size × (btc_move_seen / min_observations_full_size)  (if low observations)
```

### TP Squeeze
```
squeeze = (elapsed / max_timeout) ^ decay_exponent
squeeze_factor = max(1.0 - squeeze × tp_squeeze_factor, 0.0)
min_profit = size × tp_min_roi × squeeze_factor
fire when upnl >= min_profit
```

### BTC Reversal
```
net_btc_delta = current_btc_spot - entry_btc_spot
reversal_threshold = min_btc_delta × btc_reversal_multiplier
YES position: reversed if net_btc_delta < -reversal_threshold
NO position:  reversed if net_btc_delta > +reversal_threshold
```

### Trailing Stop
```
arm when: upnl >= size × trailing_stop_trigger_pct
fire when: (peak_pnl - upnl) >= peak_pnl × trailing_stop_distance_pct
```

### Walk-the-Book
```
for each level (best-first):
    take = min(remaining_tokens, level.size)
    cost += take × level.price
avg_fill = cost / filled
slippage = |avg_fill - best_price|
total_exec_cost = buy_slippage + sell_slippage + spread
```

### Mispricing Reject (Nσ Gate)
```
threshold = min(edge_reject_sigma × mispricing_std, max_edge_mispricing)
reject if |mispricing| > threshold
```
Requires ≥50 ticks for dynamic threshold; otherwise uses `max_edge_mispricing` flat cap.

### Edge/Max Profit Ratio
```
max_profit = 1.0 - fill_price
edge = min(|mispricing|, max_profit)
ratio = edge / max_profit
reject if ratio < min_edge_profit_ratio OR ratio > param_space.high (overconfident)
```

### Stop-Room/Slippage Survivability
```
stop_room = entry_price × stop_loss_pct
survive_ratio = stop_room / total_exec_cost
reject if survive_ratio < min_stop_room_ratio
```
