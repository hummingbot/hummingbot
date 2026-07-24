# Prediction Markets Connector — Architecture Findings

Status: research / scoping. Source-of-truth is the current `development` branch.
Target venues: **Hyperliquid (HIP-4)**, **Polymarket**, **Kalshi**.

These three are fundamentally the same instrument: a **binary outcome share/contract that
trades on a CLOB at a price in (0, 1) and settles to exactly 0 or 1** in a stable quote
(USDC / USDH / USD). On Hyperliquid HIP-4 each side is a `#N` coin (`N = 10*outcome + side`);
on Polymarket each side is an ERC-1155 outcome token; on Kalshi each side is a Yes/No contract.
In every case you *buy and sell a token/contract* — you do not take a margined position.

---

## 1. Core design decision: spot order plumbing **+ a reused position concept**

**Recommendation: build on `ExchangePyBase`'s spot order/balance machinery (`ConnectorType.Exchange`,
plain `OrderCandidate` — no leverage/funding/margin), but compose it with a `PositionMode`-aware
position-tracking layer reused from `PerpetualTrading`. Do NOT derive from
`PerpetualDerivativePyBase`; do adopt the position *concept*.**

This is a refinement of an earlier "pure two-spot-pairs, no positions" idea, which broke on Kalshi
(see below). The position concept is needed; the perpetual *machinery* is not.

### Why the perpetual base class is still wrong
`PerpetualDerivativePyBase` forces abstract methods with no meaning here — `get_funding_info`,
`set_leverage`, `get_buy/sell_collateral_token` — and `PerpetualOrderCandidate` divides collateral
by leverage. Spot collateral is already correct: a BUY needs `amount * price` in quote (USDC), a
SELL needs the base amount (`core/data_type/order_candidate.py`, `connector/budget_checker.py`).
So the **order pipeline stays spot**.

### Why we nonetheless need the position concept
The three venues disagree on the *unit of inventory*, and this maps exactly onto the existing
`PositionMode` enum:

| Venue | Native model | Hold both sides? | `PositionMode` |
|-------|--------------|------------------|----------------|
| Polymarket | two ERC-1155 tokens (YES/NO), separate books, optional CTF merge | **Yes** | **HEDGE** |
| Hyperliquid HIP-4 | two `#N` coins, separate spot books | **Yes** | **HEDGE** |
| Kalshi | one auto-netted signed position, one mirrored book | **No** (10 Yes + 5 No → net 5 Yes, $5 collateral returned) | **ONEWAY** |

This is *precisely* the distinction `PerpetualTrading.position_key()` already encodes
(`connector/perpetual_trading.py:126-139`): HEDGE keys positions by `trading_pair + side` (two
positions per market); ONEWAY keys by `trading_pair` (one net position). A naive two-spot-pairs
model can't represent Kalshi: a spot BUY of 15 NO while holding 10 Yes should yield "15 NO," but
Kalshi nets to 5 NO — violating the spot fill→balance invariant. With positions, that action is
simply `CLOSE 10` + `OPEN 5`, which *is* the netting.

### The position concept is separable from the perp machinery
`PerpetualTrading` bundles two independent concerns. Only the first is reused:
- **Reusable (no perp dependency):** `_account_positions: Dict[str, Position]`, `_position_mode`,
  `position_key()`, `get/set/remove_position`, `set_position_mode`.
- **Dropped (perp-only):** `_leverage`/`get/set_leverage`, `_funding_info` + funding updater,
  `get_buy/sell_collateral_token` (already deprecated).

`Position` (`connector/derivative/position.py`) is already the right shape — `trading_pair`,
`position_side`, `entry_price`, `amount`, `unrealized_pnl` — its only perp-ism is a `leverage`
field (set to 1, or omit in our variant). `PositionMode`/`PositionSide`/`PositionAction` live in
`core/data_type/common.py` and are **not** perp-exclusive: `InFlightOrder.position` defaults to
`NIL` and `TradeFill.position` is a column, so a spot-order connector can legitimately stamp
`OPEN`/`CLOSE` to drive netting.

### Why this converges three problems at once
1. **Netting / hold-both-sides** — `position_mode` + `position_key` (HEDGE vs ONEWAY).
2. **Polymarket-style PnL** — `Position.entry_price` + `unrealized_pnl` is exactly the cost-basis
   "position view" the portfolio UI shows; no perpetual stack needed.
3. **Settlement** — the position is the natural object to close at the 0/1 resolution value (§3.4),
   rather than chasing balance deltas.

### Packaging decision (open)
Either **extract** the position-tracking half of `PerpetualTrading` into a shared `PositionTracker`
component (DRY, but edits a class all ~25 perp connectors depend on → regression surface), or
**replicate** a lightweight `PositionTracker` for prediction markets only (zero blast radius, mild
duplication). Lean: **replicate now, converge later.** The connector is then
`ExchangePyBase` (spot orders) + `PositionTracker` (mode-aware net inventory), e.g. a new
intermediate `PredictionMarketPyBase`.

---

## 2. What works as-is (reusable without modification)

The order pipeline is price-range agnostic — there are **no hardcoded price floors/ceilings** and
nothing rejects a price < 1.0:

- **Quantization** (`exchange_py_base.py` `get_order_price_quantum` / `quantize_order_*`): purely
  arithmetic against `TradingRule.min_price_increment`; a [0,1] price quantizes fine.
- **Spot collateral / budget checker**: `amount*price` (buy) / base amount (sell) — correct for
  outcome shares. Use plain `OrderCandidate`, never `PerpetualOrderCandidate`.
- **Fees** (`core/data_type/trade_fee.py`): `TradeFeeSchema` supports zero maker/taker and empty
  flat-fee lists, covering HIP-4's zero open fee.
- **Order/trade types** (`core/data_type/common.py`): `LIMIT`, `MARKET`, `LIMIT_MAKER`, `BUY`,
  `SELL` are all available to spot connectors with no framework restriction.
- **In-flight order tracking** (`core/data_type/in_flight_order.py`): no price-bound validation.
- **Multi-pair per connector**: connectors take `trading_pairs: List[str]`; `OrderBookTracker`
  keeps a `Dict[str, OrderBook]`. An event with N sides = N pairs on one connector.
- **Registration / connect flow**: folder-scan + `<name>_utils.py` metadata
  (`KEYS`, `EXAMPLE_PAIR`, `DEFAULT_FEES`, `CENTRALIZED`), credential storage, and the `connect`
  command all work for a non-gateway, non-eth-wallet spot connector with no changes
  (`client/settings.py`, `client/command/connect_command.py`).
- **V2 controllers**: market-making spreads are percentage-of-mid
  (`market_making_controller_base.py`: `price = ref * (1 ± spread_pct)`), which behaves sensibly on
  a 0–1 asset. Candles are **optional** (`controller_base.get_candles_config()` defaults to empty),
  so the absence of OHLCV history does not block controllers.
- **PnL math** in `position_executor` is ratio-based (`(close-entry)/entry`) and is numerically
  correct on 0–1 prices — the problem is *settlement*, not the arithmetic (see §5).

---

## 3. What needs adapting (and why)

### 3.1 Trading-pair naming / symbol mapping
**Why:** The `BASE-QUOTE` (single hyphen, exactly two parts) convention is assumed throughout:
`connector/utils.py:split_hb_trading_pair` (`base, quote = pair.split("-")`),
`validate_trading_pair`, and `markets_recorder.py` (`base, quote = evt.trading_pair.split("-")`)
plus the `Order`/`TradeFill` schema columns. Native symbols like Hyperliquid `#1421` or multi-word
event names (`"2026 NBA Finals champion / New York"`) will break naive parsing or DB persistence.
**Adapt:** Define a clean HB-side pair scheme that is always exactly two hyphen-parts (e.g.
`NBAFINALS26NY-USDC`) and maintain a connector-internal symbol map between that and the venue
symbol (`#1421` / token id / ticker). This is the same `trading_pair_symbol_map` pattern existing
connectors use, but the naming scheme must be designed so the base token encodes event+side
unambiguously without extra hyphens.

### 3.2 Bounded [0,1] prices
**Why:** `TradingRule` has `min_price_increment` but **no `min_price`/`max_price`**. The pipeline
won't reject a price of 1.5 or −0.1, and percentage barriers can compute impossible prices
(a +60% take-profit on a 0.63 share = 1.008). The only precedent for price bounds is connector-local
(`architect_perpetual` `AdditionalInstrumentInfo.upper/lower_price_bound`), not in the shared model.
**Adapt:** Clamp/validate order prices to (0,1) in the connector, and clamp executor-derived prices
(TP/SL) to the bound. Optionally extend `TradingRule` with `min_price`/`max_price` (shared-model
change) so the bound is declared once and reused by quantization and executors.

### 3.3 Settlement / resolution — the net-new concept
**Why:** This has **no analog anywhere in the codebase.** All ~25 derivative connectors are
perpetual-only; dated/expiring futures are actively filtered out (e.g. `bitget_perpetual_utils.py`
rejects any symbol with a `deliveryPeriod`). There is no instrument-level expiry/settlement
timestamp, no settlement-price push, and no forced-close-at-settlement. `FundingInfo` carries only
`next_funding_utc_timestamp` (a recurring event, not a terminal date); `OrderExpirationEntry` is
order-level; Bybit `"Settling"` / Hyperliquid `"delistedCanceled"` map only to order **cancellation**.
**Adapt (new):**
- A market-state lifecycle (active → resolved/settled) with a settlement timestamp and settlement
  value (0 or 1) per market.
- A connector-emitted **settlement/resolution event**.
- Balance handling that credits the held token at its settlement value (winning → 1.00 quote,
  losing → 0.00) **without a closing trade**, since there is no counterparty at resolution. With
  the position concept (§1), this is a position close at the 0/1 value rather than a balance-delta hunt.
- Guarding `get_price` when the book goes one-sided/empty near resolution (best bid → 0 / NaN),
  which would otherwise break any mid/PnL division.

### 3.4 V2 executor layer
**Why:** `position_executor` models a continuously-traded instrument you exit by *trading out before
a self-chosen timer*. Its `is_expired`/`end_time` is the executor's own `triple_barrier.time_limit`
(unrelated to the market's resolution date), and on expiry it places a **MARKET close order** into
the book (`control_time_limit` → `place_close_order_and_cancel_open_orders`). For a prediction market
you usually want to **hold to settlement** and be auto-credited 0/1, not market-sell into a thin book
at an arbitrary deadline. Its PnL also only realizes a settled outcome if it happens to trade out
near 1.00 first.
**Adapt:** Introduce a settlement-aware executor (new `PredictionMarketExecutor`, sibling to
`position_executor`, rather than mutating it) with: a terminal `CloseType.SETTLED` that books PnL
from the settlement value with no closing trade; [0,1] clamping of entry/TP/SL; and "hold to
resolution" semantics reusing the time-limit hook pointed at the resolution date. The underlying
ratio-PnL math is reused as-is.

### 3.5 Rate oracle / balance & PnL display
**Why:** Outcome tokens (YES/NO) are not on any external rate source (Binance/CoinGecko). The system
degrades gracefully but imperfectly: `balance` shows global value `0` when a rate is missing
(`balance_command.py`), and fee-token conversion is skipped with a warning (`client/performance.py`).
PnL falls back to last trade price, which is acceptable since shares resolve to 0/1.
**Adapt:** Register the connector with `RateOracle` so the live order book supplies the rate, and/or
special-case outcome tokens whose USD value is simply the mid price (quote is already a stablecoin).
Not breaking — but needed for correct balance/PnL display.

### 3.6 Connector taxonomy (minor)
**Why:** `ConnectorType` (`client/settings.py`) has `Exchange / Derivative / CLOB_SPOT / CLOB_PERP /
GATEWAY_DEX / Connector`. Riding `ConnectorType.Exchange` requires **no enum/scan changes** and
auto-includes the connector in `get_exchange_names()`, the connect flow, and spot strategy
whitelists.
**Adapt:** Prefer reusing `Exchange`. Only if prediction markets need distinct UI/strategy gating do
we add a category (which then touches the folder scan at `settings.py` and the
`get_exchange_names()/get_derivative_names()` getters). A lightweight marker flag on
`ConnectorSetting` is likely enough to distinguish them in the UI without a full new type.

### 3.7 Candles / data feeds (minor)
**Why:** Prediction markets have no conventional OHLCV history and resolve. Candles are optional in
controllers, so nothing breaks, but **candle/indicator-driven directional controllers are largely
inapplicable**; market-making, spread, and cross-venue arbitrage controllers fit naturally.
**Adapt:** Don't wire candle configs for these markets; favor book-/probability-driven controllers.

---

## 4. Settlement layer — system-wide implications

Settlement is the one genuinely net-new primitive. Its root property: **settlement is a non-trade,
externally-triggered, possibly-fractional, possibly-delayed terminal event.** Everything below
follows from those four traits. Note "fractional": the live "2026 NBA Finals champion" market we
queried resolves to **0.5** if no champion is declared by the deadline — so the settlement value is
a `Decimal` in `[0,1]`, **not** `{0,1}`.

### Key design lever: model settlement as a synthetic fill
Emit settlement as a **synthetic close `TradeFill`** at the resolution value (1.0 / 0.0 / 0.5) for
the held quantity, produced by the connector when the venue resolves. If settlement enters the
system as a fill, the existing PnL / reporting / persistence pipeline absorbs it for free. The
alternative (a separate settlement table + event that every reporter special-cases) is a schema
migration plus many call-site changes. **Recommend synthetic-fill** — it is the difference between
settlement touching ~2 places vs. ~10. The implications below assume this lever and note where it
still leaks.

### PnL & accounting
- **Realized PnL with no order.** Standard PnL is trade-paired or balance-based
  (`client/performance.py`: `cur_value = cur_base_bal*cur_price + cur_quote_bal`). Without a synthetic
  fill, a held-to-resolution position reads as a dangling open buy forever, and `cur_price` goes
  stale once the book disappears (`stored_or_live_rate → None → trades[-1].price`). The synthetic
  fill closes the loop and lets cost-basis (`avg_entry`, `Position.entry_price`) settle correctly.
- **PnL is bimodal, not continuous.** Terminal PnL per position is `(settlement − avg_entry) * qty`
  — a win/loss/void fork. Pre-resolution PnL is mark-to-mid; reporting must distinguish "marked"
  from "realized at settlement" and treat 0.5 as a partial refund, not a clean win/loss.
- **Settlement fees have no home** unless they ride the synthetic fill (fees attach to fills in the
  pipeline). Per-venue: HIP-4 zero open fee; Kalshi/Polymarket differ.

### Reporting / persistence / UI
- **`history` / `status` must make long-lived holds legible** — a position open for weeks awaiting a
  result should show resolution date + current mark, not read as a stuck order.
- **DB / `markets_recorder`**: synthetic fill ⇒ no schema change (`TradeFill.position` already
  exists). Otherwise ⇒ migration + settlement table.
- **Remote reporting (`remote_iface` / MQTT)** inherits the same need to surface settled vs. open
  exposure.

### Executors
- **Lifetime grows from seconds–hours to days–weeks**, breaking two assumptions: (1) the triple-barrier
  `time_limit` currently triggers a *market close into the book* — wrong here; the resolution date must
  mean "hold and await settlement." (2) **Restart survival**: held-position state must persist and, on
  startup, reconcile whether the market resolved while the bot was offline (query venue settlement
  status, then book the synthetic fill retroactively).
- **TP/SL semantics shift**: stop-loss becomes "exit before resolution if probability moved against
  me" — a deliberate choice, not a default. `CloseType.SETTLED` is the primary terminal state.
- **`ExecutorOrchestrator`** must tear down settled executors cleanly and aggregate realized PnL.

### Strategies / controllers / capital
- **Capital is locked until resolution.** Controllers allocate `total_amount_quote` assuming
  recyclable capital; here it is illiquid for days. Avoid opening positions near market close.
- **Settlement risk is a new risk axis for market-making**: an MM flat in dollar terms but holding
  residual shares at resolution takes a **binary wipeout** on the losing side — inventory does not
  retain value like spot inventory. Flatten (or knowingly accept) settlement exposure before close.
- **Cross-venue convergence arb becomes first-class and safer**: buy YES on venue A + NO on venue B
  when prices sum to < 1; holding both to settlement locks the spread regardless of outcome (the
  prediction-market analog of `scripts/v2_funding_rate_arb.py`). Requires holding both legs to
  settlement **and an event-identity mapping across venues** (same event has different IDs on Kalshi
  / Polymarket / HL) — a new cross-connector concern with no current analog.

### Risk & operational
- **Disputes / voids / delays**: Polymarket UMA disputes can delay/reverse; Kalshi can void to 0.5.
  Settlement value is `Decimal` in `[0,1]`; settlement timing is an estimate, not a guarantee.
- **Source of truth is the venue, asynchronously**: the connector polls/subscribes for resolution;
  open orders at resolution are venue-cancelled and need cleanup; restart reconciliation is mandatory.

### New events / data types
- A `MarketResolvedEvent` / `PositionSettledEvent` through the pubsub system for executors/strategies.
- A market-info field carrying **state (active/halted/resolved) + resolution timestamp + settlement
  value** (this is also where the §3.3 market lifecycle lives).

**Throughline:** settlement is cheap if it enters as a synthetic fill and the position object owns
the lifecycle; it gets expensive only where *time* enters — long capital lockup, restart/offline
reconciliation, and settlement-as-risk for strategies. Those three deserve the design attention.

---

## 5. Net-new vs. reusable — summary

| Area | Verdict |
|------|---------|
| Spot order pipeline, quantization, collateral, fees (`ExchangePyBase`, `OrderCandidate`) | **Reuse as-is** |
| Multi-pair tracking, registration, connect flow, credential storage | **Reuse as-is** |
| V2 controller spread/amount math; candles optional | **Reuse as-is** |
| PnL ratio math in executors | **Reuse as-is** |
| Position concept: `PositionMode`/`PositionSide`/`Position`/`position_key` (HEDGE vs ONEWAY netting) | **Reuse the concept, drop perp machinery (extract or replicate `PositionTracker`)** |
| Trading-pair naming + venue symbol map | **Design + per-venue code** |
| [0,1] price bounds (clamp; optional `TradingRule` fields) | **Small shared-model change + connector validation** |
| Rate-oracle registration / balance display for outcome tokens | **Small adaptation** |
| Settlement / resolution lifecycle + event + balance credit | **Net-new (no analog exists)** |
| Settlement-aware executor (`PredictionMarketExecutor`) | **Net-new (sibling to position_executor)** |
| Connector taxonomy marker | **Optional, minor** |

---

## 6. Why an "expiring futures" analog does not already exist

Searched the full connector and core-data layers: **no dated/quarterly/expiring futures, no
instrument-level expiry or settlement field, no settlement-price distribution, and no
forced-close-at-settlement** anywhere. The codebase is entirely perpetual-focused and even rejects
dated contracts at the symbol-filter stage. Consequently the settlement lifecycle (§3.3) and the
settlement-aware executor (§3.4) are genuinely new scaffolding, not adaptations of an existing
pattern. Everything else is either reusable spot machinery or a small, well-scoped change.

---

## 7. Open questions

- **`PositionTracker` packaging**: extract the position-tracking half of `PerpetualTrading` into a
  shared component (DRY, but regression surface across ~25 perp connectors) vs. replicate a
  lightweight tracker for prediction markets only (lean: replicate now, converge later).
- **Pair naming scheme**: exact human-readable base-token format that stays single-hyphen and
  encodes event + side unambiguously across all three venues.
- **Settlement source of truth**: each venue's API/event for resolution (Hyperliquid on-chain HIP-4
  resolution, Polymarket UMA/CTF redemption, Kalshi settlement) and how the connector surfaces it.
- **Venue connector type**: Polymarket (on-chain EVM CLOB, wallet signing — possibly Gateway) vs.
  Kalshi (REST, custodial CEX-like) vs. Hyperliquid (HyperCore CLOB, reuses existing HL infra).
- **Whether to add `min_price`/`max_price` to `TradingRule`** (shared) or keep bounds connector-local.
