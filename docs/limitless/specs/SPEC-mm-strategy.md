# SPEC: Market Making Strategy (Phase 1)

## Output
**File:** `skills/limitless-mm/scripts/mm_bot.py`
**Imports from:** `skills/limitless-mm/scripts/connector.py` (LimitlessConnector class)

## Goal

Simple bracket-quote MM for Limitless prediction markets. BTC only to start.
Uses `LimitlessConnector` for all exchange interaction.

## Strategy Overview

Post bid and ask around the mid price, collect spread on fills.
Stay inventory-neutral (balanced YES/NO). Pull orders before expiry.

## Market Lifecycle

Each hourly (or 15-min) market has a known lifecycle:

```
:00        Market opens. Discover new market slug, cache venue.
:00-:45    ACTIVE PHASE — post quotes, collect spread, manage inventory.
:45-:55    WIND DOWN — widen spread, reduce size, get conservative.
:55-:00    HANDS OFF — cancel all orders. Hold inventory for settlement.
:00        Settlement — positions pay out. Roll to next market.
```

All times configurable. For 15-min markets, compress proportionally:
```
:00-:10    ACTIVE
:10-:13    WIND DOWN
:13-:15    HANDS OFF
```

## Core Loop (every tick, ~5s)

```python
async def tick():
    # 1. Check lifecycle phase
    phase = get_phase(time_to_expiry)

    if phase == "HANDS_OFF":
        await connector.cancel_all(market_slug)
        return

    # 2. Get current state
    mid = await connector.get_mid_price(market_slug)
    inventory = get_inventory()  # net YES shares held

    # 3. Calculate quotes
    spread = base_spread
    if phase == "WIND_DOWN":
        spread = base_spread * wind_down_multiplier  # e.g. 2x

    # 4. Skew for inventory (Avellaneda-Stoikov lite)
    skew = inventory * skew_factor
    bid_price = mid - spread/2 - skew
    ask_price = mid + spread/2 - skew

    # 5. Clamp to valid range
    bid_price = clamp(bid_price, 0.01, 0.99)
    ask_price = clamp(ask_price, 0.01, 0.99)

    # 6. Size (reduce if imbalanced)
    bid_size = base_size * (1.0 if inventory <= 0 else inventory_decay(inventory))
    ask_size = base_size * (1.0 if inventory >= 0 else inventory_decay(inventory))

    # 7. Cancel stale orders + place new ones
    await cancel_stale_orders()
    await connector.buy(market_slug, bid_price, bid_size, "GTC", "YES")
    await connector.sell(market_slug, ask_price, ask_size, "GTC", "YES")
```

## Inventory Management

**Goal:** Stay close to 0 net inventory (balanced YES/NO).

Inventory = YES shares held - NO shares held (in dollar terms).

### Skew Formula (Avellaneda-Stoikov simplified)

```
skew = inventory * skew_factor
```

- `inventory > 0` (long YES): skew > 0 → bid drops, ask drops → encourage selling YES
- `inventory < 0` (long NO): skew < 0 → bid rises, ask rises → encourage buying YES
- `inventory == 0`: symmetric quotes

### Size Decay

When inventory is imbalanced, reduce size on the heavy side:

```python
def inventory_decay(inventory_abs):
    """Reduce size as inventory grows. Returns multiplier 0-1."""
    return max(0.1, 1.0 - (abs(inventory) / max_inventory) * 0.8)
```

### Hard Limit

If `abs(inventory) > max_inventory`:
- Stop quoting on the heavy side entirely
- Only quote the reducing side
- This is the "I'm too exposed" safety

## Market Discovery & Rollover

```python
async def discover_next_market(ticker: str, timeframe: str):
    """Find the active market for a ticker (BTC) and timeframe (1H, 15M).

    - Fetch active markets from API
    - Filter by ticker tag and timeframe tag
    - Pick the ATM strike (closest to current spot)
    - Cache venue data
    - Return market slug
    """
```

### Rollover Flow

```
1. Current market enters HANDS_OFF phase
2. Discover next market (new hour/quarter)
3. Wait for settlement of current market
4. Start quoting on new market
5. No overlap — one market at a time initially
```

## Configuration

```json
{
    "ticker": "BTC",
    "timeframes": ["1H"],
    "base_spread": 0.04,
    "base_size": 20.0,
    "skew_factor": 0.01,
    "max_inventory": 100.0,
    "wind_down_multiplier": 2.0,
    "tick_interval_s": 5,
    "active_phase_end_min": 15,
    "wind_down_end_min": 5,
    "hands_off_min": 5,
    "max_order_size_usd": 20.0,
    "min_spread": 0.02,
    "max_spread": 0.10,
    "paper_mode": true,
    "log_level": "INFO"
}
```

### Config Explanation

| Param | Default | What it does |
|---|---|---|
| `base_spread` | 0.04 | Target total spread ($0.04 = 4 cents). Must be ≤0.06 to qualify for MM rewards |
| `base_size` | 20.0 | Shares per order (each side) |
| `skew_factor` | 0.01 | How aggressively to skew for inventory. Higher = more aggressive rebalancing |
| `max_inventory` | 100.0 | Max net exposure in shares. Beyond this, stop quoting heavy side |
| `wind_down_multiplier` | 2.0 | Spread multiplier during wind down phase |
| `hands_off_min` | 5 | Minutes before expiry to pull all orders |
| `min_spread` | 0.02 | Never quote tighter than this (safety) |
| `max_spread` | 0.10 | Never quote wider than this (stay competitive) |
| `paper_mode` | true | Log orders without submitting. START HERE. |

## Order Management

### Cancel-Replace Strategy

Don't cancel and replace every tick. Only update when:
- Price moved more than `reprice_threshold` (e.g. $0.01) from current order
- Order was partially filled
- Phase changed (active → wind down)

This reduces API calls and avoids unnecessary cancel/create churn.

### Order Tracking

```python
self._active_bid: Optional[str] = None  # order ID
self._active_ask: Optional[str] = None  # order ID
self._bid_price: float = 0.0
self._ask_price: float = 0.0
self._fills: list[dict] = []            # filled orders log
```

### Fill Detection

Poll open orders every tick. If an order disappears → it was filled.
Update inventory accordingly:
- Bid filled → we bought YES shares → inventory += size
- Ask filled → we sold YES shares → inventory -= size

## Risk Controls

### Kill Switch
```python
if total_loss_usd > max_loss_per_hour:
    await cancel_all_and_stop()
```

### Circuit Breaker
- If spread collapses below `min_spread` → don't quote (something weird happening)
- If orderbook is empty → don't quote (no reference price)
- If WS disconnected > 10s → cancel orders (stale data)

### Position Limits
- Max net inventory: `max_inventory` shares
- Max order size: `max_order_size_usd` dollars
- Max orders per market: 1 bid + 1 ask (simple, no multi-level yet)

## Logging & Monitoring

Every tick: log state
```
10:15:05 BTC-1H | mid=0.52 | bid=0.50 ask=0.54 | inv=+5 YES | phase=ACTIVE
10:15:10 BTC-1H | FILL bid 10@0.50 | inv=+15 YES | spread_earned=$0.40
10:45:00 BTC-1H | phase=WIND_DOWN | spread widened 0.04→0.08
10:55:00 BTC-1H | phase=HANDS_OFF | all orders cancelled | holding +15 YES / -10 NO
11:00:00 BTC-1H | SETTLED | YES won | PnL: +$2.30 | rolling to next market
```

CSV trade log:
```
timestamp, market_slug, side, price, size, fill_type, inventory_after, pnl_est
```

## MM Rewards Qualification

To qualify for the 100 USDC/day/market reward pool:
- Spread must be ≤ ±3¢ from midpoint (6¢ total)
- Minimum 100 contracts per side
- Inside 5¢-95¢ range: one side OK
- Outside: need both sides

Our `base_spread` of 0.04 (4¢) qualifies. With 20 shares per side, we need 5 ticks of live quoting to hit 100 contracts minimum. Achievable within one market cycle.

## Settlement & PnL

At settlement:
- YES = $1 if outcome is YES, $0 otherwise
- NO = $1 if outcome is NO, $0 otherwise

If balanced (equal YES and NO):
- One pays $1, other pays $0
- Net position value = $inventory_balanced
- Profit = total spread captured across all fills

If imbalanced:
- Directional risk on the excess
- Small positions = small risk

**PnL tracking:**
```
realized_pnl += spread_captured_per_fill
settlement_pnl += settlement_value - position_cost
total_pnl = realized_pnl + settlement_pnl
```

## Phase 1 Simplifications (vs Hummingbot Phase 2)

- Single market at a time (no multi-market)
- Single level quoting (no multi-level bid/ask ladder)
- Fixed base spread (no dynamic spread based on volatility)
- Simple linear skew (no full Avellaneda-Stoikov with risk aversion parameter)
- Poll-based fill detection (no WS user stream)
- Manual rollover logic (Hummingbot would automate)

## Implementation Order

1. Market discovery + lifecycle timing
2. Core tick loop with paper orders
3. Order placement (GTC bids/asks via connector)
4. Cancel-replace logic
5. Fill detection + inventory tracking
6. Inventory skew
7. Wind down + hands off phases
8. Settlement + rollover
9. PnL tracking + logging
10. Risk controls (kill switch, circuit breaker)
