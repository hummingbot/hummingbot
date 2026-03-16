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

## Execution Strategy Selection Logic

### Decision Tree

```
Signal arrives (bullish/bearish + strength)
│
├─ Time to expiry > 30 min? (enough time for limit fills)
│   │
│   ├─ YES: Prefer MAKER entries (Limit BUY or MINT + Limit SELL)
│   │   │
│   │   ├─ Orderbook thin on our side? → MINT + Limit SELL (add liquidity where needed)
│   │   ├─ Good depth exists? → Limit BUY (simpler, no mint cost)
│   │   └─ Both sides thin + signal weak? → MINT + Limit SELL BOTH (neutral MM)
│   │
│   └─ NO: Prefer TAKER entries (speed matters near expiry)
│       │
│       ├─ Signal strong + good price? → Market BUY YES/NO
│       └─ Signal weak near expiry? → SKIP (not enough edge to pay spread)
│
├─ Signal strength?
│   │
│   ├─ STRONG (>0.8): Taker OK — edge covers spread cost
│   ├─ MEDIUM (0.5-0.8): Maker preferred — need rebate to be profitable
│   └─ WEAK (<0.5): Neutral MM only or skip
│
└─ Current position?
    │
    ├─ Already holding YES + signal turns bearish → EXIT (Limit SELL YES or Market SELL)
    ├─ Already holding NO + signal turns bullish → EXIT
    └─ Holding minted pair (YES+NO) → SELL the side signal says, keep the other
```

### Cost Comparison (per $1 notional)

| Path | Entry Cost | Potential Reward | Break-even | MM Income |
|------|-----------|-----------------|------------|-----------|
| Market BUY YES @ $0.50 | $0.50 + spread | $1.00 if wins | Need >50% win rate | None |
| Limit BUY YES @ $0.48 | $0.48 (if fills) | $1.00 if wins | Need >48% win rate | LP rewards + rebate |
| MINT + Limit SELL NO @ $0.52 | $1.00 - $0.52 = $0.48 net | $1.00 if wins (redeem YES) | Need >48% win rate | LP rewards + rebate on NO sale |
| MINT + SELL BOTH @ $0.52/$0.52 | $1.00 - $1.04 = -$0.04 profit | Locked $0.04 regardless | Already profitable if both fill | LP rewards on both + rebates on both |

### Key Insight: MINT + SELL BOTH

If YES + NO sell prices > $1.00 (even by 1¢), minting is **instant risk-free profit** plus you earn LP rewards while orders rest AND maker rebates when they fill. This is the holy grail — no directional risk, pure income.

Even if only one side fills, you're left with a directional position that cost you LESS than buying directly (because you got partial proceeds from the other side).

---

## Capital Efficiency

| Strategy | USDC Locked | Max Loss | Max Gain |
|----------|------------|----------|----------|
| Buy YES @ $0.40 | $0.40 | $0.40 (0%) | $0.60 (150%) |
| Buy NO @ $0.60 | $0.60 | $0.60 (0%) | $0.40 (67%) |
| Mint + Sell NO @ $0.60 | $1.00 upfront, $0.40 net after NO sale | $0.40 | $0.60 + rebate |
| Mint + Sell Both @ $0.52/$0.52 | $1.00 upfront, -$0.04 net after both fill | $0 (if both fill) | $0.04 + LP rewards + rebates |

**Mint path locks more capital upfront ($1 per pair)** but:
- Earns LP rewards while orders rest
- Earns maker rebates when filled
- Can be profitable even without directional edge (if spread > 0)

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
The old bot used market orders. That was leaving money on the table:
- Market BUY YES @ $0.50 = pay spread (say $0.52 actual) + 0 rewards
- Limit BUY YES @ $0.49 = save 3¢ + LP rewards while resting + rebate on fill
- On $1 positions: 3¢ spread + rewards = 6-10% edge improvement
- Worst case (no fill): earned LP rewards, lost nothing
- Only exception: <5 min to expiry with >0.8 signal strength → taker OK

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
