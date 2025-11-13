Jarvis – Implementation Details

Scope

This document captures the technical plan to adapt Hummingbot (v2.10.0 base) with Hyperliquid connectors to power the Jarvis trading agent, including APIs, runtime, and concrete code touchpoints.

1) Event-driven Hummingbot runtime

- Strategy base
  - Add EventDrivenStrategyV2Base that marks strategies as event-driven and runs two lightweight loops:
    - _info_update_loop(): fold connector/executor/book updates into strategy state.
    - _action_loop(): compute actions on a short cadence (e.g., 200–500 ms).
- Trading core gate
  - In TradingCore._start_strategy_execution(), if strategy.is_event_driven: call start_event_driven(); else fall back to Clock iterator.

2) Hyperliquid connector improvements (already applied)

- WebSocket keepalive in API order book data source: send ping at ~80% HEARTBEAT_TIME_INTERVAL.
- Added reduceOnlyRejected order state mapping.
- Fee accounting: buy_percent_fee_deducted_from_returns=False.
- Balance refresh on position CLOSE in ClientOrderTracker.
- Min-notional check and balance/position refresh retry in OrderExecutor.

3) Jarvis Orchestrator service

- API surface (FastAPI recommended)
  - POST /intents: Submit an intent (NL or structured). Returns compiled plan.
  - POST /strategies: Create a strategy from a plan; returns id.
  - POST /strategies/{id}/start | /stop | /cancel
  - GET /strategies/{id}: State (active, PnL, fills, budget).
  - GET /events/stream: WebSocket/SSE for realtime updates.
- Compile pipeline
  - Intent → parse (LLM+schema or deterministic grammar) → validate (allowlist, budgets) → compile (StrategyConfig + Executors) → schedule (create or reuse a runtime) → run.
- Strategy templates
  - DirectBuy: single order (limit/market/IOC).
  - PriceLimit: “buy at x/sell at y” with GTC + cancel conditions.
  - EMACross: entry/exit on cross, optional ATR filters.
  - TWAP/DCA: time-slicing with min-notional protections.
- Data/scanners
  - Volume spike scanner: N-minute rolling sum vs baseline; emit trigger.
  - Breakout scanner: price crossing rolling high/low bands.
  - Alert jobs: only notify; strategies optional.

4) Wallets and identity

- Privy
  - Frontend: embed SDK; collect DID + signature; request session JWT.
  - Backend: verify Privy token; map to internal user id; attach scoped permissions.
- Hyperliquid Agent Wallet
  - Per-user credentials (or vault) stored in secret store (e.g., AWS Secrets Manager).
  - Withdrawal routes require out-of-band approval; trading is scoped by budget caps.
  - Connector uses these credentials for signing with no change to public API.

5) Safety and risk controls

- Hard caps: per-intent and per-day notional limits; per-order min/max.
- Reduce-only where relevant; “close-only” mode toggle.
- Cooldowns after failures; circuit breaker on consecutive rejections.
- Dry run flag and paper connector support for first‑time intents.

6) Runtime and deployment

- Processes
  - Orchestrator API (stateless) + background workers.
  - One Hummingbot process can host many strategies; shard by user count.
- Infra
  - Supervisord/systemd for long‑running tasks; Prometheus metrics; structured logs.
- Storage
  - PostgreSQL (jobs, runs, audit), Redis (queues, pub/sub), S3 (artifacts).

7) Minimal code insertion points (when we implement)

- New package: jarvis/
  - api/server.py (FastAPI endpoints)
  - compiler/ (intent → plan → config)
  - runners/ (strategy lifecycle, mapping to StrategyV2)
  - signals/ (volume spike, breakout)
  - risk/ (budget checker, allowlists)
- Hummingbot integration (no breaking changes)
  - Use StrategyV2 + executors; inherit from EventDrivenStrategyV2Base.
  - Interact via in‑process Python calls or lightweight RPC (if separate processes).

8) Observability

- Metrics: order attempts, rejections, fills, balance refreshes, WS reconnects.
- Traces around compile → schedule → run → stop.
- Alerts on circuit breaker trip, WS instability, budget threshold breaches.

Rollout plan

1. Land orchestrator API skeleton + intent schema + “DirectBuy” strategy.
2. Add EMACross template, volume spike scanner, and alert jobs.
3. Add hedge flow (portfolio readback → target notional → short index perp).
4. Harden risk controls and approval flows; add paper/live switches.
5. Expand UI with Privy auth and status stream.

# Event-Driven Strategy V2 – Implementation Notes

## Overview

This refactor introduces the `EventDrivenStrategyV2Base` helper and wires Hummingbot to run Strategy V2 scripts without relying on the per-second `on_tick()` loop. Event-driven strategies still sit on the central clock for lifecycle bookkeeping (order tracker, timestamps), but the heavy logic now lives in lightweight asyncio tasks that react to events.

## Key Components

- `hummingbot/strategy_v2/event_driven_strategy_v2_base.py`
  - Subclass of `StrategyV2Base` with `is_event_driven = True`.
  - Spawns two background loops:
    - `_info_update_loop()` → periodically syncs executor/controller state.
    - `_action_loop()` → pulls `determine_executor_actions()` and executes decisions.
  - Overrides `on_tick()` to a no-op while leaving `TimeIterator` ticking for order tracker upkeep.
  - Ensures tasks are cancelled in `on_stop()`.

- `hummingbot/core/trading_core.py`
  - When a strategy exposes `is_event_driven`, we call `start_event_driven()` before adding it to the clock. This primes the new asyncio loops while retaining the existing iterator behaviour for order trackers and lifecycle hooks.

- Hyperliquid websocket positions
  - `hummingbot/connector/derivative/hyperliquid_perpetual/hyperliquid_perpetual_derivative.py` listens for `assetPositions` payloads on the user stream, updates `_perpetual_trading`, and emits `AccountEvent.PositionUpdate`. REST `_update_positions()` remains the reconciliation fallback.
  - Position payloads normalised to `Position` instances with sign-aware side detection; zero-size payloads clear state.

## Testing

- New unit tests under `test/hummingbot/strategy_v2/test_event_driven_strategy_v2_base.py` cover task creation, idempotency, loop execution, and task cancellation. Tests skip automatically if Strategy V2 compiled dependencies are unavailable.
- Hyperliquid websocket processing tests live in `test/hummingbot/connector/derivative/hyperliquid_perpetual/test_hyperliquid_perpetual_derivative.py`. These run when `aioresponses` is installed; otherwise they skip at collection time.

## Operational Guidance

- Event-driven strategies should inherit from `EventDrivenStrategyV2Base` (or a project-specific subclass) to opt-in.
- Supervisord/systemd can run one process per user; setting `is_event_driven` removes the expensive per-second logic while keeping connectors on the clock.
- When adding new connectors that emit position events, follow the Hyperliquid pattern: normalise amounts, map to HB trading pairs, update `PerpetualTrading`, emit `PositionUpdateEvent`.
