Jarvis Trading Agent – Mental Model

Overview

Jarvis is a voice/text-driven trading assistant. Users express intents (“buy BTC at 90k”, “alert me if BTC volume spikes”, “run EMA cross buy/sell”), and Jarvis compiles those into safe, auditable jobs executed by a hardened backend built on a minimally modified, event‑driven Hummingbot (v2.10.0 base) and Hyperliquid connectors.

Goals & constraints

- Turn Hummingbot into a **multi-tenant trading engine**:
  - Many concurrent users and strategies per user.
  - Low-latency event-driven execution (no global 1 s tick delay).
  - Single shared market data layer all strategies subscribe to.
- Keep core Hummingbot connectors + StrategyBase APIs intact; add only additive hooks (event-driven base, TradingCore gate).
- Embed Hummingbot into a `UserEngine` wrapper so backend services can spin up per-user runtimes on demand.
- Deliver one reference **event-driven EMA+ATR** strategy for Jarvis; defer the broader library.
- Provide minimal ExecutionService risk checks necessary for production usage; larger risk products are out-of-scope now.
- Jarvis/LLM stack is unchanged in this pass; focus from “strategy spec ready” downward.

Non-goals (this phase)

- No generalized strategy marketplace yet—land the EMA+ATR exemplar first.
- No additional queues/buffers in the hot path; keep MDS → Redis Streams → UserEngines as lean as possible.
- No frontend or LLM UX work besides documenting how they invoke the new runtime.

High-level architecture

- Mobile/Web Frontend (Hyperliquid Builder UI + Privy)
  - Auth: Privy embedded wallet/sign-in.
  - Intent capture: NLU prompt → intent schema (JSON) with strategy type, pair, sizing, risk caps, timing.
  - Session: Privy DID + short‑lived JWT signed client-side. No private key custody in frontend.
  - Transport: HTTPS to Jarvis Orchestrator; realtime status via WebSocket/SSE.
- Wallets and custody
  - User identity via Privy; execution via Hyperliquid Agent Wallet (server-side, per-user or vault).
  - The agent wallet only holds exchange API keys / signing material needed for Hyperliquid; withdrawals require explicit user approval path.
  - Position readback and PnL through Hummingbot connectors.
- Jarvis Orchestrator (stateless API + background workers)
  - Accepts intents, validates, compiles to strategy configs, creates/runs jobs.
  - Exposes CRUD for strategies/executors, event stream for fills, PnL, alerts.
  - Communicates with an Event‑Driven Hummingbot Runtime via in‑process API or RPC.
- Event‑Driven Hummingbot Runtime
  - Strategies extend `EventDrivenStrategyV2Base` (Clock no longer drives them).
  - TradingCore detects `is_event_driven` strategies and calls their `start_event_driven()` entrypoint instead of `Clock.add_iterator`.
  - Uses existing executors and the improved Hyperliquid connector.
  - Publishes fills/balances over the EventBus so orchestrator subscribers stay in sync.
- Market Data Service (MDS)
  - One process per cluster connects once per Hyperliquid symbol/timeframe.
  - Computes EMA/ATR incrementally and publishes to Redis Stream topics `md.<symbol>.<timeframe>`.
  - Maintains per-symbol indicator state entirely in-memory for microsecond-level turnaround.
- Event bus
  - Thin abstraction over Redis Streams with `publish` / async `subscribe`.
  - No additional buffering (no extra queues); MDS hands data straight to Redis, UserEngines consume immediately.
- UserEngine (per user)
  - Embeds TradingCore + connectors + ExecutionService and injects EventBus handles into strategies.
  - Subscribes to shared market data topics; runs multiple strategies per user or scales out with per-user processes.
  - Exposes lifecycle RPC (start/stop strategies) for the orchestrator/StrategyManager.
- Data/Signals
  - Hyperliquid trades/orderbook/candles (with keepalive pings) + derived signals (EMA, volume spikes, breakouts).
  - Scanners run as light jobs and emit triggers that start/stop strategies.

Trust and safety model

- Intent gate: explicit allowlist of symbols, venues, and strategy types.
- Budget caps: per-intent max notional and per-user daily limit; reduce-only where applicable.
- Two‑phase execute for risky intents: “plan → user approval → execute”.
- Backtesting/sandbox: first execution can run in paper mode before going live.
- Audit: every change produces an immutable execution record (intent, compiled config, events, outcome).

Primary user stories

1) “Buy BTC at 90k” → Single order strategy
   - Intent → Limit/IOC config → OrderExecutor with min‑notional and balance refresh protections.
2) “Buy when 9/21 EMA crosses up, sell on cross down” → EMACross strategy
   - Intent → StrategyV2 config with two executors (entry/exit) driven by EMA signals.
3) “Alert me if BTC 1h volume spikes > 2× 30‑day avg before 6pm” → Alert job
   - Scanner emits trigger → push notification; optional “tap to trade” follow‑up intent.
4) “Hedge 20% of my exposure with a short on total market index” → Hedge job
   - Portfolio readback → compute target notional → pick venue/index perp → risk‑capped short executor.

Key integration points

- Privy
  - Frontend SDK for auth + DID.
  - Server verifies Privy JWT → issues short-lived session tied to user id.
- Hyperliquid Agent Wallet
  - Created/linked per user; credentials stored in HSM/secret store.
  - Hummingbot Hyperliquid connectors use those credentials for signing.
- Hummingbot (v2.10.0)
  - Event‑driven strategy base; strategy_v2 executors.
  - Hyperliquid connector improvements already in this repo (WS keepalive, order-state mapping, fee fix, balance refresh after close, notional checks + retry).

Runtime and deployment

- One orchestrator API (FastAPI) + worker (async) per environment.
- Market Data Service + Redis per region; Redis Streams fan out to all UserEngines.
- One or more event-driven Hummingbot processes; scale by user or shard.
- Supervisord/systemd to manage workers; metrics + logs shipped to central observability.

Extensibility

- Strategies are templates: DirectBuy, PriceLimit, EMACross, TWAP, DCA.
- Scanners (volume spike, breakout) are pluggable, emit normalized triggers.
- Risk adapters enforce venue‑specific constraints and per‑user budgets.

Data retention

- Minimal PII (Privy DID) + execution logs + configs.
- No raw private keys in application logs; secrets isolated.
