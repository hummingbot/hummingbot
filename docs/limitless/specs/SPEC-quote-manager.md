# SPEC: quote_manager.py — Signal-Informed Market Making Module

New module inside `controllers/generic/binary_options/`. Sits alongside
`action_router.py` — same controller, different objective. Config toggle
switches between directional (action_router) and MM (quote_manager) modes.

---

## 1. Core Concept

The signal engine computes per-coin per-tick:
1. **Fair value** — B-S model probability from spot, strike, time, vol
2. **Z-scores** — SPOT (mispricing divergence) and BTC (BTC-implied divergence)
3. **Direction** — which side our model favors (YES/NO)

For directional trading: high z → enter trade. For MM: high z → widen or
pull quotes. The **same Optuna-tuned thresholds** from `runtime.json` drive
both modes — no new thresholds invented.

---

## 2. Revenue Streams

### 2a. LP Rewards (passive, no fills needed)
- Orders within **spread** of orderbook midpoint earn rewards
- Per-market: `Rewards` (daily USDC pool), `Spread` (max distance), `Min Shares` (min size)
- Calculated **every minute**, paid daily at 12:00 UTC
- **Bonus multiplier:** tighter to midpoint = higher reward share
- One-sided OK when odds 5%–95%

### 2b. Maker Rebates (on fills)
- 20% of taker fees rebated to maker (Hourly + 15-min Crypto)
- Pro-rata daily USDC payout based on your share of total rebate credit
- Only executed fills count

### 2c. Spread Capture (convergence)
- Both YES + NO filled at total < $1.00 = locked settlement profit

### 2d. Fee Structure
- **Makers: ZERO fees** — placing/cancelling quotes costs nothing
- Takers: 0.40%–3.00% (buy), 0.42%–1.50% (sell)

---

## 3. The Reward Tunnel

Quotes exist within a tunnel between two walls:

```
INNER WALL ──── closest to mid (most competitive, highest LP bonus)
    │
    │  ← z-score slides quote position within this range
    │
OUTER WALL ──── LP reward spread limit (e.g. 3¢ from mid)
    │
  PULLED   ──── beyond outer wall = no quote on this side
```

**The tunnel width is defined by the market's LP reward spread parameter.**
Quote placement is %-based, so it works regardless of the specific market's
spread setting (3¢, 5¢, etc).

### Quote Position = f(z-score, model skew)

For each side (YES bid, NO bid):

```
z_ratio = z_score / coin_threshold  # 0.0 to 1.0 (from runtime.json)

# Base distance from midpoint (symmetric)
base_dist = inner + (outer - inner) × z_ratio

# Skew from model disagreement
model_disagree = model_prob - market_yes  # signed
skew = model_disagree × skew_sensitivity

# Final placement
favored_side_dist  = base_dist - skew  # tighter (toward inner)
opposing_side_dist = base_dist + skew  # wider (toward outer)
```

Where `inner` and `outer` are %-based fractions of the market's reward spread.

### Behavior by Z-Score Regime

| Z Regime | Favored Side | Opposing Side | Mode |
|----------|-------------|---------------|------|
| z ≈ 0 | ~middle of tunnel | ~middle of tunnel | Symmetric MM |
| z at 0.5× threshold | inner half | outer half | Skewed MM |
| z at 0.9× threshold | inner wall | outer wall | Aggressive skew |
| z ≥ threshold | **inner wall (STAYS)** | **PULLED** | Directional via maker |
| z drops below threshold | inner wall | outer wall (re-placed) | Recovery |

**Critical rule: at threshold, the favored side is NEVER pulled.** It stays
at inner wall — inviting the fill. This IS the directional entry, just via
maker order = zero fees + earning rebates. The opposite side pulls to avoid
adverse fill.

The only scenario where BOTH sides pull is TBD (parked — see Open Questions
in QUANT-MISSION.md). Candidates: vol spike + low confidence, or lower vol
band crossing. Needs data.

---

## 4. Threshold Reuse from runtime.json

**No new thresholds.** The existing Optuna-tuned per-coin params define
everything:

| runtime.json param | MM usage |
|---|---|
| `edge_z_threshold` | SPOT z pull trigger (opposing side) |
| `btc_z_threshold` | BTC z pull trigger (opposing side) |
| `vol_ema_halflife_secs` | Vol regime detection |
| `scale_in_cooldown_seconds` | Post-fill cooldown before re-quoting |
| `tp_distance` | Post-fill close order distance from fair value |
| `min_edge_after_execution` | Re-entry gate after fill |

`RuntimeBridge` already reads these per-coin. `quote_manager` just consumes
them differently than `action_router`.

**Why this works:** Optuna optimized directional thresholds into near-zero-trade
territory. The thresholds sit right at the noise/signal boundary. Below = safe
quoting zone. Above = movement = pull. The system self-selects.

---

## 5. Post-Fill Management

### One Side Filled

When filled on the favored side (the expected case):

1. **Opposing side:** already pulled (z was at threshold). Stays pulled.
2. **Close order:** place SELL limit at `fair_value - tp_distance` (from
   runtime.json, already Optuna-tuned per coin)
3. **Dynamic repricing:** every tick, recalculate fair value, cancel + replace
   close order if price drifted beyond reprice threshold
4. **BTC reversal / stop:** handled by existing `exit_monitor.py` — same
   logic, monitors BTC movement against our fill direction
5. **Settlement:** if market approaches expiry with position, `exit_monitor`
   handles settlement hold vs exit decision

This is functionally identical to a directional position. The only difference
is HOW we entered (maker order vs taker order).

### Both Sides Filled

- Total cost < $1.00 = convergence profit locked
- Wait for settlement or merge via CTF contract
- No action needed

### Integration with position_tracker
- Partial fills create tracked positions (same as directional)
- position_tracker gates apply (cooldown, max positions, circuit breaker)
- **Resting quotes are NOT positions** until filled

---

## 6. Config

New section in `BinaryOptionsControllerConfig`:

```python
class QuoteConfig(BaseModel):
    """Market-making quote parameters."""

    enabled: bool = False  # master toggle

    # Tunnel bounds (as fraction of market's reward spread)
    inner_fraction: float = 0.2    # 20% of reward spread = closest to mid
    outer_fraction: float = 0.9    # 90% of reward spread = widest before pull

    # Skew
    skew_sensitivity: float = 0.5  # model disagreement → tunnel asymmetry

    # Size
    base_size: int = 100           # shares per order (must meet LP min_shares)
    max_size: int = 500            # max shares per order

    # Post-fill close order
    reprice_threshold: float = 0.01  # reprice close order when fair value
                                      # drifts by this amount

    # Market selection
    odds_min: float = 0.05         # don't quote below 5%
    odds_max: float = 0.95         # don't quote above 95%
    min_hours_for_quoting: float = 0.25  # 15 min — don't quote near expiry

    # Capital
    max_capital_per_market: float = 50.0   # USDC
    max_total_capital: float = 200.0       # USDC
```

**Note:** No pull thresholds, no z thresholds, no vol thresholds here.
All from `runtime.json` per-coin via `RuntimeBridge`.

---

## 7. Module Interface

```python
@dataclass
class QuoteAction:
    """Single quote placement/update/cancel action."""
    action: str          # "place" | "cancel" | "update" | "close_order"
    coin: str
    side: str            # "YES" | "NO"
    price: float
    size: int
    order_id: str = ""   # for cancel/update

@dataclass
class QuoteActions:
    """Batch of actions from one tick."""
    actions: List[QuoteAction]

class QuoteState(str, Enum):
    IDLE = "idle"              # not quoting (filtered out by market selection)
    SYMMETRIC = "symmetric"    # both sides, low z, pure MM
    SKEWED = "skewed"          # both sides, moderate z, tunnel asymmetric
    ONE_SIDED = "one_sided"    # favored side only, z ≥ threshold
    FILLED = "filled"          # one side filled, managing close order
    CONVERGED = "converged"    # both sides filled, locked profit

class QuoteManager:
    """Signal-informed market making — quotes within reward tunnel,
    position determined by z-scores and model disagreement."""

    def __init__(self, config: QuoteConfig, runtime_bridge: RuntimeBridge):
        self._config = config
        self._rb = runtime_bridge
        self._states: Dict[str, QuoteState] = {}
        self._open_orders: Dict[str, Dict[str, str]] = {}  # {coin: {side: order_id}}
        self._close_orders: Dict[str, str] = {}  # {coin: close_order_id}
        self._fill_prices: Dict[str, Dict[str, float]] = {}  # {coin: {side: fill_price}}

    def tick(
        self,
        signals: Dict[str, dict],        # from signal_engine.tick()
        markets: Dict[str, dict],         # from market_manager
        positions: Dict[str, Any],        # from position_tracker
        orderbook_mids: Dict[str, float], # current orderbook midpoints
        reward_spreads: Dict[str, float], # per-market LP reward spread limit
    ) -> QuoteActions:
        """Compute quote actions for this tick.

        Per coin:
        1. Get z_ratio = max(spot_z, btc_z) / threshold (from runtime.json)
        2. Get model_disagree = model_prob - market_yes
        3. Compute tunnel position for each side
        4. If z ≥ threshold: pull opposing, keep favored at inner
        5. If filled: manage close order at fair_value - tp_distance
        6. Emit place/cancel/update actions
        """

    def on_fill(self, coin: str, side: str, price: float, size: int):
        """Resting order filled. Transition to FILLED state,
        place close order using tp_distance from runtime.json."""

    def on_close_fill(self, coin: str):
        """Close order filled. Position exited. Return to quoting."""

    def get_state(self, coin: str) -> QuoteState:
        """Current state for a coin."""
```

---

## 8. Controller Integration

In `controller.py` → `update_processed_data()`:

```python
async def update_processed_data(self):
    signals = self.signal_engine.tick(spots, markets, btc_spot, now_ts)

    if self.config.quoting.enabled:
        quote_actions = self.quote_manager.tick(
            signals, markets,
            self.position_tracker.snapshot(),
            orderbook_mids, reward_spreads)
        # Convert QuoteActions to executor actions
        ...
    else:
        # Directional mode via action_router (existing)
        ...
```

Toggle `quoting.enabled` in YAML to switch modes. Both share the same
signal engine, fair value, market manager, spot feed.

---

## 9. What This Reuses

### Zero changes:
- `fair_value.py` — model_prob, vol, mispricing (consumers unchanged)
- `signal_engine.py` — all z-scores, event classification (output unchanged)
- `config.py` / `RuntimeBridge` — reads same runtime.json params
- `market_manager.py` — same market discovery
- `spot_feed.py` — same price feeds
- `order_types.py` — LIMIT_MAKER already exists
- `position_tracker.py` — filled orders = tracked positions
- `exit_monitor.py` — BTC reversal + settlement for filled positions

### New code:
- `quote_manager.py` — THIS module (~300-400 lines)
- `QuoteConfig` added to `config.py` (~20 lines)
- Controller tick branch (~10 lines)

### Semantic reinterpretation (same data, different consumer):
- `runtime.json` thresholds → pull triggers instead of entry triggers
- `tp_distance` → close order distance instead of take-profit
- `exit_monitor` → applies to filled MM positions identically

---

## 10. Module Dependencies

```
signal_engine.tick()
       │
       ▼
quote_manager.tick()  ←── runtime_bridge (thresholds, tp_distance)
       │                  fair_value (model_prob via signals)
       │                  orderbook mids (from connector/market data)
       │                  reward spreads (from market metadata)
       ▼
QuoteActions → executor (place/cancel/update limit orders)
       │
       ▼ (on fill)
position_tracker ←── exit_monitor (BTC reversal, settlement)
```
