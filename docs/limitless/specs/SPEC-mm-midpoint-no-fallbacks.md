# SPEC — Use venue midpoint anchors in MM path (no synthetic fallbacks)

## Objective
Make Hummingbot MM quoting use the **venue-provided midpoint (`adjustedMidpoint`) as primary anchor** and remove trading-critical synthetic fallbacks.

## Hard safety rule
If required live book data is missing/invalid/stale for a coin, do **not** compute new quote prices for that coin and do **not** place/update new orders for that coin on that tick.

No default 0.5 midpoint for execution decisions.
No recycled unknown midpoint for execution decisions.

## Scope
- `/home/tiger/hummingbot/controllers/generic/binary_options/market_manager.py`
- `/home/tiger/hummingbot/controllers/generic/binary_options/controller.py`
- `/home/tiger/hummingbot/controllers/generic/binary_options/quote_manager.py`
- tests under `/home/tiger/hummingbot/controllers/generic/binary_options/tests/`

Do NOT change connector/websocket architecture.

## Required behavior changes

### 1) Market data fields + midpoint precedence (market_manager)
In `build_market_data()`, compute/store explicit fields per coin from top-of-book:
- `yes_bid` = best bid
- `yes_ask` = best ask
- `yes_mid_local` = (yes_bid + yes_ask) / 2 when both sides present
- `yes_mid_api` = API `adjustedMidpoint` when present/valid
- `yes_mid` chosen by strict precedence:
  1. `yes_mid_api` (primary)
  2. `yes_mid_local` (fallback only if both bid+ask are valid)
  3. otherwise invalid/no midpoint for trading
- `no_bid` = 1 - yes_ask
- `no_ask` = 1 - yes_bid
- `no_mid` = 1 - yes_mid (only when yes_mid valid)

Keep compatibility fields if needed, but ensure controller MM path reads `yes_mid` (not bid-as-mid).

### 2) Validity gating
A coin is "quote-valid" when:
- `yes_mid_api` is present and valid in (0,1), OR
- both `yes_bid` and `yes_ask` are present and valid in (0,1) with bid < ask (to form local fallback midpoint).

If not valid:
- mark as invalid for that tick
- do not provide trading midpoint for that coin

### 3) Controller MM input wiring
In MM branch of `controller.py`, set:
- `orderbook_mids[coin] = md["yes_mid"]` for valid coins only
Pass only valid coins into quote tick.

### 4) Quote manager behavior on missing mid
In `QuoteManager.tick/_tick_coin`, if coin lacks required mid/reward inputs for this tick:
- return no place/update actions for that coin
- optionally cancel stale quotes only if existing policy already does so (do not add aggressive new behavior unless needed)

### 5) Preserve existing strategy math
Do not alter z-score logic, inner/outer fractions, or skew formula in this task.
Only change the price anchor to true midpoint and enforce no-fallback safety gating.

## Tests
Add/update tests to verify:
1. midpoint precedence: API `adjustedMidpoint` is preferred over local midpoint when both exist
2. local midpoint fallback is used only when API midpoint missing/invalid and bid+ask are valid
3. controller uses `yes_mid` (not `yes_price`) as quote anchor
4. missing/invalid midpoint data causes no new quote actions for that coin
5. NO derivation is complementary (`no_mid = 1 - yes_mid`) when midpoint valid
6. existing quote math still runs when valid midpoint exists

## Validation
- run targeted tests for touched modules
- run lint hooks if configured

## Deliverables
- patch with above behavior
- summary of changed files
- exact test commands + results
- commit hash
