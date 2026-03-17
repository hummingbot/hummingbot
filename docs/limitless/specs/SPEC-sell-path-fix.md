# SPEC: Fix SELL Path for Binary Options

## Problem

PositionExecutor cannot SELL YES/NO tokens. When it tries to close a filled position
(via TripleBarrier TP/SL/time_limit), the SELL order path crashes because:

1. `ETHNO-USDC` has no real OrderBook in `order_book_tracker` — only YES pair (`ETH-USDC`) has one
2. When PositionExecutor calls `get_price_by_type(ETHNO-USDC, BestAsk)`, our override flips
   the YES price correctly. But other code paths that access the orderbook directly
   (e.g. `get_order_book()`, VWAP calculations) crash with KeyError or empty data.
3. The connector's `_place_order` / `sell()` path may not handle binary options correctly

## Root Cause

The `get_price_by_type` override in `LimitlessExchange` handles NO pairs by flipping
YES prices. But there are multiple access patterns the framework uses:

- `get_price_by_type()` → our override works ✅
- `get_order_book(trading_pair)` → crashes for NO pairs ❌ (not in tracker)
- `get_vwap_for_volume()` → uses orderbook directly ❌
- `c_get_price()` → calls `get_price()` on connector_base → NOT overridden ❌

## Solution

### 1. Override `get_order_book()` for NO pairs

In `LimitlessExchange`, override `get_order_book()` to return a synthetic OrderBook
for NO pairs by flipping the YES orderbook:

```python
def get_order_book(self, trading_pair: str) -> OrderBook:
    if self._is_no_pair(trading_pair):
        yes_tp = self._yes_pair(trading_pair)
        yes_ob = super().get_order_book(yes_tp)
        # Create synthetic NO orderbook:
        # YES bids become NO asks (flipped: 1 - price)
        # YES asks become NO bids (flipped: 1 - price)
        return self._flip_orderbook(yes_ob)
    return super().get_order_book(trading_pair)
```

### 2. Override `get_price()` for NO pairs

Override `get_price()` (called by `c_get_price()`) to handle NO pairs:

```python
def get_price(self, trading_pair: str, is_buy: bool, amount: Decimal = s_decimal_NaN) -> Decimal:
    if self._is_no_pair(trading_pair):
        yes_tp = self._yes_pair(trading_pair)
        # Flip is_buy: buying NO = selling YES
        yes_price = super().get_price(yes_tp, not is_buy, amount)
        return Decimal("1") - yes_price
    return super().get_price(trading_pair, is_buy, amount)
```

### 3. Fix SELL order routing in `_place_order()`

**Current bug:** `_place_order()` at line 569 hardcodes `self._inner_connector.buy()`
for ALL orders — it ignores the `trade_type` parameter entirely.

Fix: use the `trade_type` parameter to route to buy() or sell():

```python
# In _place_order(), replace the hardcoded buy() call with:
if trade_type == TradeType.SELL:
    result = await self._inner_connector.sell(
        market_slug=slug,
        price=order_price,
        size=float(amount),
        order_type="GTC",
        token=token,
    )
else:
    result = await self._inner_connector.buy(
        market_slug=slug,
        price=order_price,
        size=float(amount),
        order_type="GTC",
        token=token,
    )
```

Token mapping stays the same:
- `ETH-USDC` → token="YES"
- `ETHNO-USDC` → token="NO"

The inner connector's sell() (line 244) handles `Side.SELL` correctly.

**Confirmed:** `self._inner_connector.sell()` exists (connector.py line 244). It calls
`_place_order(side=Side.SELL, token=token)`. So the API supports direct sell.

Mapping:
- SELL YES token → `inner.sell(slug, amount, price, token="YES")`
- SELL NO token → `inner.sell(slug, amount, price, token="NO")`

### 4. Helper: `_flip_orderbook()`

Create a helper that takes a YES OrderBook and returns a flipped NO OrderBook:

```python
def _flip_orderbook(self, yes_ob: OrderBook) -> OrderBook:
    """Create synthetic NO orderbook from YES orderbook.

    YES bids (people buying YES) → NO asks (selling NO = buying YES)
    YES asks (people selling YES) → NO bids (buying NO = selling YES)
    Prices flipped: 1 - yes_price
    """
    # Implementation depends on OrderBook class API
    # May need to create OrderBookMessage entries
    pass
```

### 5. Verify inner connector sell support

Check `/home/tiger/hummingbot/hummingbot/connector/exchange/limitless/connector.py`:
- Does it have a `sell()` method?
- What does the Limitless API support? Buy YES, Buy NO, Sell YES, Sell NO?
- Or only Buy YES and Buy NO (and selling = buying the opposite)?

## Files to Modify

1. `hummingbot/connector/exchange/limitless/limitless_exchange.py`
   - Add `get_order_book()` override
   - Add `get_price()` override
   - Fix `_place_order()` SELL path
   - Add `_flip_orderbook()` helper

2. `hummingbot/connector/exchange/limitless/connector.py`
   - Check/add `sell()` method if needed

## Files NOT to Modify

- `position_executor.py` — framework code, don't touch
- `executor_base.py` — framework code, don't touch
- `exchange_base.pyx` — Cython base, don't touch
- Controller — no changes needed, PositionExecutor handles exits

## Testing

1. Unit test `get_price_by_type` for all PriceType values on NO pairs
2. Unit test `get_order_book` returns flipped book for NO pairs
3. Unit test `get_price(is_buy=True)` and `get_price(is_buy=False)` for NO pairs
4. Unit test SELL order routing in `_place_order`
5. Integration: PositionExecutor with `TradeType.SELL` on `ETHNO-USDC` — should not crash

## Key Invariant

`YES_price + NO_price = 1.00` must hold everywhere:
- `get_price_by_type(ETH-USDC, BestBid) + get_price_by_type(ETHNO-USDC, BestAsk) ≈ 1.0`
- `get_price_by_type(ETH-USDC, BestAsk) + get_price_by_type(ETHNO-USDC, BestBid) ≈ 1.0`

## Context Files

- Inner connector: `hummingbot/connector/exchange/limitless/connector.py`
- Exchange wrapper: `hummingbot/connector/exchange/limitless/limitless_exchange.py`
- Executor base: `hummingbot/strategy_v2/executors/executor_base.py` (line 294: `get_price`)
- Position executor: `hummingbot/strategy_v2/executors/position_executor/position_executor.py`
- Exchange base (Cython): `hummingbot/connector/exchange_base.pyx` (line 338: `get_price_by_type`)
- Connector base (Cython): `hummingbot/connector/connector_base.pyx` (line 415: `c_get_price`)
