Jarvis – Implementation Details

Scope

This document captures the technical plan to adapt Hummingbot (v2.10.0 base) with Hyperliquid connectors to power the Jarvis trading agent, including APIs, runtime, and concrete code touchpoints.

1) Event-driven Hummingbot runtime

- Strategy base
  - Add `EventDrivenStrategyV2Base` (new file `hummingbot/strategy/event_driven_strategy_v2_base.py`):
    - Inherits from `ScriptStrategyBase` so all existing helpers (`buy`, `sell`, `connectors`, `markets`) stay untouched.
    - Sets `is_event_driven = True`, overrides `on_tick()` to no-op, and exposes async `start_event_driven()` / `stop_event_driven()` entrypoints.
    - Manages its own background tasks via `_spawn_task()` that wraps `safe_ensure_future`, ensuring deterministic cancellation on stop.
    - Subclasses override `_start_loops()` to subscribe to market data or event buses; no shared Clock involvement.
- Trading core gate
  - Update `TradingCore._start_strategy_execution()` so that when `strategy.is_event_driven` is true it skips `Clock.add_iterator` and awaits `strategy.start_event_driven()` instead.
  - Non-event-driven strategies remain untouched and still run through the Clock iterator.
  - `TradingCore.stop_strategy()` now calls `strategy.stop_event_driven()` before discarding event-driven strategies to guarantee cleanup.
- Reference strategy
  - Place `scripts/jarvis/ema_atr_event_driven.py` as the canonical EMA+ATR subclass.
  - Strategy subscribes to `md.<symbol>.<timeframe>` via the injected EventBus client, reacts to EMA 12/26 cross filtered by ATR, and routes orders through inherited helper methods (or injected ExecutionService).

2) Hyperliquid connector improvements (already applied + WS-first positions)

- WebSocket keepalive in API order book data source: send ping at ~80% HEARTBEAT_TIME_INTERVAL.
- Added reduceOnlyRejected order state mapping.
- Fee accounting: buy_percent_fee_deducted_from_returns=False.
- Balance refresh on position CLOSE in ClientOrderTracker.
- Min-notional check and balance/position refresh retry in OrderExecutor.
- WS-first positions
  - Ensure the Hyperliquid perpetual connector parses `assetPositions` (and related) payloads from the user WebSocket stream.
  - Update `self._account_positions` + emit `PositionUpdateEvent` as soon as WS messages arrive; REST polling is relegated to startup/reconciliation.
  - Document drift handling in `gotchas.md`.

3) Multi-tenant platform services (new `services/` package)

- Event bus (`services/event_bus.py`)
  - Thin async interface over Redis Streams: `publish(topic, payload)` and `subscribe(topic)` returning an async iterator.
  - Uses consumer groups for fan-out while avoiding extra queues/buffers; backpressure handled by Redis trimming policies.
  - Backend is swappable (NATS/Kafka later) because callers only know about the abstraction.
- Market Data Service (`services/market_data_service.py`)
  - Connect once per Hyperliquid symbol/timeframe, maintain `IndicatorState` (EMA fast/slow, ATR) entirely in-memory.
  - For each WS candle/trade message: update indicators in O(1), publish payload `{symbol, timeframe, close, ema_fast, ema_slow, atr, timestamp}` to `md.<symbol>.<tf>` immediately.
  - Guarantees low-latency (no sleep loops) by streaming directly from WS → Redis.
- ExecutionService (`services/execution_service.py`)
  - Wraps connector order helpers with minimal risk checks (notional caps, leverage, reduce-only).
  - Strategies submit `OrderIntent` dataclasses; ExecutionService enforces rules then calls `buy`/`sell`.
- UserEngine (`services/user_engine.py`)
  - Embeds TradingCore per user, wiring user-specific connectors + ExecutionService + EventBus handles.
  - Provides `start_ema_atr_strategy`, `stop_strategy`, etc., injecting shared market data bus references into each strategy.
  - Persists strategy instances in-memory and ensures `stop_event_driven()` is called during shutdown.
- UserEngine registry (`services/user_engine_registry.py`)
  - Lazy-start map of `user_id -> UserEngine`, instantiating connectors + TradingCore exactly once per process.
  - Used by StrategyManager to ensure per-user isolation.
- Strategy lifecycle & data models
  - `StrategyJobSpec`, `StrategyConfig`, `OrderIntent` live in `services/models.py`.
  - `services/strategy_manager.py` persists `StrategyConfig`, asks the registry for an engine, and starts/stops strategies based on type (EMA+ATR for now).

4) Jarvis Orchestrator service

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

5) Wallets and identity

- Privy
  - Frontend: embed SDK; collect DID + signature; request session JWT.
  - Backend: verify Privy token; map to internal user id; attach scoped permissions.
- Hyperliquid Agent Wallet
  - Per-user credentials (or vault) stored in secret store (e.g., AWS Secrets Manager).
  - Withdrawal routes require out-of-band approval; trading is scoped by budget caps.
  - Connector uses these credentials for signing with no change to public API.

6) Safety and risk controls

- Hard caps: per-intent and per-day notional limits; per-order min/max.
- Reduce-only where relevant; “close-only” mode toggle.
- Cooldowns after failures; circuit breaker on consecutive rejections.
- Dry run flag and paper connector support for first‑time intents.

7) Runtime and deployment

- Processes
  - Market Data Service (Redis → EventBus) per region.
  - UserEngine processes (per user or per shard) embedding Hummingbot TradingCore.
  - Orchestrator API (stateless) + background workers.
- Infra
  - Supervisord/systemd for long‑running tasks; Prometheus metrics; structured logs.
- Storage
  - PostgreSQL (jobs, runs, audit), Redis Streams (event bus), S3 (artifacts).

8) Minimal code insertion points (when we implement)

- New package: jarvis/
  - api/server.py (FastAPI endpoints)
  - compiler/ (intent → plan → config)
  - runners/ (strategy lifecycle, mapping to StrategyV2)
  - signals/ (volume spike, breakout)
  - risk/ (budget checker, allowlists)
- Hummingbot integration (no breaking changes)
  - Use StrategyV2 + executors; inherit from EventDrivenStrategyV2Base.
  - Interact via in‑process Python calls or lightweight RPC (if separate processes).

9) Observability

- Metrics: order attempts, rejections, fills, balance refreshes, WS reconnects.
- Traces around compile → schedule → run → stop.
- Alerts on circuit breaker trip, WS instability, budget threshold breaches.

Rollout plan

1. Land orchestrator API skeleton + intent schema + "DirectBuy" strategy.
2. Add EMACross template, volume spike scanner, and alert jobs.
3. Add hedge flow (portfolio readback → target notional → short index perp).
4. Harden risk controls and approval flows; add paper/live switches.
5. Expand UI with Privy auth and status stream.

Jarvis frontend MVP (Next.js)

- Location: `/Users/udaikhattar/jarvis-mvp` – Next.js 15, TypeScript, Tailwind, Privy SDK.
- Chat/agent UX hits `/api/agent/intent` which wraps the OpenAI Agents SDK (model `gpt-5.1-med`) plus compile/portfolio/notification tools; confirmations post to `/api/agent/tools/strategy/start`.
- Wallet + funding: `/api/agent/wallet` and `/api/agent/wallet/deposit` mirror Hyperliquid `approveAgent` + `usdSend`. Secrets backend is pluggable with AWS Secrets Manager (preferred) and Turnkey shims.
- Marketing + portfolio pages copy Emre Karatas comps (starfield hero, holdings, asset detail) and are wired to swap mock payloads for orchestrator data once available.
