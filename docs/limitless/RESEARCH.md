# Limitless MM — Research & Reference

Single source of truth for everything we learn. Update this as we go.

---

## Platform Basics

- **Exchange:** Limitless (limitless.exchange)
- **Chain:** Base (Coinbase L2)
- **Market type:** Binary prediction markets (YES/NO outcomes)
- **Settlement:** YES + NO = $1. Winner pays $1, loser pays $0.
- **Market durations:** Hourly, 15-minute (crypto markets)
- **Assets:** BTC, ETH, SOL, DOGE, XRP (crypto); also sports, politics, etc.

## Orderbook Structure

- **Single unified orderbook per market** — bids and asks for YES shares
- NO price = 1 - YES price (same book mirrored, not separate)
- Website YES/NO toggle is cosmetic — same book, same prices
- Bid = someone wants to BUY YES shares
- Ask = someone wants to SELL YES shares
- Buying NO = effectively selling YES

## Order API

- **Auth:** `X-API-Key` header (keys start with `lmts_`). Env var: `LIMITLESS_API_KEY`
- **Signing:** EIP-712 for order signing (SDK handles this internally!)
- **Side:** 0 = BUY, 1 = SELL (SDK: `Side.BUY`, `Side.SELL`)
- **Order types:** GTC (limit, rests on book), FOK (fill immediately or reject)
- **Position tokens:** `market.tokens.yes`, `market.tokens.no`
- **Precision:** USDC uses 6 decimals (1 USDC = 1,000,000 units), shares scaled by 1e6
- **Chain:** Base (chainId 8453)
- **EIP-712 domain:** `name="Limitless CTF Exchange"`, `version="1"`, `verifyingContract=venue.exchange`
- **Venue:** Each market has `venue.exchange` (verifying contract) + optional `venue.adapter` (NegRisk)
- **Venue data is STATIC per market** — fetch once and cache

### REST Endpoints
- `POST /orders` — create order
- `DELETE /orders/:id` — cancel single
- `DELETE /orders/cancel-all` — cancel all
- `DELETE /orders/cancel-batch` — cancel batch
- `GET /orders/user/:marketSlug` — get user orders
- `GET /orders/status-batch` — batch order status

### Buy Order (raw)
```
makerAmount = price * num_shares * 1e6   # USDC you pay
takerAmount = num_shares * 1e6           # Shares you receive
side = 0
```

### Sell Order (raw)
```
makerAmount = num_shares * 1e6           # Shares you pay
takerAmount = price * num_shares * 1e6   # USDC you receive
side = 1
```

## MM Reward Program

- **Rebate:** 20% of taker fees rebated to qualifying makers
- **Daily pool:** 100 USDC per market (may vary by market type / coin — UNVERIFIED)
- **Qualifying spread:** ±3¢ max from midpoint (max 6¢ total spread)
- **Minimum size:** 100 contracts per side
- **Rules:** Inside 5¢-95¢ range one side OK, outside need both sides
- **Applies to:** Hourly + 15-min Crypto markets
- **⚠️ WARNING:** Exact reward amounts, qualification rules, and per-market differences NOT fully verified. 15-min markets may have different pool sizes. Per-coin differences possible. Need to check actual reward program details before optimizing for rewards. For now, focus on spread profit — rewards are bonus.

## Volume Observations

- **Dead hours:** Sunday early morning, first 15 min of each hour — near zero volume
- **Volume picks up at :30** into each hour, spikes near expiry
- **Expiry rush:** 15-min BTC went $7.60 → $140 → $480 total. 98% of volume in final 5 minutes
- **Peak hours (weekday):** 20k+ volume observed on hourly markets
- **Typical position sizes:** $1-16 (small retail)
- **Seed liquidity:** Limitless likely seeds markets with initial liquidity (wide spreads)

## Current Spread Observations (Sunday 9am)

- Spreads 20-40 cents on hourly markets
- Some markets: bid $0.25 / ask $0.94 (69 cent spread!)
- Nobody qualifying for MM rewards at these spreads (max 6¢ to qualify)
- Essentially zero competing market makers during off-hours

## Existing Infrastructure (from limitless-recon)

- **WS orderbook streaming:** battle-tested, 3-state cache (FRESH/QUIET/STALE)
- **dr_manhattan library:** Limitless connector skeleton (needs limitless-mm package for auth)
- **limitless_client.py:** REST API wrapper with rate limiting, orderbook fetching
- **Wallet:** exists on Base, needs funding

## Official Python SDK (`limitless-sdk`)

**Install:** `pip install limitless-sdk`
**Source:** `https://github.com/limitless-labs-group/limitless-sdk`
**Python:** 3.9+ required
**Architecture:** Async-first (aiohttp), Pydantic models, auto-reconnect WS

### Components
- `HttpClient` — authenticated HTTP client, loads `LIMITLESS_API_KEY` from env
- `MarketFetcher` — market data + automatic venue caching
- `OrderClient` — order creation, EIP-712 signing, cancel
- `PortfolioFetcher` — positions, PnL, trade history
- WebSocket client with auto-reconnect

### Order Creation (SDK handles signing internally!)
```python
from limitless_sdk.orders import OrderClient
from limitless_sdk.types import Side, OrderType

# GTC (limit order — rests on book)
result = await order_client.create_order(
    token_id=market.tokens.yes,  # or market.tokens.no
    price=0.65,        # price per share in dollars
    size=10.0,         # number of shares
    side=Side.BUY,
    order_type=OrderType.GTC,
    market_slug="btc-above-100k",
)

# FOK (fill or kill — immediate execution or reject)
result = await order_client.create_order(
    token_id=market.tokens.yes,
    maker_amount=10.0,  # BUY: USDC to spend; SELL: shares to sell
    side=Side.BUY,
    order_type=OrderType.FOK,
    market_slug="btc-above-100k",
)
```

### Cancel Orders
```python
await order_client.cancel(order_id="abc123")        # single
await order_client.cancel_all(market_slug="btc-...")  # all on market
```

### Token Approvals (one-time on-chain setup per venue)
- USDC → `venue.exchange` (for BUY orders)
- Conditional Tokens → `venue.exchange` (for SELL orders)
- NegRisk markets: also approve CT → `venue.adapter`
- USDC address on Base: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- CT framework address: `0xC9c98965297Bc527861c898329Ee280632B76e18`

## Dependencies / Libraries

- **limitless-sdk (OFFICIAL):** Async Python SDK. Handles auth, signing, orders, WS. This is what we use.
- **dr_manhattan:** Has Limitless class but auth is broken (depends on dead limitless-mm). NOT needed for MM.
- **Hummingbot:** Open source MM framework, no Limitless connector exists. Has Avellaneda-Stoikov strategy.
- **limitless-mm (mdragan85):** Third-party, Phase 0 only. Dead end.

## Key Risks

1. **Unmatched inventory** — filled on one side only, holding directional bet
2. **Low volume** — quotes sit unfilled during dead hours
3. **Expiry** — positions settle at 0 or 1 if unhedged (mitigated by matched pairs)
4. **Gas/tx latency** — on-chain order management not instant
5. **Capital efficiency** — money locked in positions until settlement

## Architecture Decision

**Phase 1 (now):** Custom `LimitlessConnector` class wrapping `limitless-sdk`.
- Standalone async Python class with Hummingbot-compatible method names
- Methods: `buy()`, `sell()`, `cancel()`, `get_order_book()`, `get_balance()`, etc.
- WS orderbook via SDK's WebSocketClient
- Paper mode for testing without capital
- See: `specs/SPEC-limitless-connector.md`

**Phase 2 (after OS reinstall):** Hummingbot integration.
- `LimitlessConnector` becomes the inner engine
- Thin `ExchangePyBase` subclass wraps it
- Add: AuthBase, OrderBookTrackerDataSource, UserStreamTrackerDataSource
- Add: TradingRule, symbol mapping, InFlightOrder state management
- Docker deployment via hummingbot-api

**Why this order:**
- No Docker needed for Phase 1 (no OS reinstall blocker)
- `limitless-sdk` handles all the hard stuff (auth, signing, WS)
- Same code powers both phases — no throwaway work
- Can test live with tiny amounts before Hummingbot integration

## Docs & Links

- Limitless docs index: `https://docs.limitless.exchange/llms.txt`
- Python quickstart: `https://docs.limitless.exchange/developers/quickstart/python.md`
- WebSocket events: `https://docs.limitless.exchange/developers/websocket-events`
- API reference: `https://docs.limitless.exchange/api-reference/introduction.md`
- Hummingbot connectors: `https://hummingbot.org/connectors/`
- Hummingbot CLOB spot template: `https://hummingbot-foundation.notion.site/Spot-Connector-v2-1-1cc43830938445c9974f43ef861d59f1`
- dr_manhattan source: `/opt/miniconda3/lib/python3.13/site-packages/dr_manhattan/`
- limitless-mm repo: `https://github.com/mdragan85/limitless-mm`

---

## TODO / Questions to Answer

- [x] Read full EIP-712 signing docs — DONE. SDK handles signing internally.
- [x] Understand order lifecycle — DONE. GTC rests on book, FOK immediate. Cancel single/batch/all.
- [x] Check if batch cancel exists — YES. `cancel_all(market_slug)` and batch cancel endpoint.
- [ ] Check if Hummingbot can handle expiring markets or needs custom strategy
- [ ] Check gas costs for order create/cancel on Base (orders are off-chain signed, settlement on-chain?)
- [ ] Fund wallet — how much USDC to start? Need ETH for gas too?
- [ ] Verify: can we cancel unfilled orders for free (no gas)?
- [ ] Understand the reward calculation — how exactly is the 100 USDC/day/market distributed?
- [ ] Token approvals — need to do on-chain approve for USDC and CT before first trade
- [ ] Check if `limitless-sdk` installs on our Python 3.13 (miniconda)
- [ ] Get `ownerId` / profile ID from API
- [ ] Generate API key from Limitless UI
