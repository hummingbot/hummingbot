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
- Redis Stream backlogs or stalls.
  - Mitigation: per-topic maxlen trim + consumer lag monitoring; alert when lag > 100 ms.
- Market Data Service failover.
  - Mitigation: run hot-standby MDS pointing to same Redis; user engines detect stale timestamps (>2× timeframe) and raise alarms.
- UserEngine restart sequencing.
  - Mitigation: persist `StrategyConfig` so StrategyManager can rehydrate strategies before orchestrator accepts new intents.

Development caveats

- Keep connector changes additive and backward compatible.
- Never block on long loops in strategies (use event-driven pattern).
- Do not persist secrets in logs; scrub configs before storing.
- Paper/live toggles must be explicit in every run config.
- EventBus is Redis Streams only for now—no random asyncio.Queue usage; swapping backend later must preserve `publish/subscribe` semantics.
- Strategies must inject ExecutionService instead of hand-rolling risk logic to keep per-user caps consistent.

Testing notes

- Unit: intent compiler, budget checker, notional sizing, EMA cross signal.
- Integration: strategy lifecycle; fills and position updates end‑to‑end.
- Chaos: WS drop/reconnect, partial fills, rejection bursts, REST fallback.
- Latency: assert WS → Redis → UserEngine path stays <50 ms in lab env; raise alarms if exceeded.

Frontend-specific notes

- Hyperliquid still lacks documented account abstraction for agents. The Next.js MVP keeps the approveAgent + usdSend flow and simply surfaces it in the UI; swap once HL publishes AA docs.
- Secrets backend is stubbed. Before production, wire AWS Secrets Manager (preferred) or Turnkey and ensure no agent keys live in browser storage/logs.
