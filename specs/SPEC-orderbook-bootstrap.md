# SPEC: Orderbook Bootstrap After register_market()

## Problem

After making `_initialize_trading_pair_symbol_map()` a no-op (placeholder only), the HB orderbook tracker never gets bootstrapped. The tracker's `listen_for_order_book_snapshots()` tries to fetch a REST snapshot for `ETH-USDC` (the placeholder) which fails with 404. Later, `register_market()` updates `_slug_map` to point at the real slug, but the tracker never retries the snapshot — so it stays uninitialized.

There's also a polling loop in `listen_for_subscriptions()` that polls `inner_connector.cached_orderbooks` every 2s. This *should* work once the slug map is updated and WS data arrives, but the HB tracker apparently needs an initial snapshot to become "ready".

## Current Flow

1. Connector starts → `_initialize_trading_pair_symbol_map()` creates placeholder `ETH-USDC -> ETH-USDC`
2. `listen_for_order_book_snapshots()` runs → tries REST fetch for slug `ETH-USDC` → fails (ValueError guard I added)
3. Controller ticks → `market_manager.evaluate()` discovers real market
4. Controller calls `connector.register_market(slug, "ETH-USDC")` → updates `_slug_map`, subscribes WS, creates trading rules
5. `listen_for_subscriptions()` polls cached orderbooks → should now find data under the real slug
6. BUT: `orderbook_mids` in controller is still empty → `mm_tick` never fires → no orders

## Desired Flow

Same as above, but after step 4, the orderbook tracker should become ready:
- Either trigger a REST snapshot fetch for the real slug after `register_market()` succeeds
- Or ensure `listen_for_subscriptions()` polling properly bootstraps the tracker

## Key Files

- `/home/tiger/hummingbot/hummingbot/connector/exchange/limitless/limitless_exchange.py`
  - `register_market()` at line ~301
  - `_initialize_trading_pair_symbol_map()` at line ~395
  - `status_dict` at line ~120
- `/home/tiger/hummingbot/hummingbot/connector/exchange/limitless/limitless_api_order_book_data_source.py`
  - `_request_order_book_snapshot()` — has guard to skip placeholder slugs
  - `listen_for_subscriptions()` — polls inner connector cached orderbooks
  - `listen_for_order_book_snapshots()` — REST snapshot loop (60s interval)

## Constraints

- Don't revert the deferred/placeholder approach in `_initialize_trading_pair_symbol_map()`
- Don't add new dependencies
- Keep it minimal — ideally just wire the snapshot fetch into `register_market()` or signal the data source to retry
- The `self._order_book_tracker` on the exchange has a `data_source` property that's the `LimitlessAPIOrderBookDataSource` instance

## Testing

After fix: restart hbot, watch logs for:
1. "Registered dynamic market: ETH-USDC -> <slug>"
2. Shortly after: orderbook data appearing (snapshot message)
3. `mm_tick` lines appearing in controller
4. Eventually orders being created
