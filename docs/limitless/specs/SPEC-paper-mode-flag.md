# SPEC: Paper Mode Flag

## Goal
Wire `paper_mode` from controller YAML → inner connector so we can test the full pipeline without placing real orders.

## Current State
- Inner `LimitlessConnector` (connector.py) already supports `paper_mode: bool` param
- In paper mode it logs orders instead of submitting, returns synthetic results
- `LimitlessExchange` (limitless_exchange.py) creates the inner connector but never passes `paper_mode`
- No YAML config for it

## Changes Required

### 1. Controller YAML (`conf/controllers/binary_options.yml`)
Add under connection section:
```yaml
paper_mode: true   # true = log orders only, false = real trading
```

### 2. Controller config (`controllers/generic/binary_options/config.py`)
Add `paper_mode: bool = False` field to `BinaryOptionsControllerConfig`.

### 3. LimitlessExchange (`hummingbot/connector/exchange/limitless/limitless_exchange.py`)
- Accept `paper_mode` parameter (check if it's available from trading pair config or pass via kwargs)
- Pass it through to inner connector: `LimitlessConnector(..., paper_mode=paper_mode)`

### 4. Strategy script (`scripts/binary_options_strategy.py`)
- Read `paper_mode` from controller config
- Pass to connector initialization if possible

## Key Constraint
The connector is initialized by Hummingbot framework via `connect_markets()` config, NOT by our controller directly. So the cleanest path is:

### Preferred approach
In `LimitlessExchange.__init__()` or `_ensure_inner_connector()`, check for a config flag. Options:
1. **Environment variable**: `LIMITLESS_PAPER_MODE=1` — simplest, no framework changes
2. **Exchange config**: If `limitless` connector config supports extra params
3. **Class attribute**: Controller sets `exchange.paper_mode = True` before first tick

Option 3 is cleanest — controller has access to the exchange instance and can set it before trading starts.

### Implementation (Option 3)
1. Add `paper_mode: bool = False` attribute to `LimitlessExchange`
2. In `_ensure_inner_connector()`, pass `self.paper_mode` to `LimitlessConnector()`
3. In controller's `on_start()` or first tick, set `self.connector.paper_mode = config.paper_mode`
4. Add `paper_mode: bool = False` to `BinaryOptionsControllerConfig`
5. Add `paper_mode: true` to YAML

## Testing
- Start with `paper_mode: true` in YAML
- Verify logs show `[PAPER]` prefix on order attempts
- Verify NO real orders hit Limitless API
- Verify full pipeline still runs: signals, quote_manager, repricing, position tracking

## Files to modify
1. `conf/controllers/binary_options.yml` — add `paper_mode: true`
2. `controllers/generic/binary_options/config.py` — add field
3. `hummingbot/connector/exchange/limitless/limitless_exchange.py` — add attribute, pass to inner
4. `controllers/generic/binary_options/controller.py` — set connector.paper_mode from config on start
