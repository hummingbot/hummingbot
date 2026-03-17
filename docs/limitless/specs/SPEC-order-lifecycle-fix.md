# SPEC: Order Lifecycle Fix

## Context
The binary options MM controller has two critical bugs causing it to spam orders and trade one-sided.

## Bug 1: Hardcoded TradeType.BUY
**File:** `controllers/generic/binary_options/controller.py`
**Method:** `_make_mm_executor_config` (line ~457)

Currently: `side=TradeType.BUY` is hardcoded for ALL quotes.
Fix: Pass `qa.side` through and map it:
- `qa.side == "YES"` → `TradeType.BUY` (buying YES token)
- `qa.side == "NO"` → `TradeType.SELL` (Hummingbot SELL maps to buying NO token at connector level)

Change `_make_mm_executor_config` signature to accept a `side: str` parameter (the YES/NO string from QuoteAction).
Map inside the method:
```python
trade_side = TradeType.BUY if side == "YES" else TradeType.SELL
```
Update all 3 call sites (place, update) to pass `qa.side`.

### IMPORTANT: Connector-level token routing (Bug 1b)
**File:** `hummingbot/connector/exchange/limitless/limitless_exchange.py`
**Method:** `_place_order` (the one calling `self._inner_connector.buy/sell`)

Currently both BUY and SELL call with `token="YES"`. But SELL YES requires holding YES tokens (we don't have any).

Fix the SELL path to BUY NO instead:
```python
if trade_type is TradeType.BUY:
    result = await self._inner_connector.buy(
        market_slug=slug, price=float(price), size=float(amount),
        order_type="GTC", token="YES",
    )
else:
    # "SELL" in Hummingbot = buy the NO token on Limitless
    # NO price = 1 - YES price
    no_price = 1.0 - float(price)
    result = await self._inner_connector.buy(
        market_slug=slug, price=no_price, size=float(amount),
        order_type="GTC", token="NO",
    )
```
This means both sides are limit buy orders waiting to fill — no inventory needed.

## Bug 2: No Order Feedback to QuoteManager
**File:** `controllers/generic/binary_options/controller.py`
**Method:** `_mm_tick` (the `for qa in quote_actions.actions:` loop)

After creating a PositionExecutor for a "place" action, the controller stores the executor_id in `_mm_executor_map` but NEVER feeds it back to `quote_manager._current_orders`. 

Result: `_sync_side()` always sees `order_id=None` → always emits "place" → order spam every tick.

Fix: After creating the executor config for "place", call:
```python
self.quote_manager.set_order_id(qa.coin, qa.side, executor_config.id)
```

Add this method to QuoteManager:
```python
def set_order_id(self, coin: str, side: str, order_id: str) -> None:
    """Feed back executor id so _sync_side knows an order exists."""
    orders = self._current_orders.setdefault(coin, {})
    if side in orders:
        orders[side]["order_id"] = order_id
```

Similarly, after a "cancel" action removes the executor, clear the order tracking:
```python
self.quote_manager.clear_order(qa.coin, qa.side)
```

Add:
```python
def clear_order(self, coin: str, side: str) -> None:
    """Remove tracked order for a side."""
    orders = self._current_orders.get(coin, {})
    orders.pop(side, None)
```

For "update" actions: stop old executor, create new one, feed back new id:
```python
self.quote_manager.set_order_id(qa.coin, qa.side, new_executor_config.id)
```

## Files to change
1. `controllers/generic/binary_options/controller.py` — fix side mapping + order feedback
2. `controllers/generic/binary_options/quote_manager.py` — add `set_order_id()` and `clear_order()` methods
3. `hummingbot/connector/exchange/limitless/limitless_exchange.py` — fix SELL to BUY NO token

## Tests
Update existing tests in `controllers/generic/binary_options/tests/test_quote_manager.py`:
- Add test that `set_order_id` prevents duplicate place actions
- Add test that `clear_order` allows fresh place
- Verify existing tests still pass

Update/add tests in `controllers/generic/binary_options/tests/test_controller.py` (if exists):
- Verify YES side gets TradeType.BUY
- Verify NO side gets TradeType.SELL

Run: `/opt/miniconda3/envs/hummingbot/bin/python -m pytest controllers/generic/binary_options/tests/ -v`
ALL tests must pass.

## DO NOT
- Change any other files
- Modify trading logic, signal engine, or quote computation
- Change any config values
- Add new dependencies
