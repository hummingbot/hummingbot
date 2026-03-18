# SPEC: MM Single-Order Gating + Paper Budget Consistency

## Goal
Fix two production blockers in binary-options MM:

1) Repeated `Not enough budget to open position` / collateral-style failures during paper tests.
2) Multiple simultaneous open quotes on same side due to cancel/replace race.

Hard requirement from Tiger:
- Never allow multiple open quotes per side.
- On update, wait for old quote to be fully canceled/closed before placing replacement.

## Symptoms Observed

### A) Budget/out-of-funds spam
- `PositionExecutor - ERROR - Not enough budget to open position` repeated.
- In old logs also saw exchange `HTTP 400 Insufficient collateral balance`.
- Connector startup log can show `paper=False` before controller applies `paper_mode=True`.

### B) Multi-open quote race
- `update` currently emits `StopExecutorAction(old_id)` and `CreateExecutorAction(new)` in the same tick.
- If cancel ack is delayed, this can temporarily create overlap (old + new both open/in-flight).
- This also causes noisy budget reservation collisions.

## Root Causes

1) Paper-mode is not guaranteed early/consistently for all budget-related paths.
2) MM lifecycle is optimistic; it does not serialize replacement by waiting for confirmation.

## Required Changes

## 1) Strict serialized replace in controller (no overlap)
File: `controllers/generic/binary_options/controller.py`

Add pending replacement state:
- `_mm_pending_replacements: Dict[str, dict]` where key=`"{coin}:{side}"`
- Value contains desired quote payload (`coin`, `side`, `price`, `size`, `trading_pair`, `ts`)

Behavior:
- For `qa.action == "update"`:
  - If active mapped executor exists: emit ONLY `StopExecutorAction(old_id)`.
  - Store desired replacement in `_mm_pending_replacements[key]`.
  - Do NOT create new executor in same tick.
- For `qa.action == "place"`:
  - If key has active executor OR pending replacement, skip (no duplicate place).
- For `qa.action == "cancel"`:
  - Stop mapped executor and clear pending replacement for that key.
- After syncing `executors_info` closed states each tick:
  - If key has no active mapped executor and has pending replacement, then create replacement executor and clear pending entry.

Guardrails:
- Maximum one live/in-flight quote per key (`coin:side`) at all times.
- Replacement creation only after old executor transitions to closed/not mapped.
- Keep existing behavior for on-fill opposing-side cancel.

## 2) Paper mode consistency for budget checks
Files:
- `hummingbot/connector/exchange/limitless/limitless_exchange.py`
- possibly `controllers/generic/binary_options/controller.py` (if needed for ordering)

Requirements:
- In paper mode, internal available balance used by budget checker must not block opening tiny test orders due to real wallet collateral state.
- Keep real mode behavior unchanged.

Implementation approach:
- In `_update_balances()`:
  - if `self.paper_mode` is True, set synthetic USDC balances (large fixed amount, e.g. 1_000_000) for `_account_balances` and `_account_available_balances`, then return.
  - skip on-chain and collateral reads in this branch.
- Keep `paper_mode` setter propagation to inner connector.
- Ensure logs clearly state paper balance mode is active (debug/info once).

Rationale:
- Paper tests should validate logic flow, not fail on real collateral.

## 3) Optional churn reduction (low risk)
File: `controllers/generic/binary_options/controller.py`

- De-duplicate repeated pending replacement updates for same key by replacing payload (latest quote wins), not queueing multiple.

## Tests

### Unit tests: controller
File: `controllers/generic/binary_options/tests/test_controller.py`

Add tests:
1. `update` emits stop only; no create same tick when mapped executor exists.
2. pending replacement creates new executor only after old executor appears closed/unmapped.
3. no duplicate place when pending replacement exists.
4. cancel clears pending replacement.

### Unit tests: limitless exchange
File: `test/hummingbot/connector/exchange/limitless/test_limitless_exchange.py`

Add tests:
1. in `paper_mode=True`, `_update_balances()` writes synthetic USDC balance and bypasses external reads.
2. in `paper_mode=False`, existing path remains intact (smoke assertion).

## Non-goals
- No redesign of quote math.
- No changes to signal thresholds.
- No dashboard/API work.

## Acceptance Criteria
- During paper run, no `Not enough budget to open position` spam.
- No side ever has >1 active/in-flight quote at once.
- update path is serialized (stop-confirm-then-create).
- Existing MM quoting behavior remains functionally the same apart from race elimination.
