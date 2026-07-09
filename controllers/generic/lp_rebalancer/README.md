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

---

## Overview

LP Rebalancer maintains a single LP position and automatically rebalances it when price moves beyond configured thresholds. It uses a "grid-like" approach with separate BUY and SELL zones, anchoring positions at price limits to maximize fee collection.

### Key Features

- **Automatic rebalancing** via LP executor limit prices (no timer needed)
- **Configurable BUY and SELL price zones** (can overlap)
- **Autoswap** to automatically swap tokens when balance is insufficient
- **Supports initial RANGE, BUY, or SELL sided positions**
- **Position tracking** via position_hold for cumulative P&L

### Use Cases

- **Range-bound trading**: Collect fees while price oscillates within a range
- **Directional LP**: Position for expected price movements (BUY for dips, SELL for pumps)
- **Grid-like strategies**: Automatically reposition at price limits

---

## Architecture

### Provider Architecture

The controller uses a clear separation between network and LP provider:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Configuration Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  connector_name: "solana-mainnet-beta"   ← Network identifier   │
│  lp_provider: "meteora/clmm"             ← DEX/trading_type     │
│  trading_pair: "SOL-USDC"                ← Token pair           │
│  pool_address: "HTvjz..."                ← Pool on DEX          │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌─────────────────────┐  ┌─────────────────────┐
        │   LP Operations     │  │   Swap Operations   │
        │   (lp_provider)     │  │   (swapProvider)    │
        │                     │  │                     │
        │   meteora/clmm      │  │   jupiter/router    │
        │   orca/clmm         │  │   (from Gateway     │
        │   raydium/clmm      │  │    network config)  │
        └─────────────────────┘  └─────────────────────┘
```

| Parameter | Format | Example | Description |
|-----------|--------|---------|-------------|
| `connector_name` | network | `solana-mainnet-beta` | Network identifier for Gateway |
| `lp_provider` | dex/type | `meteora/clmm` | LP provider in format "dex/trading_type" |
| `swap_provider` | (auto) | `jupiter/router` | Auto-detected from Gateway network config |

### Controller-Executor Pattern

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
        │ - Sets limit prices │  │                     │
        │   for auto-close    │  │                     │
        │ - Calculates bounds │  │                     │
        │ - Handles autoswap  │  │                     │
        └─────────┬───────────┘  └─────────────────────┘
                  │
                  │ CreateExecutorAction
                  ▼
        ┌─────────────────────┐
        │     LPExecutor      │
        │     (Executor)      │
        │                     │
        │ - Opens position    │
        │ - Monitors price    │
        │ - Auto-closes when  │
        │   limit exceeded    │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │   Gateway Connector │
        │                     │
        │ - Solana network    │
        │ - LP via lp_provider│
        │ - Swap via network  │
        │   swapProvider      │
        └─────────────────────┘
```

### Key Components

| Component | Responsibility |
|-----------|---------------|
| **Controller** (`LPRebalancer`) | Strategy logic - sets limit prices, calculates bounds, handles autoswap |
| **Executor** (`LPExecutor`) | Position lifecycle - opens, monitors, auto-closes on limit breach |
| **Gateway Connector** | Network interaction - LP ops via lp_provider, swaps via network swapProvider |

---

## Configuration

### Full Configuration Reference

```yaml
# Identity
id: lp_rebalancer_1                    # Unique identifier
controller_name: lp_rebalancer         # Must match controller class
controller_type: generic               # Controller category

# Network and Provider (NEW ARCHITECTURE)
connector_name: solana-mainnet-beta    # Network identifier
lp_provider: meteora/clmm              # LP provider: "dex/trading_type"
trading_pair: SOL-USDC                 # Trading pair
pool_address: 'HTvjz...'               # Pool address on DEX

# Position sizing
total_amount_quote: '50'               # Total value in quote currency
side: 1                                # Initial side: 1=BUY, 2=SELL, 3=RANGE
position_width_pct: '0.5'              # Position width as percentage (0.5 = 0.5%)
position_offset_pct: '0.1'             # Offset from price (positive=out-of-range, negative=in-range)

# Auto-close threshold (replaces rebalance_seconds)
rebalance_threshold_pct: '1'           # % beyond bounds that triggers auto-close (1 = 1%)

# Price limits (like overlapping grids)
sell_price_max: 88                     # Ceiling - don't sell above
sell_price_min: 86                     # Floor - anchor SELL positions here
buy_price_max: 87                      # Ceiling - anchor BUY positions here
buy_price_min: 85                      # Floor - don't buy below

# Auto-swap feature
autoswap: false                        # Auto-swap tokens if balance insufficient
swap_buffer_pct: '0.01'                # Extra % to swap for slippage (0.01 = 0.01%)

# Optional
strategy_type: 0                       # Connector-specific (Meteora strategy type)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connector_name` | string | solana-mainnet-beta | Network identifier (e.g., "solana-mainnet-beta") |
| `lp_provider` | string | orca/clmm | LP provider in format "dex/trading_type" |
| `trading_pair` | string | "" | Trading pair (e.g., "SOL-USDC") |
| `pool_address` | string | "" | Pool address on the DEX |
| `total_amount_quote` | decimal | 50 | Total position value in quote currency |
| `side` | TradeType | BUY | Initial side: BUY, SELL, or RANGE (50/50 split) |
| `position_width_pct` | decimal | 0.5 | Position width as percentage |
| `position_offset_pct` | decimal | 0.01 | Offset from price. Positive=out-of-range. Negative=in-range |
| `rebalance_threshold_pct` | decimal | 1 | Price % beyond position bounds that triggers auto-close |
| `sell_price_max` | decimal | null | Upper limit for SELL zone |
| `sell_price_min` | decimal | null | Lower limit for SELL zone (anchor point) |
| `buy_price_max` | decimal | null | Upper limit for BUY zone (anchor point) |
| `buy_price_min` | decimal | null | Lower limit for BUY zone |
| `autoswap` | bool | false | Automatically swap tokens if balance insufficient |
| `swap_buffer_pct` | decimal | 0.01 | Extra % to swap beyond deficit for slippage |
| `strategy_type` | int | null | Connector-specific parameter (e.g., Meteora strategy type) |

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

### Auto-Close via Limit Prices

The controller uses LP executor's limit price feature for automatic position closing. This eliminates the need for timer-based rebalancing.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Position Creation                             │
├─────────────────────────────────────────────────────────────────┤
│  lower_price: 95.0                                              │
│  upper_price: 105.0                                             │
│  rebalance_threshold_pct: 1%                                    │
│                                                                 │
│  → lower_limit_price: 95.0 × (1 - 0.01) = 94.05                │
│  → upper_limit_price: 105.0 × (1 + 0.01) = 106.05              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LP Executor Monitors                          │
├─────────────────────────────────────────────────────────────────┤
│  If price < 94.05 → AUTO-CLOSE (price too low)                  │
│  If price > 106.05 → AUTO-CLOSE (price too high)                │
│  Otherwise → Continue monitoring                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits over timer-based rebalancing:**
- **Precise triggers**: Closes at exact price threshold, not after arbitrary time
- **Simpler logic**: No timer state to manage
- **Executor handles it**: Controller just monitors for completion

### Side and Amount Calculation

Based on `side` and `total_amount_quote`:

| Side | Name | base_amount | quote_amount | Description |
|------|------|-------------|--------------|-------------|
| 1 | BUY | `0` | `total` | Quote-only, positioned below price |
| 2 | SELL | `total / price` | `0` | Base-only, positioned above price |
| 3 | RANGE | `(total/2) / price` | `total/2` | Double-sided, 50/50 split |

### Bounds Calculation

**Side=BUY** - Below current price:
```
upper = min(current_price, buy_price_max) * (1 - offset)
lower = upper * (1 - position_width_pct)
```

**Side=SELL** - Above current price:
```
lower = max(current_price, sell_price_min) * (1 + offset)
upper = lower * (1 + position_width_pct)
```

**Side=RANGE** - Centered on current price (50/50 split):
```
half_width = position_width_pct / 2
lower = current_price * (1 - half_width)
upper = current_price * (1 + half_width)
```

### Effect of Position Offset

| Offset | Side=BUY | Side=SELL | Tokens Needed |
|--------|--------------|---------------|---------------|
| +0.5% | upper below price (out-of-range) | lower above price (out-of-range) | Single |
| 0% | upper at price (edge of range) | lower at price (edge of range) | Single |
| -0.5% | upper above price (in-range) | lower below price (in-range) | Both |

**Positive offset** ensures the position starts out-of-range:
- Only requires one token (quote for BUY, base for SELL)
- Position waits for price to enter range

**Negative offset** creates an in-range position:
- Requires both tokens (use autoswap to convert)
- Position immediately earns fees
- Useful when you want exposure on both sides

### Controller Decision Flow

```
                    +---------------------------------------+
                    |    LP Executor auto-closes when       |
                    |    price exceeds limit prices         |
                    +-------------------+-------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |    Controller detects executor done   |
                    |    (state == COMPLETE/TERMINATED)     |
                    +-------------------+-------------------+
                                        |
                                        v
              +-----------------------------------------------------+
              |    Determine side based on price vs closed bounds    |
              |    price >= upper → side=BUY (use quote we got)     |
              |    price < lower → side=SELL (use base we got)      |
              +-------------------------+---------------------------+
                                        |
                        +---------------+---------------+
                        |                               |
              within price limits?              outside price limits?
                        |                               |
                        v                               v
              +-------------------+           +-------------------+
              | Check autoswap    |           | Wait for price    |
              | if needed         |           | to enter limits   |
              +--------+----------+           +-------------------+
                       |
                       v
              +-------------------+
              | Create new LP     |
              | position with     |
              | limit prices      |
              +-------------------+
```

---

## Auto-Swap Feature

The autoswap feature automatically swaps tokens when your balance is insufficient to create the LP position.

### Enabling Autoswap

```yaml
autoswap: true                   # Enable automatic token swapping
swap_buffer_pct: '0.01'          # Swap 0.01% extra for slippage buffer
```

The swap provider is automatically determined from the Gateway network configuration (e.g., `swapProvider: jupiter/router` for solana-mainnet-beta).

### When Autoswap Triggers

| Scenario | Side | Has | Needs | Autoswap Action |
|----------|------|-----|-------|-----------------|
| Deficit in base | BUY/SELL | Quote | Base | BUY base with quote |
| Deficit in quote | BUY/SELL | Base | Quote | SELL base for quote |
| Both in deficit | Any | Partial | Both | Warning (underfunded) |

### SOL Buffer for Rent

When SOL is involved in the swap, an extra 0.1 SOL buffer is added to account for:
- Position rent (refundable deposit)
- Transaction fees
- Network fees

### Autoswap Flow

```
┌─────────────────────────────────────────────────────────┐
│                 determine_executor_actions()             │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  autoswap enabled?    │
              └───────────┬───────────┘
                    YES   │
                          ▼
              ┌───────────────────────┐
              │  Calculate required   │
              │  base & quote amounts │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Check wallet balance │
              │  + closed position    │
              │  amounts (if any)     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Deficit? Create      │
              │  OrderExecutor for    │
              │  swap                 │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Wait for swap        │
              │  completion           │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Update position_hold │
              │  with swap P&L        │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │  Create LP position   │
              └───────────────────────┘
```

### Negative Position Offset (In-Range Positions)

By default, `position_offset_pct` is positive, creating **out-of-range** positions that only require one token:
- BUY position: below current price → only needs quote (USDC)
- SELL position: above current price → only needs base (SOL)

With **negative** `position_offset_pct`, positions are created **in-range**, requiring both tokens:

```yaml
position_offset_pct: '-0.5'  # Negative = in-range position
autoswap: true               # Required to get both tokens
swap_buffer_pct: '0.01'      # Extra buffer for slippage
```

**Validation:** For in-range positions, `|position_offset_pct|` must not exceed `position_width_pct`.

---

## LP Executor Integration

### LPExecutor States

```
NOT_ACTIVE ──► OPENING ──► IN_RANGE ◄──► OUT_OF_RANGE
     │              │           │              │
     │              │           │              │
     │              │           └──────────────┴──► CLOSING ──► SWAPPING ──► COMPLETE
     │              │                                   │           │
     │              │                                   │           │
     └──────────────┴───────────────────────────────────┴───────────┴──► FAILED
```

| State | Description |
|-------|-------------|
| `NOT_ACTIVE` | No position, no pending orders |
| `OPENING` | add_liquidity submitted, waiting for confirmation |
| `IN_RANGE` | Position active, price within bounds |
| `OUT_OF_RANGE` | Position active, price outside bounds |
| `CLOSING` | remove_liquidity submitted, waiting for confirmation |
| `SWAPPING` | Close-out swap in progress (when keep_position=False) |
| `COMPLETE` | Position closed permanently |
| `FAILED` | Operation failed after retries |

### LPExecutorConfig

The controller creates executor configs with limit prices:

```python
LPExecutorConfig(
    connector_name="solana-mainnet-beta",   # Network identifier
    lp_provider="meteora/clmm",             # LP provider
    trading_pair="SOL-USDC",
    pool_address="HTvjz...",
    lower_price=Decimal("95.0"),
    upper_price=Decimal("105.0"),
    base_amount=Decimal("0"),               # 0 for BUY side
    quote_amount=Decimal("50"),             # All in quote for BUY
    side=TradeType.BUY,
    # Auto-close when price exceeds these limits
    upper_limit_price=Decimal("106.05"),    # upper × (1 + threshold)
    lower_limit_price=Decimal("94.05"),     # lower × (1 - threshold)
    keep_position=True,                     # Controller handles position tracking
)
```

### Position Tracking (position_hold)

The controller tracks cumulative position changes:

```python
# After each LP executor closes:
base_net = (returned_base + base_fee) - initial_base
quote_net = (returned_quote + quote_fee) - initial_quote

position_hold_base += base_net
position_hold_quote += quote_net
```

This tracks:
- Net change from each LP position lifecycle
- Swap execution gains/losses
- Cumulative P&L across multiple rebalances

---

## Scenarios

### Initial Positions

#### side=1 (BUY) at price=100, threshold=1%

```
Amounts: base=0, quote=50 USDC
Bounds:  lower=95.0, upper=99.9 (offset creates out-of-range)
Limits:  lower_limit=94.05, upper_limit=100.90

Position:               [========]     *
                       95.0    99.9   100
                        ^              ^
                   lower_limit    upper_limit
                      94.05         100.90
```

**Auto-close triggers:**
- If price drops below 94.05 → Close, create new SELL position
- If price rises above 100.90 → Close, create new BUY anchored at buy_max

### Scenario: Price Drops Below Lower Limit

```
Before:     [========]     *
           95.0    99.9   100

Price drops to 93:

After:          *     [========]
               93    95.0    99.9

→ Price 93 < lower_limit 94.05
→ Executor AUTO-CLOSES
→ Controller detects completion
→ Creates SELL position anchored at sell_price_min
```

### Scenario: Price Rises Above Upper Limit

```
Before:     [========]     *
           95.0    99.9   100

Price rises to 102:

After:      [========]           *
           95.0    99.9         102

→ Price 102 > upper_limit 100.90
→ Executor AUTO-CLOSES
→ Controller detects completion
→ Creates new BUY anchored at buy_price_max (if 102 < buy_price_max)
```

---

## Edge Cases

### Config Validation

```python
if buy_price_max < buy_price_min:
    raise ValueError("buy_price_max must be >= buy_price_min")
if sell_price_max < sell_price_min:
    raise ValueError("sell_price_max must be >= sell_price_min")
if position_offset_pct < 0 and abs(position_offset_pct) > position_width_pct:
    raise ValueError("For in-range positions, |offset| must not exceed width")
```

### Bounds Validation

After calculating bounds, invalid positions are rejected:

```python
if lower >= upper:
    self.logger().warning(f"Invalid bounds [{lower}, {upper}] - skipping")
    return None
```

### Optional Price Limits (None)

If limits are not set:

| Limit | If None | Effect |
|-------|---------|--------|
| buy_price_max | No ceiling | BUY uses current_price as upper |
| buy_price_min | No floor | Lower bound not clamped |
| sell_price_min | No floor | SELL uses current_price as lower |
| sell_price_max | No ceiling | Upper bound not clamped |

---

## Database & Tracking

### Tables Used

| Table | Purpose |
|-------|---------|
| `Controllers` | Stores controller config snapshots |
| `Executors` | Stores executor state and performance |
| `RangePositionUpdate` | Stores LP position events (ADD/REMOVE) |

### Executor custom_info

The executor exposes state to the controller via `custom_info`:

```python
{
    "state": "IN_RANGE",           # Current state
    "position_address": "ABC...",  # On-chain position address
    "lower_price": 95.0,           # Position bounds
    "upper_price": 105.0,
    "current_price": 100.0,        # Current market price
    "base_amount": 0.1,            # Current amounts in position
    "quote_amount": 15.5,
    "base_fee": 0.0001,            # Collected fees
    "quote_fee": 0.05,
    "initial_base_amount": 0.0,    # Initially deposited
    "initial_quote_amount": 50.0,
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid bounds" | Calculated lower >= upper | Check price limits configuration |
| Position not created | Price outside valid range | Adjust price limits or wait |
| Autoswap failed | Insufficient balance for both directions | Fund wallet with more tokens |
| "Connector not found" | Wrong connector_name | Use network format (e.g., "solana-mainnet-beta") |

### Logging

Enable debug logging to see decision details:

```python
# In logs/logs_*.log
LPRebalancer - INFO - Creating position: side=BUY, pool_price=100.0, bounds=[95.0, 99.9], limits=[94.05, 100.90]
LPRebalancer - INFO - Autoswap: SELL 0.5 SOL for ~50 USDC
LPRebalancer - INFO - Swap completed successfully, proceeding to LP position
```

### Verifying Positions On-Chain

For Solana positions:
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

Visit https://skills.hummingbot.org/skill/lp-agent for full documentation.

**Install with:**
```bash
npx skills add hummingbot/skills --skill lp-agent
```

---

## Related Files

| File | Description |
|------|-------------|
| `controllers/generic/lp_rebalancer/lp_rebalancer.py` | Controller implementation |
| `hummingbot/strategy_v2/executors/lp_executor/` | Executor implementation |
| `hummingbot/connector/gateway/gateway.py` | Gateway connector (LP + Swap) |
