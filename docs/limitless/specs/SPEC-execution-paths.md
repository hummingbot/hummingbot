# Execution Path Taxonomy — BinaryOptionsController

## Incentive Programs (TWO separate reward streams)

### 1. LP Rewards (for RESTING orders)
- Rewards for having limit orders ON the book (don't need to fill)
- Calculated every MINUTE across all markets
- Paid daily at 12:00 UTC in USDC
- Requirements:
  - Order within max spread from midpoint (e.g., 3¢)
  - Order exceeds min shares threshold (per-market, e.g., 100 shares)
  - One-sided OK when odds are between 5%-95%
  - Both sides required outside 5-95% range
- Bonus multiplier: tighter spread = higher reward share
- Per-market daily pool (e.g., $200/day per market)
- dYdX/Polymarket-style design

### 2. Maker Rebates (for FILLED orders)
- Rewards for executed fills where your order was maker liquidity
- 20% of taker fees rebated to makers, distributed pro-rata
- Only eligible markets: Hourly Crypto + 15-minute Crypto
- Paid daily in USDC
- Formula: Your fills' taker fees / Total day's taker fees × Daily rebate pool
- Unfilled orders earn NOTHING here — only execution counts
- More volume filled = larger share of rebate pool

### Combined Incentive
A resting limit order earns LP Rewards every minute just by existing.
When it fills, it ALSO earns Maker Rebates (20% of taker fee).
Double dip = strong incentive to be maker, not taker.

---

## Order Space

### Entry Paths

#### BULLISH (expect underlying above strike at expiry)

| # | Action | Type | Side | LP Rewards | Maker Rebate | Speed | Capital | Notes |
|---|--------|------|------|-----------|-------------|-------|---------|-------|
| 1 | Market BUY YES | Taker | BUY YES book | ❌ | ❌ (you're taker) | Instant | YES price | Worst economics, fastest fill |
| 2 | Limit BUY YES | Maker | BUY YES book | ✅ (while resting) | ✅ (on fill) | Slow/uncertain | YES price | Best economics for bullish entry |
| 3 | MINT + Market SELL NO | Taker | SELL NO book | ❌ | ❌ | Instant | $1 mint - NO proceeds | Net = YES exposure. Costs $1 upfront |
| 4 | MINT + Limit SELL NO | Maker | SELL NO book | ✅ (while resting) | ✅ (on fill) | Slow/uncertain | $1 mint cost | Best maker bullish via mint path |
| 5 | Limit SELL NO (if holding) | Maker | SELL NO book | ✅ | ✅ | Slow | Must own NO tokens | Only if already holding NO from prior mint |

#### BEARISH (expect underlying below strike at expiry)

| # | Action | Type | Side | LP Rewards | Maker Rebate | Speed | Capital | Notes |
|---|--------|------|------|-----------|-------------|-------|---------|-------|
| 6 | Market BUY NO | Taker | BUY NO book | ❌ | ❌ | Instant | NO price | Worst economics |
| 7 | Limit BUY NO | Maker | BUY NO book | ✅ | ✅ | Slow/uncertain | NO price | Best bearish entry |
| 8 | MINT + Market SELL YES | Taker | SELL YES book | ❌ | ❌ | Instant | $1 mint - YES proceeds | Net = NO exposure |
| 9 | MINT + Limit SELL YES | Maker | SELL YES book | ✅ | ✅ | Slow/uncertain | $1 mint cost | Best maker bearish via mint |
| 10 | Limit SELL YES (if holding) | Maker | SELL YES book | ✅ | ✅ | Slow | Must own YES tokens | Only if holding from prior mint |

#### NEUTRAL (pure market making / delta neutral)

| # | Action | Type | Side | LP Rewards | Maker Rebate | Speed | Capital | Notes |
|---|--------|------|------|-----------|-------------|-------|---------|-------|
| 11 | MINT + Limit SELL YES + Limit SELL NO | Maker both | Both books | ✅✅ (double) | ✅ (on fills) | Slow | $1 per pair | Delta neutral. Earn LP on both sides + rebates on fills |
| 12 | Limit BUY YES + Limit BUY NO | Maker both | Both books | ✅✅ | ✅ | Slow | YES + NO price | Only profitable if YES+NO < $1 (rare arb) |

### Exit Paths

| # | Action | Type | LP Rewards | Maker Rebate | Speed | Notes |
|---|--------|------|-----------|-------------|-------|-------|
| E1 | Market SELL YES/NO | Taker | ❌ | ❌ | Instant | Emergency exit, pays spread |
| E2 | Limit SELL YES/NO | Maker | ✅ (while resting) | ✅ (on fill) | Slow/uncertain | Best exit economics |
| E3 | Hold to settlement + redeem | N/A | ❌ | ❌ | At expiry | Winner gets $1, loser gets $0 |
| E4 | Cancel limit order | N/A | Stops LP rewards | N/A | Instant | No cost, stops earning |

---

---

## Implementation Priority

### Phase 1 (Get Trading — Limit-First)
- Path 2: Limit BUY YES (maker entry, bullish) ← DEFAULT
- Path 7: Limit BUY NO (maker entry, bearish) ← DEFAULT
- Path E2: Limit SELL (maker exit) ← DEFAULT
- Path E3: Hold to settlement + redeem
- Fallback ONLY: Market BUY/SELL when <5 min to expiry with strong signal
- From day one: every entry earns LP rewards while resting + maker rebate on fill

### Phase 2 (Mint Paths)
- Paths 3-5, 8-10: MINT + SELL for directional via mint
- Path 11-12: MINT + SELL BOTH for delta neutral income
- Adds: capital-efficient entries, zero-risk arb when spread > $1
- Requires: mint/redeem integration, inventory management, two-sided order tracking

### Phase 3 (Adaptive Execution)
- Dynamic path selection based on orderbook state, time to expiry, signal strength
- Taker fallback for time-critical exits / strong edge near expiry
- Smart order routing: limit vs mint vs market based on cost model
- Linked order management (cancel YES if NO fills, etc.)

### Why Limit-First From Day One
Market orders pay spread and earn zero rewards.
Limit orders save the spread, earn LP rewards while resting, and earn maker rebates on fill.
Taker is a fallback for time-critical situations, not the default.

---

## Connector Requirements Per Phase

### Phase 1 (already built ✅)
- `buy(market_slug, price, size, order_type='GTC', token='YES/NO')`
- `sell(market_slug, price, size, order_type='GTC', token='YES/NO')`
- `cancel(order_id)`
- `get_order_status(order_id, market_slug)`
- `get_active_markets()`
- `get_order_book(market_slug)`
- `redeem_positions(market_slug)`

### Phase 2 (minor additions)
- Limit order monitoring (already have `get_order_status`)
- Fill detection (need WebSocket or polling)
- LP reward tracking (API endpoint TBD)

### Phase 3 (new connector methods)
- `mint_tokens(market_slug, amount)` — calls `splitPosition` on CTF contract
- `get_token_balance(market_slug, token)` — YES/NO token balances
- Inventory tracking across minted pairs
- Two-sided order management (linked YES+NO orders)
