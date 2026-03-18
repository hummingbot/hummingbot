# SPEC: Canonical Price Surface + Single NO Transform

## Objective
Fix wrong-side / wrong-space quote placement (e.g. YES ~0.769 context but orders around 0.20) without changing strategy intent.

## Hard constraints (must keep)
1. Keep midpoint priority exactly as-is:
   - `yes_mid = adjustedMidpoint` from exchange when valid
   - fallback to local `(yes_bid + yes_ask) / 2` only if exchange midpoint invalid/missing
2. Keep current signal semantics (signal modulates quoting/pull behavior; not direct entry trigger logic rewrite).
3. No strategy redesign. Minimal plumbing fix only.

## Root issue hypothesis
Prices are derived in one place but transformed/reinterpreted again later, causing side/space mismatch.

## Required implementation

### 1) Canonical per-tick price surface (single source of truth)
In the market-data build path, produce and carry this exact structure for each coin:
- `yes_bid`
- `yes_ask`
- `yes_mid` (exchange adjustedMidpoint preferred; local fallback)
- `no_bid = 1 - yes_ask`
- `no_ask = 1 - yes_bid`
- `no_mid = 1 - yes_mid`
- `quote_valid`

Do this once per tick. Keep values immutable downstream (read-only usage).

### 2) Single-transform rule
NO derivation must happen exactly once (step above).
- Remove/avoid any additional `1 - x` transforms in downstream quote/action/executor configuration paths that already receive side-native prices.
- Controller/quote_manager should consume canonical YES/NO surfaces directly.

### 3) Side-native quoting
When producing QuoteActions:
- YES side prices must be based on YES surface.
- NO side prices must be based on NO surface.
No cross-space reuse.

### 4) Guardrails (runtime checks)
Before emitting a place/update action, validate side-consistency:
- YES action price must be finite and in (0,1).
- NO action price must be finite and in (0,1).
- If invalid/inconsistent, skip action and log a concise invariant failure line including coin, side, price, and canonical surface.

### 5) Minimal observability
Add one concise debug/info line per place/update showing:
- coin, side, chosen price
- yes_bid, yes_ask, yes_mid, no_bid, no_ask, no_mid
This is for verifying correctness during paper tests.

## Non-goals
- Do not modify midpoint source priority rule.
- Do not alter signal thresholds/weights.
- Do not redesign market selection.

## Tests
Update/add focused tests to prove:
1. Canonical surface values are built correctly from YES book.
2. NO transform is performed exactly once.
3. NO QuoteActions do not get re-flipped in downstream controller path.
4. Invariant guard blocks malformed side prices.

## Acceptance criteria
1. In paper run, first place/update prices align with canonical surfaces (no 0.20-style mismatch when YES context is ~0.7+ unless explicitly intended by quoting offsets from surface and logged as such).
2. No duplicate hidden transform of NO prices.
3. Existing midpoint priority behavior remains unchanged.
