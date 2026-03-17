# SPEC: Market Selection Improvement

## Context
Market selection picks the closest-to-ATM strike. This works but can select deep OTM markets when no ATM exists. We need better filtering and logging to understand what's being selected and why.

## Changes

### File: `controllers/generic/binary_options/market_manager.py`

#### 1. Add moneyness logging in discover()

After the ATM selection loop (after `if best:` block), add logging that shows:
```
discover: ETH selected strike=$2337.38 spot=$2320.21 moneyness=0.74% slug=dollareth-...
```

Calculate moneyness as `abs(spot - strike) / spot * 100` and log it for each selected market.

#### 2. Add max_moneyness filter

Add a configurable maximum moneyness filter. If the best market's `dist` (which is already `abs(spot - strike) / spot`) exceeds a threshold, skip that coin entirely.

In the ATM selection loop, after finding `best`:
```python
max_moneyness = getattr(self._config, 'max_moneyness', 0.05)  # default 5%
if best_dist > max_moneyness:
    logger.info("discover: %s best strike too far from spot (%.2f%% > %.2f%%), skipping",
                ticker, best_dist * 100, max_moneyness * 100)
    continue
```

#### 3. Log all candidates (debug level)

In the candidates collection loop, after appending to candidates, add debug logging:
```python
logger.debug("discover: candidate %s strike=%.2f dist=%.4f expiry=%s",
             ticker, strike, dist_from_spot, expiry_dt.strftime("%H:%M"))
```

Where `dist_from_spot = abs(spot - strike) / spot if spot else 0`.

But `spot` isn't available yet in the candidates loop. Instead, add this logging in the ATM selection loop where `spot` is available, before the best selection:

```python
for md in mkts:
    if spot and spot > 0:
        dist = abs(spot - md["strike"]) / spot
    else:
        dist = abs(md["yes_price"] - 0.50)
    
    logger.debug("discover: candidate %s strike=%.2f dist=%.4f expiry=%s",
                 ticker, md["strike"], dist, md["expiry"].strftime("%H:%M UTC"))
    # ... rest of selection logic
```

### File: `controllers/generic/binary_options/config.py`

Check if `max_moneyness` field exists in the controller config. If not, add it:
```python
max_moneyness: float = 0.05  # Max distance from ATM as fraction (5% default)
```

Add it to the appropriate config class (likely `BinaryOptionsControllerConfig` or similar).

## Tests

No new test files needed. Just verify the module imports cleanly:
```
/opt/miniconda3/envs/hummingbot/bin/python -c "from controllers.generic.binary_options.market_manager import MarketManager; print('OK')"
```

## DO NOT
- Change any files besides market_manager.py and config.py
- Modify the scoring/evaluate logic
- Change connector code
- Remove existing functionality
