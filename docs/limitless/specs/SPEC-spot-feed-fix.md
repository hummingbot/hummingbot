# SPEC: Spot Feed — Always BTC + Binance Primary

## Files to edit
- `controllers/generic/binary_options/spot_feed.py`
- `controllers/generic/binary_options/controller.py`

## Problem
1. BTC is filtered out of market_data (coins: [ETH]) but BTC spot price is needed as signal source
2. Pyth addresses may no longer be available (Limitless moved to Chainlink). Binance should be primary, not fallback.

## Fix 1: spot_feed.py — Binance primary, Pyth fallback
- Flip the priority: try Binance FIRST, then Pyth as fallback (opposite of current)
- Always include "BTC" in the ticker set regardless of what's in pyth_addresses or market data
- Add a `core_tickers` set initialized to `{"BTC"}` in __init__. These are always fetched.
- In `get_prices()`, merge `core_tickers` into `all_tickers` before splitting

## Fix 2: controller.py — Always request BTC
- In `update_processed_data()`, after `spots = self.spot_feed.get_prices(now_ts)`, no change needed IF spot_feed handles it internally (preferred).
- BUT: also add common Binance symbols to spot_feed at init time. In `__init__` of BinaryOptionsController, after creating self.spot_feed, call:
  `self.spot_feed.core_tickers.add("BTC")`
  (This is a safety net — spot_feed should already have it, but explicit is better)

## Constraints
- Keep it minimal — fewest lines changed
- Don't remove Pyth support entirely, just deprioritize it
- Binance ticker format: "BTCUSDT", "ETHUSDT" etc. Make sure the mapping works (internal ticker "BTC" → Binance symbol "BTCUSDT")
