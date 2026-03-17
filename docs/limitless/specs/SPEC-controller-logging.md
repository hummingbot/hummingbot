# SPEC: Controller Signal/Action Logging

## Goal
Add strategic logging to `controllers/generic/binary_options/controller.py` so we can see what's happening each tick in the Hummingbot log file.

## File to edit
`/home/tiger/hummingbot/controllers/generic/binary_options/controller.py`

## Requirements

### In `update_processed_data()`:

1. After `market_data = await self.market_manager.build_market_data(now_ts)` (line ~113):
   - Log at INFO level: `"tick: %d coins tracked, btc=%.2f"` with len(market_data) and btc_spot
   - For each coin in market_data, log at DEBUG: `"  %s: yes=%.4f bid=%.4f ask=%.4f strike=%.2f"` using the market_data fields

2. After `signals = self.signal_engine.tick(...)` (line ~127):
   - For each coin in signals dict, if signal has a non-zero z_score or any actionable field, log at INFO:
     `"signal[%s]: z=%.3f fair=%.4f edge=%.4f tier=%s"` 
   - Use whatever fields the signal dict actually contains — check signal_engine.py to see what it returns

### In `determine_executor_actions()`:

3. In the MM branch (`_determine_mm_actions`), log at INFO:
   - `"mm_tick: %d coins, actions: %s"` with count and brief summary of what quote_manager produced

4. In the directional branch, after `entry_dicts = self.action_router.route(...)`:
   - If entry_dicts is non-empty, log at INFO: `"action_router: %d entries → %s"` with list of coins
   - If empty but signals exist, log at DEBUG: `"action_router: no entries (signals: %s)"` with signal summary

5. For exit_dicts from exit_monitor:
   - If non-empty, log at INFO: `"exit_monitor: %d exits → %s"` with executor IDs

### Throttling
- The tick runs every ~1 second. The INFO-level logs in update_processed_data (item 1) should be throttled to log at most once every 30 seconds to avoid spam. Use a simple `self._last_log_ts` check.
- Signal and action logs (items 2-5) should always log at INFO when non-trivial (non-zero signals, actual actions).

## Constraints
- Do NOT change any logic — only add logging
- Use the existing `logger = logging.getLogger(__name__)` 
- Keep it clean — no multi-line log spam
- Check signal_engine.py and action_router.py to understand what the dicts actually contain before writing log format strings
