# SPEC: Z-Score Threshold Fix

## Context
Quote manager uses a single `edge_z_threshold` for both spot_z and btc_z. But runtime.json has separate per-coin thresholds that Optuna tuned independently. We need to normalize each z against its own threshold.

## Changes

### File: `controllers/generic/binary_options/quote_manager.py`

#### In `_tick_coin()`, replace the z-ratio computation block:

**Current code (around line 125-130):**
```python
spot_z = abs(sig.get("z_score", 0.0))
btc_z = abs(sig.get("btc_z_score", 0.0))
threshold = self._rb.get_coin_param(coin, "edge_z_threshold", 1.5)
z_ratio = max(spot_z, btc_z) / threshold if threshold > 0 else 0.0
z_ratio = max(0.0, min(1.0, z_ratio))
```

**New code:**
```python
spot_z = abs(sig.get("z_score", 0.0))
btc_z = abs(sig.get("btc_z_score", 0.0))
combined_z = sig.get("combined_z", 0.0)  # signed, used for direction

# Normalize each z against its own Optuna-tuned threshold
spot_thresh = self._rb.get_coin_param(coin, "edge_z_threshold", 1.5)
btc_thresh = self._rb.get_coin_param(coin, "btc_z_threshold", 0.5)
combo_thresh = self._rb.get_coin_param(coin, "combined_z_threshold", 0.7)

spot_ratio = spot_z / spot_thresh if spot_thresh > 0 else 0.0
btc_ratio = btc_z / btc_thresh if btc_thresh > 0 else 0.0
combo_ratio = abs(combined_z) / combo_thresh if combo_thresh > 0 else 0.0

z_ratio = max(spot_ratio, btc_ratio, combo_ratio)
z_ratio = max(0.0, min(1.0, z_ratio))
```

#### In the state transition and ONE_SIDED direction block, replace `model_disagree` direction with `combined_z` direction:

**Current code (around line 145-150):**
```python
if z_ratio >= 1.0:
    new_state = QuoteState.ONE_SIDED
elif z_ratio > 0.5:
    new_state = QuoteState.SKEWED
else:
    new_state = QuoteState.SYMMETRIC
```

Keep this the same — state transitions use z_ratio which now incorporates all 3 signals.

**Current ONE_SIDED block (around line 164-172):**
```python
if new_state == QuoteState.ONE_SIDED:
    favored = "YES" if model_disagree > 0 else "NO"
```

**Change to:**
```python
if new_state == QuoteState.ONE_SIDED:
    favored = "YES" if combined_z > 0 else "NO"
```

Use combined_z sign for direction (Optuna's blended view of which way price is moving). Positive combined_z = price going up = YES is favored = pull NO side.

#### For the SKEW computation, also use combined_z for direction:

**Current (around line 136):**
```python
model_disagree = model_prob - yes_price
```
and
```python
skew = model_disagree * cfg.skew_sensitivity
```

**Change to:**
```python
# Direction from combined_z (Optuna-blended), normalized for skew scaling
combo_direction = combined_z / combo_thresh if combo_thresh > 0 else 0.0
combo_direction = max(-1.0, min(1.0, combo_direction))  # clamp to [-1, 1]
```
and
```python
skew = combo_direction * cfg.skew_sensitivity * reward_spread
```

Note: `reward_spread` is already passed to `_tick_coin`. The skew is now a fraction of reward_spread scaled by the normalized combined_z direction. Remove the old `model_disagree` and `model_prob`/`yes_price` lines if they're no longer used elsewhere in this method.

### File: `controllers/generic/binary_options/signal_engine.py`

Check if `combined_z` is already in the signal dict returned by `compute()` or `tick()`. If not, add it.

Search for where signal dicts are built and ensure `combined_z` is included. It should be the weighted combination of spot_z and btc_z that the original limitless-recon system computes. If not present, compute it as:
```python
combined_z = spot_z * spot_weight + btc_z * btc_weight
```
where weights come from the signal config or runtime.

### File: `controllers/generic/binary_options/controller.py`

Make sure `combined_z` is passed through in the signal dict from signal_engine to quote_manager. Check the signal pipeline:
1. `signal_engine.compute()` or `signal_engine.tick()` returns signal dict
2. Signal dict gets stored in `self.processed_data["coins"]`
3. Quote manager receives it via `signals.get(coin, {})`

If `combined_z` isn't in that dict, add it.

## Tests

Update `controllers/generic/binary_options/tests/test_quote_manager.py`:
- Update existing z-score tests to use the new 3-threshold logic
- Add test: spot_z over its threshold → z_ratio >= 1.0 even if btc_z is 0
- Add test: btc_z over its threshold → z_ratio >= 1.0 even if spot_z is 0
- Add test: combined_z sign determines favored side in ONE_SIDED
- Add test: skew direction follows combined_z sign

Run: `/opt/miniconda3/envs/hummingbot/bin/python -m pytest controllers/generic/binary_options/tests/test_quote_manager.py -v`
ALL tests must pass.

## DO NOT
- Change any other files beyond the 3 listed
- Modify connector, market_manager, or fair_value code
- Change config values or YAML files
- Add new dependencies
- Remove any existing functionality
