Jarvis – Gotchas and Safeguards

Operational risks

- Stale balances after position close can zero out candidate size.
  - Mitigation: already implemented balance refresh after CLOSE + retry.
- Hyperliquid WS idle disconnects (code 1006).
  - Mitigation: keepalive ping at ~80% heartbeat; monitor reconnect rate.
- Min-notional rejections on very small orders.
  - Mitigation: pre-check min-notional and zero candidate when below; refresh once.
- EMA/candle computations on sparse assets.
  - Mitigation: use HL candle feed heartbeat (v2.10.0) and internal resampling with NaN‑safe ops.
- Over‑permissioned agent wallet.
  - Mitigation: scoped budgets per user + daily caps; withdrawals require separate approval path.
- Intent ambiguity (e.g., “buy soon”, “short index” without symbol).
  - Mitigation: compile to a plan with explicit parameters; request confirmation when missing.
- Strategy proliferation (zombie jobs).
  - Mitigation: TTL and idle shutdown; single‑owner lock per symbol/side unless overridden.

Development caveats

- Keep connector changes additive and backward compatible.
- Never block on long loops in strategies (use event-driven pattern).
- Do not persist secrets in logs; scrub configs before storing.
- Paper/live toggles must be explicit in every run config.

Testing notes

- Unit: intent compiler, budget checker, notional sizing, EMA cross signal.
- Integration: strategy lifecycle; fills and position updates end‑to‑end.
- Chaos: WS drop/reconnect, partial fills, rejection bursts, REST fallback.

# Event-Driven Strategy V2 – Gotchas

- **Clock membership still required**
  - We keep event-driven strategies on the `Clock` so `StrategyBase.c_tick` continues to update timestamps and the order tracker. Removing the iterator breaks order bookkeeping.
- **Background loop interval**
  - `_info_update_loop` and `_action_loop` default to 0.5s. Aggressive reductions can overwhelm executors; tune per strategy if needed.
- **Task lifecycle**
  - Ensure `on_stop()` is awaited; orphaned `_info_update_task`/`_action_loop_task` will otherwise continue running and log `CancelledError` traces.
- **Websocket schema variance**
  - Hyperliquid’s `assetPositions` payload occasionally omits nested dictionaries (e.g., leverage). Parsing uses `Decimal(str(value))`; ensure future schema updates still coerce cleanly.
- **Dependencies for tests**
  - Event-driven tests skip when compiled strategy modules are missing. Hyperliquid websocket tests require `aioresponses`; install or expect skipped runs locally.
- **Position removal**
  - Zero-size websocket updates remove only the side reported. Exchanges that omit the side for closures may require explicit cleanup of both `LONG` and `SHORT` keys.
