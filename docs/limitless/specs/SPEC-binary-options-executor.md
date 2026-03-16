# SPEC: BinaryOptionsExecutor

Custom executor extending `ExecutorBase` for binary options lifecycle.
Handles everything from entry through settlement/redemption.

## Why Custom (not PositionExecutor)

PositionExecutor handles standard triple-barrier (stop/TP/trailing/timeout).
Binary options need:
1. **BTC reversal exit** — cross-asset trigger (BTC spot moves against position)
2. **Settlement lifecycle** — hold winning positions to expiry for $1.00 payout instead of selling
3. **Redemption** — call `redeemPositions()` on-chain after market resolves
4. **Confirmed stop loss** — N consecutive ticks below threshold + grace period (not instant)
5. **Adaptive timeout with extensions** — extend timeout when position is trending favorably
6. **Take-profit squeeze** — TP threshold decays toward zero over time via exponential decay
7. **Maker rebate awareness** — prefer limit exits to earn rebates
8. **Mint path entries** — entry via mint + sell opposite (not just buy)

## File Structure

```
hummingbot/strategy_v2/executors/binary_options_executor/
├── __init__.py
├── binary_options_executor.py    ← THIS SPEC
├── data_types.py                 ← Config + enums
```

Register in `ExecutorOrchestrator._executor_mapping`:
```python
"binary_options_executor": BinaryOptionsExecutor
```

---

## 1. Config (data_types.py)

```python
class BinaryOptionsExecutorConfig(ExecutorConfigBase):
    type: Literal["binary_options_executor"] = "binary_options_executor"
    trading_pair: str                          # market slug
    connector_name: str = "limitless"
    side: TradeType                            # BUY or SELL
    amount: Decimal                            # position size in USDC
    direction: str                             # "YES" or "NO"
    entry_price: Optional[Decimal] = None      # None = market price

    # --- Entry method ---
    execution_path: str                        # from ExecutionPath enum (action_router)
    entry_order_type: str = "limit"            # "limit" | "market"

    # --- Barrier config ---
    stop_loss_pct: Decimal                     # e.g. 0.29 = -29% hard stop
    stop_loss_grace_secs: float = 20.0         # no stop in first N seconds
    stop_loss_confirm_ticks: int = 2           # consecutive ticks below threshold
    stop_loss_confirm_secs: float = 0.0        # seconds elapsed below threshold

    trailing_trigger_pct: Decimal              # arm trailing at this % profit
    trailing_distance_pct: Decimal             # close when profit drops this % from peak

    take_profit_threshold: Decimal             # initial TP target (from magnitude stats)
    tp_squeeze_factor: Decimal = Decimal("0.75")  # TP decay multiplier
    decay_exponent: Decimal = Decimal("2.0")   # time decay exponent for TP squeeze

    # --- Timeout ---
    base_timeout_secs: float                   # base position timeout
    max_timeout_multiplier: float = 2.905      # hard ceiling
    timeout_extension_factor: float = 1.3      # extension when trending
    max_timeout_extensions: int = 3

    # --- BTC reversal ---
    btc_reversal_multiplier: float = 5.24      # net BTC delta threshold
    btc_entry_spot_price: float                # BTC spot at entry (for delta tracking)

    # --- Settlement ---
    hold_to_settlement: bool = True
    settlement_hold_threshold: float = 0.70    # min prob of winning to hold

    # --- Market ---
    market_expiry_ts: float                    # UTC timestamp of market resolution
    strike_price: float                        # market strike
    coin: str                                  # ticker (for cross-ref)

    # --- Exit preferences ---
    exit_order_type: str = "limit"             # "limit" | "market"
```

---

## 2. Executor Lifecycle

```
on_start()
  └─ validate_sufficient_balance()
  └─ execute_entry()
       ├─ path = BUY_YES/NO → place buy order (limit or market)
       ├─ path = MINT_SELL_* → mint tokens, then place sell order
       └─ path = MINT_SELL_BOTH → mint, place sell YES + sell NO
     ↓
control_task() loop (every 0.5s):
  ├─ If entry not filled → control_entry_order()
  │   └─ Monitor fill, handle expiry/cancel
  │
  ├─ If entry filled → control_position()
  │   ├─ Update BTC spot price (from market_data_provider or connector)
  │   ├─ Update current YES/NO price
  │   ├─ Compute uPnL
  │   │
  │   ├─ PRIORITY 1: Market Expiry
  │   │   └─ market_expiry_ts reached?
  │   │      ├─ Winning + prob > threshold → HOLD (no action, await settlement)
  │   │      └─ Losing → market exit
  │   │
  │   ├─ PRIORITY 2: BTC Reversal
  │   │   └─ |btc_spot_now - btc_entry_spot| >= btc_reversal_multiplier
  │   │      AND direction opposes position?
  │   │      └─ EXIT
  │   │
  │   ├─ PRIORITY 3: Confirmed Stop Loss
  │   │   └─ uPnL% < -stop_loss_pct?
  │   │      ├─ Within grace period (< stop_loss_grace_secs since entry)? → skip
  │   │      ├─ Increment breach counter
  │   │      ├─ breach_ticks >= stop_loss_confirm_ticks
  │   │      │  AND breach_elapsed >= stop_loss_confirm_secs? → EXIT
  │   │      └─ Not confirmed yet → continue monitoring
  │   │
  │   ├─ PRIORITY 4: Trailing Stop Arm
  │   │   └─ uPnL% > trailing_trigger_pct?
  │   │      └─ Activate trailing, update peak_pnl = max(peak_pnl, current_pnl)
  │   │
  │   ├─ PRIORITY 5: Take Profit Squeeze
  │   │   └─ Compute decayed TP threshold:
  │   │      elapsed_frac = elapsed / base_timeout
  │   │      decayed_tp = threshold × (1 - elapsed_frac^decay_exp) × tp_squeeze_factor
  │   │      uPnL > decayed_tp? → EXIT (take profit)
  │   │
  │   ├─ PRIORITY 6: Trailing Stop Fire
  │   │   └─ trailing_active AND
  │   │      (peak_pnl - current_pnl) > trailing_distance_pct × peak_pnl?
  │   │      └─ EXIT (trailing stop)
  │   │
  │   └─ PRIORITY 7: Adaptive Timeout
  │       └─ elapsed > current_timeout?
  │          ├─ Trending favorably AND extensions < max? → extend timeout
  │          └─ Not trending OR max extensions → EXIT (timeout)
  │          "Trending" = price moved further in favorable direction since entry
  │
  └─ If SHUTTING_DOWN:
      └─ control_shutdown()
          ├─ Cancel open orders
          ├─ If holding tokens → sell (market or limit)
          └─ Wait for fills → TERMINATED
```

### Post-Settlement Flow
```
Market resolved (expiry passed, resolution available):
  ├─ Check if position won or lost
  ├─ If won AND holding tokens → call connector.redeem_positions(slug)
  │   └─ Winning tokens → $1.00 USDC per token
  ├─ If lost → tokens worth $0, write off
  └─ Record final PnL, set close_type, TERMINATE
```

---

## 3. State

```python
class BinaryOptionsExecutor(ExecutorBase):
    def __init__(self, strategy, connectors, config: BinaryOptionsExecutorConfig):
        super().__init__(strategy, connectors, config)

        # Entry tracking
        self._entry_order: Optional[TrackedOrder] = None
        self._exit_order: Optional[TrackedOrder] = None
        self._entry_filled: bool = False
        self._entry_timestamp: Optional[float] = None
        self._entry_avg_price: Decimal = Decimal("0")

        # Mint state (for mint paths)
        self._minted: bool = False
        self._mint_tx: Optional[str] = None
        self._yes_tokens: Decimal = Decimal("0")
        self._no_tokens: Decimal = Decimal("0")

        # Barrier state
        self._peak_pnl: Decimal = Decimal("0")
        self._trailing_active: bool = False
        self._stop_breach_ticks: int = 0
        self._stop_breach_started_at: Optional[float] = None

        # Timeout state
        self._extensions_used: int = 0
        self._current_timeout: float = config.base_timeout_secs

        # BTC tracking
        self._btc_spot_current: float = config.btc_entry_spot_price

        # Settlement
        self._awaiting_settlement: bool = False
        self._settled: bool = False
```

---

## 4. Key Methods

### Entry

```python
async def execute_entry(self):
    path = self.config.execution_path
    if path in ("buy_yes_limit", "buy_no_limit"):
        self._entry_order = self.place_order(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            side=TradeType.BUY,
            amount=self.config.amount,
            price=self.config.entry_price
        )
    elif path in ("buy_yes_market", "buy_no_market"):
        self._entry_order = self.place_order(
            order_type=OrderType.MARKET, ...
        )
    elif path.startswith("mint_sell"):
        # Step 1: mint tokens
        connector = self.connectors[self.config.connector_name]
        self._mint_tx = await connector.mint_tokens(
            self.config.trading_pair, float(self.config.amount)
        )
        self._minted = True
        self._yes_tokens = self.config.amount
        self._no_tokens = self.config.amount
        # Step 2: sell opposite side
        if "sell_no" in path:
            self._entry_order = self.place_order(side=TradeType.SELL, ...)
        elif "sell_yes" in path:
            self._entry_order = self.place_order(side=TradeType.SELL, ...)
        elif "sell_both" in path:
            # Two sell orders
            self._sell_yes_order = self.place_order(...)
            self._sell_no_order = self.place_order(...)
```

### BTC Price Updates

```python
def update_btc_price(self, btc_spot: float):
    """Called by controller each tick with latest BTC spot."""
    self._btc_spot_current = btc_spot
```

Controller calls this in `update_processed_data()` for all active binary options executors.
The executor uses it in Priority 2 (BTC reversal) check.

### Exit

```python
def _execute_exit(self, close_type: CloseType, reason: str = ""):
    if self.config.exit_order_type == "market":
        self._exit_order = self.place_order(OrderType.MARKET, side=SELL, ...)
    else:
        self._exit_order = self.place_order(OrderType.LIMIT_MAKER, side=SELL, ...)
    self.close_type = close_type
```

### Settlement

```python
async def _handle_settlement(self):
    """Called when market has resolved."""
    connector = self.connectors[self.config.connector_name]
    # Check if our side won
    market_info = await connector.get_market(self.config.trading_pair)
    if market_info.get("resolved"):
        winning_side = market_info.get("winning_side")  # "YES" or "NO"
        if winning_side == self.config.direction:
            # Redeem winning tokens for $1.00 each
            result = await connector.redeem_positions(self.config.trading_pair)
            self.close_type = CloseType.COMPLETED
        else:
            # Tokens worth $0
            self.close_type = CloseType.STOP_LOSS  # lost at settlement
        self._settled = True
        self.stop()
```

### PnL

```python
def get_net_pnl_quote(self) -> Decimal:
    if self._settled:
        if winning: return self._tokens_held - self._total_cost - self.cum_fees
        else: return -self._total_cost - self.cum_fees
    if not self._entry_filled:
        return Decimal("0")
    current_price = self.get_price(...)
    return (current_price - self._entry_avg_price) * self._tokens_held - self.cum_fees

def get_net_pnl_pct(self) -> Decimal:
    if self._total_cost == 0: return Decimal("0")
    return self.get_net_pnl_quote() / self._total_cost
```

---

## 5. CloseTypes (extension)

Add to existing `CloseType` enum or use custom:
```python
# Reuse existing where possible:
STOP_LOSS = 2           # confirmed stop loss
TAKE_PROFIT = 3         # TP squeeze hit
TRAILING_STOP = 6       # trailing stop fired
TIME_LIMIT = 1          # adaptive timeout expired
EARLY_STOP = 5          # controller-initiated stop

# New (may need custom enum or string field):
BTC_REVERSAL = "btc_reversal"
SETTLEMENT_WIN = "settlement_win"
SETTLEMENT_LOSS = "settlement_loss"
MARKET_EXPIRY_EXIT = "market_expiry_exit"
```

---

## 6. Registration

In `ExecutorOrchestrator.__init__` or `_executor_mapping`:
```python
_executor_mapping = {
    ...existing...,
    "binary_options_executor": BinaryOptionsExecutor,
}
```

---

## 7. Phase Plan

### Phase 1 (MVP — use PositionExecutor)
Controller sends `PositionExecutorConfig` with `TripleBarrierConfig`.
Handles: stop loss (instant, not confirmed), trailing, timeout, TP.
Missing: BTC reversal (controller workaround via StopExecutorAction), settlement, confirmed stops, TP squeeze.

### Phase 2 (This spec — BinaryOptionsExecutor)
Full custom executor with all 7 priority exits, settlement, redemption, mint paths.
Controller sends `BinaryOptionsExecutorConfig`.
BTC reversal moves from controller into executor.

### Phase 3 (Optimization)
- Maker rebate tracking (log how much earned per position)
- LP reward estimation
- Smart exit routing (limit if time allows, market if urgent)
- Partial exits (sell portion, hold rest to settlement)

---

## 8. Source References

| Logic | Source |
|-------|--------|
| 7-priority exit cascade | `system-map/02-orchestration-execution.md` § 2.5 (check_positions) |
| Stop loss confirmation | `02` § 2.5 — breach counter + grace period |
| Trailing stop arm/fire | `02` § 2.5 — trigger_pct + distance_pct |
| TP squeeze + decay | `02` § 2.5 — magnitude_threshold × (1 - frac^decay) × squeeze |
| Adaptive timeout + extensions | `02` § 2.5 — trending check, extension_factor, max_extensions |
| BTC reversal | `02` § 2.5 — net_btc_delta >= multiplier |
| Settlement/redeem | `04` § 1 — connector.redeem_positions() |
| Mint entry path | `SPEC-execution-paths.md` paths 3-4, 8-9, 11 |
| Walk-the-book (replaced) | `02` § 2.4 — now real fills from connector |
| Position dataclass (reference) | `02` § 2.2 — 50+ field Position, maps to executor state |
| ExecutorBase API | `V2-REFERENCE.md` § 4 |
| PositionExecutor reference | `V2-REFERENCE.md` § 5 |
| ExecutorOrchestrator registration | `V2-REFERENCE.md` § 7 |
