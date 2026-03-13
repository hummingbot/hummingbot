# LP Rebalancer Controller

A concentrated liquidity (CLMM) position manager that automatically rebalances positions based on price movement and configurable price limits.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [LP Executor Integration](#lp-executor-integration)
- [Scenarios](#scenarios)
- [Edge Cases](#edge-cases)
- [Database & Tracking](#database--tracking)
- [Troubleshooting](#troubleshooting)
- [Scripts](#scripts)
- [Why Controller-Managed Rebalancing?](#why-controller-managed-rebalancing)

---

## Overview

LP Rebalancer maintains a single LP position and automatically rebalances it when price moves out of range. It uses a "grid-like" approach with separate BUY and SELL zones, anchoring positions at price limits to maximize fee collection.

### Key Features

- **Automatic rebalancing** when price exits position range
- **Configurable BUY and SELL price zones** (can overlap)
- **"KEEP" logic** to avoid unnecessary rebalancing when already at optimal position
- **Supports initial BOTH, BUY, or SELL sided positions**
- **Retry logic** for transaction failures due to chain congestion

### Use Cases

- **Range-bound trading**: Collect fees while price oscillates within a range
- **Directional LP**: Position for expected price movements (BUY for dips, SELL for pumps)
- **Grid-like strategies**: Automatically reposition at price limits

---

## Architecture

### Controller-Executor Pattern

Hummingbot's strategy_v2 uses a **Controller-Executor** pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Strategy Layer                            │
│  (v2_with_controllers.py - orchestrates multiple controllers)   │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌─────────────────────┐  ┌─────────────────────┐
        │   LPRebalancer      │  │   Other Controller  │
        │   (Controller)      │  │                     │
        │                     │  │                     │
        │ - Decides WHEN to   │  │                     │
        │   create/stop       │  │                     │
        │   positions         │  │                     │
        │ - Calculates bounds │  │                     │
        │ - KEEP vs REBALANCE │  │                     │
        └─────────┬───────────┘  └─────────────────────┘
                  │
                  │ CreateExecutorAction / StopExecutorAction
                  ▼
        ┌─────────────────────┐
        │     LPExecutor      │
        │     (Executor)      │
        │                     │
        │ - Manages single    │
        │   position lifecycle│
        │ - Opens/closes via  │
        │   gateway           │
        │ - Tracks state      │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │   Gateway (LP)      │
        │                     │
        │ - Connector to DEX  │
        │ - Meteora, Raydium  │
        │ - Solana chain ops  │
        └─────────────────────┘
```

### Key Components

| Component | Responsibility |
|-----------|---------------|
| **Controller** (`LPRebalancer`) | Strategy logic - when to create/stop positions, price bounds calculation, KEEP vs REBALANCE decisions |
| **Executor** (`LPExecutor`) | Position lifecycle - opens position, monitors state, closes position on stop |
| **Gateway** (`gateway_lp.py`) | DEX interaction - sends transactions, tracks confirmations |
| **Connector** (`meteora/clmm`) | Protocol-specific implementation |

### Data Flow

1. **Controller** reads market data and executor state
2. **Controller** decides action (create/stop/keep)
3. **Controller** returns `ExecutorAction` to strategy
4. **Strategy** creates/stops executor based on action
5. **Executor** calls gateway to open/close position
6. **Gateway** sends transaction to chain
7. **Events** propagate back through the stack

---

## Configuration

### Full Configuration Reference

```yaml
# Identity
id: lp_rebalancer_1                    # Unique identifier
controller_name: lp_rebalancer         # Must match controller class
controller_type: generic               # Controller category

# Position sizing
total_amount_quote: '50'               # Total value in quote currency
side: 0                                # Initial side: 0=BOTH, 1=BUY, 2=SELL
position_width_pct: '0.5'              # Position width as percentage (0.5 = 0.5%)
position_offset_pct: '0.1'             # Offset to ensure single-sided positions start out-of-range

# Connection
connector_name: meteora/clmm           # LP connector
network: solana-mainnet-beta           # Network
trading_pair: SOL-USDC                 # Trading pair
pool_address: 'HTvjz...'               # Pool address on DEX

# Price limits (like overlapping grids)
sell_price_max: 88                     # Ceiling - don't sell above
sell_price_min: 86                     # Floor - anchor SELL positions here
buy_price_max: 87                      # Ceiling - anchor BUY positions here
buy_price_min: 85                      # Floor - don't buy below

# Timing
rebalance_seconds: 60                  # Seconds out-of-range before rebalancing
rebalance_threshold_pct: '0.1'         # Price must be this % beyond bounds before timer starts

# Optional
strategy_type: 0                       # Connector-specific (Meteora strategy type)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | string | auto | Unique controller identifier |
| `total_amount_quote` | decimal | 50 | Total position value in quote currency |
| `side` | int | 1 | Initial side: 0=BOTH, 1=BUY, 2=SELL |
| `position_width_pct` | decimal | 0.5 | Position width as percentage |
| `position_offset_pct` | decimal | 0.01 | Offset from current price to ensure single-sided positions start out-of-range |
| `sell_price_max` | decimal | null | Upper limit for SELL zone |
| `sell_price_min` | decimal | null | Lower limit for SELL zone (anchor point) |
| `buy_price_max` | decimal | null | Upper limit for BUY zone (anchor point) |
| `buy_price_min` | decimal | null | Lower limit for BUY zone |
| `rebalance_seconds` | int | 60 | Seconds out-of-range before rebalancing |
| `rebalance_threshold_pct` | decimal | 0.1 | Price must be this % beyond position bounds before rebalance timer starts (0.1 = 0.1%, 2 = 2%) |

### Price Limits Visualization

```
Price:    84        85        86        87        88        89
          |---------|---------|---------|---------|---------|
                    ^         ^         ^         ^
               buy_min   sell_min   buy_max   sell_max
                    |         |         |         |
                    +---------+---------+         |
                       BUY ZONE [85-87]           |
                              +---------+---------+
                                SELL ZONE [86-88]
                              +---------+
                              OVERLAP [86-87]
```

---

## How It Works

### Side and Amount Calculation

Based on `side` and `total_amount_quote`:

| Side | Name | base_amount | quote_amount | Description |
|------|------|-------------|--------------|-------------|
| 0 | BOTH | `(total/2) / price` | `total/2` | Double-sided, 50/50 split |
| 1 | BUY | `0` | `total` | Quote-only, positioned below price |
| 2 | SELL | `total / price` | `0` | Base-only, positioned above price |

### Bounds Calculation

**Side=0 (BOTH)** - Initial only, centered on current price:
```
half_width = position_width_pct / 2
lower = current_price * (1 - half_width)
upper = current_price * (1 + half_width)
```

**Side=1 (BUY)** - Anchored at buy_price_max:
```
upper = min(current_price, buy_price_max)
lower = upper * (1 - position_width_pct)
```

**Side=2 (SELL)** - Anchored at sell_price_min:
```
lower = max(current_price, sell_price_min)
upper = lower * (1 + position_width_pct)
```

### Rebalancing Decision Flow

```
                    +---------------------------------------+
                    |    INITIAL (total_amount_quote=50)    |
                    |    side from config: 0, 1, or 2       |
                    +-------------------+-------------------+
                                        |
                                        v
              +-----------------------------------------------------+
              |                    ACTIVE POSITION                   |
              |    Stores [lower_price, upper_price] in custom_info  |
              +-------------------------+---------------------------+
                                        |
                        +---------------+---------------+
                        |                               |
         current < lower_price              current > upper_price
              (side=2 SELL)                     (side=1 BUY)
                        |                               |
                        v                               v
         +-------------------------+     +-------------------------+
         | lower == sell_price_min?|     | upper == buy_price_max? |
         +------+----------+-------+     +------+----------+-------+
                |          |                    |          |
           YES  |          | NO            YES  |          | NO
                v          v                    v          v
         +----------+ +------------+    +----------+ +------------+
         |   KEEP   | | REBALANCE  |    |   KEEP   | | REBALANCE  |
         | POSITION | | SELL at    |    | POSITION | | BUY at     |
         |          | | sell_min   |    |          | | buy_max    |
         +----------+ +------------+    +----------+ +------------+
```

### Rebalance vs Keep Summary

| Price Exit | At Limit? | Action |
|------------|-----------|--------|
| Above (BUY) | upper < buy_price_max | REBALANCE to buy_max |
| Above (BUY) | upper == buy_price_max | **KEEP** |
| Below (SELL) | lower > sell_price_min | REBALANCE to sell_min |
| Below (SELL) | lower == sell_price_min | **KEEP** |

---

## LP Executor Integration

### LPExecutor States

The executor manages position lifecycle through these states:

```
NOT_ACTIVE ──► OPENING ──► IN_RANGE ◄──► OUT_OF_RANGE ──► CLOSING ──► COMPLETE
     │              │           │              │               │
     │              │           │              │               │
     └──────────────┴───────────┴──────────────┴───────────────┘
                           (on failure, retry)
```

| State | Description |
|-------|-------------|
| `NOT_ACTIVE` | No position, no pending orders |
| `OPENING` | add_liquidity submitted, waiting for confirmation |
| `IN_RANGE` | Position active, price within bounds |
| `OUT_OF_RANGE` | Position active, price outside bounds |
| `CLOSING` | remove_liquidity submitted, waiting for confirmation |
| `COMPLETE` | Position closed permanently |

### LPExecutorConfig

The controller creates executor configs with these key fields:

```python
LPExecutorConfig(
    market=ConnectorPair(connector_name="meteora/clmm", trading_pair="SOL-USDC"),
    pool_address="HTvjz...",
    lower_price=Decimal("86.5"),
    upper_price=Decimal("87.0"),
    base_amount=Decimal("0"),       # 0 for BUY side
    quote_amount=Decimal("20"),     # All in quote for BUY
    side=1,                         # BUY
    position_offset_pct=Decimal("0.1"),  # Used for price shift recovery
    keep_position=False,            # Close on stop
)
```

### Retry Behavior and Error Handling

When a transaction fails (e.g., due to chain congestion), the executor automatically retries up to 10 times (configured via executor orchestrator).

**When max_retries is reached:**
1. Executor stays in current state (`OPENING` or `CLOSING`) - does NOT shut down
2. Sets `max_retries_reached = True` in custom_info
3. Sends notification to user via hummingbot app
4. Stops retrying until user intervenes

**User intervention required:**
- For `OPENING` failures: Position was not created - user can stop the controller
- For `CLOSING` failures: Position exists on-chain - user may need to close manually via DEX UI

**Example notification:**
```
LP CLOSE FAILED after 10 retries for SOL-USDC. Position ABC... may need manual close.
```

### Price Shift Recovery

When creating a single-sided position (BUY or SELL), the price may move into the intended position range between when bounds are calculated and when the transaction executes. This causes the DEX to require tokens on **both** sides instead of just one.

**The Problem:**
```
Controller calculates BUY position:
  price=100, bounds=[99.0, 99.9] (position below current price)
  → Expects only USDC needed

During transaction submission, price drops to 99.5:
  → Position is now IN_RANGE
  → DEX requires BOTH SOL and USDC
  → Transaction fails with "Price has moved" or "Position would require"
```

**Automatic Recovery:**

The executor detects this error and automatically shifts bounds using `position_offset_pct`:

1. Fetches current pool price
2. Recalculates bounds using same width but new anchor point with offset
3. For BUY: `upper = current_price * (1 - offset_pct)`, then lower extends down
4. For SELL: `lower = current_price * (1 + offset_pct)`, then upper extends up
5. Retries position creation with shifted bounds

**This does NOT count as a retry** since it's a recoverable adjustment, not a failure.

**Example (BUY side, offset=0.1%):**
```
Original:      bounds=[99.0, 99.9], price moved to 99.5 (in-range!)
After shift:   bounds=[98.4, 99.4], price=99.5 (out-of-range, only USDC needed)
```

**Why position_offset_pct matters:**

| offset_pct | Effect |
|------------|--------|
| 0 | No buffer - any price movement during TX can cause failure |
| 0.1 (0.1%) | Small buffer - handles typical price jitter |
| 1.0 (1%) | Large buffer - handles volatile markets, but position further from price |

The offset ensures the position starts **out-of-range** so only one token is required:
- BUY positions: only quote token (USDC)
- SELL positions: only base token (SOL)

### Executor custom_info

The executor exposes state to the controller via `custom_info`:

```python
{
    "state": "IN_RANGE",           # Current state
    "position_address": "ABC...",  # On-chain position address
    "lower_price": 86.5,           # Position bounds
    "upper_price": 87.0,
    "current_price": 86.8,         # Current market price
    "base_amount": 0.1,            # Current amounts in position
    "quote_amount": 15.5,
    "base_fee": 0.0001,            # Collected fees
    "quote_fee": 0.05,
    "out_of_range_seconds": 45,    # Seconds out of range (if applicable)
    "max_retries_reached": False,  # True when intervention needed
}
```

### Controller-Executor Communication

```python
# Controller decides to rebalance
def determine_executor_actions(self) -> List[ExecutorAction]:
    executor = self.active_executor()

    if executor.custom_info["state"] == "OUT_OF_RANGE":
        if executor.custom_info["out_of_range_seconds"] >= self.config.rebalance_seconds:
            # Stop current executor (closes position)
            return [StopExecutorAction(executor_id=executor.id)]

    if executor is None and self._pending_rebalance:
        # Create new executor with new bounds
        return [CreateExecutorAction(executor_config=new_config)]

    return []
```

---

## Scenarios

### Initial Positions

#### side=0 (BOTH) at price=86.5

```
Amounts: base=0.289 SOL, quote=25 USDC
Bounds:  lower=86.28, upper=86.72
```

```
Price:    84        85        86        87        88        89
          |---------|---------|---------|---------|---------|

Position:                     [===*===]
                            86.28    86.72
                                  ^
                              price=86.5 (IN_RANGE, centered)
```

#### side=1 (BUY) at price=86.5

```
Amounts: base=0, quote=50 USDC
Bounds:  upper=86.5, lower=86.07
```

```
Position:                 [========*]
                        86.07    86.50
                                  ^
                              price=86.5 (IN_RANGE at upper edge)
```

#### side=2 (SELL) at price=86.5

```
Amounts: base=0.578 SOL, quote=0 USDC
Bounds:  lower=86.5, upper=86.93
```

```
Position:                 [*========]
                        86.50    86.93
                          ^
                      price=86.5 (IN_RANGE at lower edge)
```

### Scenario A: Price Moves UP (starting from BUY)

#### A1: Price 86.5 -> 87.5 (OUT_OF_RANGE above)

```
Position:                 [========]            *
                        86.07    86.50      price=87.5
```

**Decision:**
1. Side = BUY (price > upper)
2. At limit? upper (86.50) < buy_price_max (87) -> **NO**
3. **REBALANCE** to BUY anchored at buy_price_max

```
New Position: BUY [86.57, 87.00]
                             ^
                      anchored at buy_max
```

#### A2: Price 87.5 -> 88.5 (still OUT_OF_RANGE above)

```
Position:                     [========]                *
                            86.57    87.00          price=88.5
```

**Decision:**
1. Side = BUY (price > upper)
2. At limit? upper (87.00) == buy_price_max (87) -> **YES**
3. **KEEP POSITION** - already anchored optimally

#### A3: Price 88.5 -> 86.8 (back IN_RANGE)

```
Position:                     [===*====]
                            86.57    87.00
                                ^
                            price=86.8 (IN_RANGE)
```

Price dropped back into range. Buying base. **This is why we KEEP** - positioned to catch the dip.

### Scenario B: Price Moves DOWN

Starting from: BUY [86.07, 86.50] at price 86.5

#### B1: Price 86.5 -> 85.5 (OUT_OF_RANGE below)

```
Position:        *        [========]
             price=85.5 86.07    86.50
```

**Decision:**
1. Side = SELL (price < lower)
2. At limit? lower (86.07) > sell_price_min (86) -> **NO**
3. **REBALANCE** to SELL anchored at sell_price_min

```
New Position: SELL [86.00, 86.43]
                    ^
             anchored at sell_min
```

#### B2: Price 85.5 -> 84.0 (still OUT_OF_RANGE below)

```
Position:         *                   [========]
              price=84.0            86.00    86.43
```

**Decision:**
1. Side = SELL (price < lower)
2. At limit? lower (86.00) == sell_price_min (86) -> **YES**
3. **KEEP POSITION** - already anchored optimally

#### B3: Price 84.0 -> 86.2 (back IN_RANGE)

```
Position:                 [*=======]
                        86.00    86.43
                          ^
                      price=86.2 (IN_RANGE)
```

Price rose back into range. Selling base. **This is why we KEEP** - positioned to catch the pump.

### All Scenarios Summary

| Starting Position | Price Movement | Result |
|-------------------|----------------|--------|
| BUY at current | up, not at limit | REBALANCE to buy_max |
| BUY at buy_max | up | KEEP |
| BUY at current | down | REBALANCE to SELL at sell_min |
| SELL at current | down, not at limit | REBALANCE to sell_min |
| SELL at sell_min | down | KEEP |
| SELL at current | up | REBALANCE to BUY at buy_max |
| BOTH at current | up | REBALANCE to BUY at buy_max |
| BOTH at current | down | REBALANCE to SELL at sell_min |
| Any | oscillate in range | No action, accumulate fees |

---

## Edge Cases

### Config Validation

```python
if buy_price_max < buy_price_min:
    raise ValueError("buy_price_max must be >= buy_price_min")
if sell_price_max < sell_price_min:
    raise ValueError("sell_price_max must be >= sell_price_min")
```

### Bounds Validation

After calculating bounds, invalid positions are rejected:

```python
if lower >= upper:
    self.logger().warning(f"Invalid bounds [{lower}, {upper}] - skipping")
    return None
```

### Initial Position Validation

| side | Valid price range | Error if outside |
|------|-------------------|------------------|
| 0 (BOTH) | buy_price_min <= price <= sell_price_max | Bounds validation fails |
| 1 (BUY) | price >= buy_price_min | Explicit error |
| 2 (SELL) | price <= sell_price_max | Explicit error |

### Optional Price Limits (None)

If limits are not set, behavior changes:

| Limit | If None | Effect |
|-------|---------|--------|
| buy_price_max | No ceiling | BUY always uses current_price as upper |
| buy_price_min | No floor | Lower bound not clamped |
| sell_price_min | No floor | SELL always uses current_price as lower |
| sell_price_max | No ceiling | Upper bound not clamped |

**No limits = always follow price** (no anchoring, always rebalance).

### Gap Zone (sell_price_min > buy_price_max)

If there's no overlap between zones (e.g., buy_max=86, sell_min=88), positions in the gap [86, 88] work correctly:

- **BUY at price=87**: position [85.57, 86.00] below price, waiting for dips
- **SELL at price=87**: position [88.00, 88.44] above price, waiting for pumps

This is valid - positions don't need to contain current price.

### Boundary Precision

LP protocols typically use half-open intervals `[lower, upper)`:
- `price >= lower` -> IN_RANGE (lower is inclusive)
- `price >= upper` -> OUT_OF_RANGE (upper is exclusive)

---

## Database & Tracking

### Tables Used

| Table | Purpose |
|-------|---------|
| `Controllers` | Stores controller config snapshots |
| `Executors` | Stores executor state and performance |
| `RangePositionUpdate` | Stores LP position events (ADD/REMOVE) |

### RangePositionUpdate Events

Each position open/close creates a record:

```sql
SELECT position_address, order_action, base_amount, quote_amount,
       base_fee, quote_fee, lower_price, upper_price
FROM RangePositionUpdate
WHERE config_file_path = 'conf_v2_with_controllers_1.yml'
ORDER BY timestamp;
```

### Viewing LP History

Use the `lphistory` command in hummingbot:

```
>>> lphistory
>>> lphistory --days 1
>>> lphistory --verbose
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid bounds" | Calculated lower >= upper | Check price limits configuration |
| Position not created | Price outside valid range for side | Adjust price limits or wait for price |
| Repeated rebalancing | Price oscillating at limit | Increase `rebalance_seconds` |
| Transaction timeout | Chain congestion | Retry logic handles this automatically |
| "LP OPEN/CLOSE FAILED" notification | Max retries reached | See intervention steps below |

### Max Retries Reached - Intervention Required

When you receive a notification like:
```
LP CLOSE FAILED after 10 retries for SOL-USDC. Position ABC... may need manual close.
```

**For OPENING failures:**
1. Position was NOT created on-chain
2. Stop the controller via hummingbot
3. Check chain status / RPC health
4. Restart when ready

**For CLOSING failures:**
1. Position EXISTS on-chain but couldn't be closed
2. Check the position address on Solscan/Explorer
3. Close manually via DEX UI (e.g., Meteora app)
4. Stop the controller after manual close

**To increase retry tolerance:**
Set `executors_max_retries` in the strategy config or executor orchestrator settings.

### Logging

Enable debug logging to see decision details:

```python
# In logs/logs_*.log
controllers.generic.lp_rebalancer - INFO - REBALANCE initiated (side=1, price=87.5)
controllers.generic.lp_rebalancer - INFO - KEEP position - already at limit
```

### Verifying Positions On-Chain

For Solana/Meteora positions:
```bash
# Check position exists
solana account <position_address>

# View transaction
https://solscan.io/tx/<signature>
```

---

## Scripts

Utility scripts for analyzing and visualizing LP position data are available through the **LP Agent Skill**.

### Installing the LP Agent Skill

Visit https://skills.hummingbot.org/skill/lp-agent for full documentation and installation instructions.

**Install with:**
```bash
npx skills add hummingbot/skills --skill lp-agent
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `visualize_lp_positions.py` | Interactive HTML dashboard from LP position events |
| `visualize_executors.py` | Interactive HTML dashboard from executor data |
| `export_lp_positions.py` | Export raw LP add/remove events to CSV |
| `export_lp_executors.py` | Export executor data to CSV |

---

## Why Controller-Managed Rebalancing?

LPExecutor has a built-in `auto_close_out_of_range_seconds` config that can automatically close positions after being out of range. However, LP Rebalancer doesn't use this - instead, the controller manages timing via its own `rebalance_seconds` config.

| Approach | Config | Who Closes |
|----------|--------|------------|
| **Controller manages timing** | `rebalance_seconds` (controller config) | Controller sends `StopExecutorAction` |
| **Executor auto-closes** | `auto_close_out_of_range_seconds` (executor config) | Executor self-closes |

### Why LP Rebalancer Uses Controller-Managed Timing

```
Controller monitors executor.custom_info["out_of_range_seconds"]
         │
         ▼
out_of_range_seconds >= rebalance_seconds?
         │
    YES  │
         ▼
Controller checks: _is_at_limit()?
         │
    ┌────┴────┐
    │         │
   YES       NO
    │         │
    ▼         ▼
  KEEP    REBALANCE
(no-op)  (StopExecutorAction)
```

**Benefits:**
- **KEEP logic**: Controller can check "am I at limit?" BEFORE closing, avoiding unnecessary transactions
- **Full context**: Controller has access to price limits, config, market state
- **Flexibility**: Can implement sophisticated logic (velocity checks, fee thresholds, etc.)

### When Executor Auto-Close Makes Sense

For simpler use cases without KEEP/REBALANCE logic:
- Simple scripts without controllers
- One-shot "set and forget" positions
- Testing executor behavior

With executor auto-close, the executor closes regardless of whether the position was at a limit - potentially wasting transactions if the controller just reopens the same position.

---

## Related Files

| File | Description |
|------|-------------|
| `controllers/generic/lp_rebalancer/lp_rebalancer.py` | Controller implementation |
| `hummingbot/strategy_v2/executors/lp_executor/` | Executor implementation |
| `hummingbot/connector/gateway/gateway_lp.py` | Gateway LP connector |
| `hummingbot/client/command/lphistory_command.py` | LP history command |
