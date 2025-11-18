Jarvis – Quick Reference

APIs (proposed)

- POST /intents
  - Body: { userId, text?, intent?, params?, riskCaps? }
  - Returns: { intentId, plan, requiresApproval }
- POST /strategies
  - Body: { plan } → returns { strategyId }
- POST /strategies/{id}/start | /stop | /cancel
- GET /strategies/{id}
- GET /events/stream (WebSocket/SSE)
- POST /internal/user-engines/{userId}/strategies/ema-atr (internal hook that maps straight into UserEngine.start_ema_atr_strategy)

Common intents

- DirectBuy: “buy btc at 90000” → limit buy
- EMACross: “buy when 9/21 cross up, sell on cross down”
- VolumeAlert: “alert me if BTC 1h volume > 2x 30d avg before 6pm”
- Hedge: “hedge 20% exposure with short on total market index”

Env vars (examples)

- PRIVY_APP_ID, PRIVY_VERIFIER_PUBLIC_KEY
- HL_AGENT_WALLET_SECRET_REF (e.g., AWS Secrets Manager ARN)
- JARVIS_DB_URL, JARVIS_REDIS_URL
- JARVIS_PAPER_MODE=true|false
- REDIS_URL (EventBus + Market Data Service)
- MDS_SYMBOLS=BTC-PERP,ETH-PERP ; MDS_TIMEFRAMES=1m,5m
- USER_ENGINE_CONNECTOR_CONFIG_PATH=/secrets/connectors/{user_id}.yml

CLI snippets

- Start orchestrator (to be implemented): python -m jarvis.api.server
- Start Market Data Service: python -m services.market_data_service --symbols BTC-PERP,ETH-PERP --timeframes 1m,5m
- Start per-user engine worker: python -m services.user_engine_process --user-id <user>
- Create DirectBuy (cURL): POST /intents { “intent”: “DirectBuy”, “params”: { “symbol”: “BTC-USD”, “price”: “90000”, “sizeQuote”: “100” } }
- Start EMA+ATR (cURL): POST /strategies { "strategy_type": "ema_atr", "params": { ... } }

References

- Hummingbot v2.10.0; StrategyV2 executors; Hyperliquid connector.
- Redis Streams topics `md.<symbol>.<timeframe>` supply shared market data.
- UserEngine registry persists `strategy_id` ↔ runtime mapping in PostgreSQL for restart safety.

Frontend MVP notes

- Repo: `/Users/udaikhattar/jarvis-mvp` (Next.js 15 / Tailwind).
- Env vars: `NEXT_PUBLIC_PRIVY_APP_ID`, `NEXT_PUBLIC_PRIVY_VERIFIER_PUBLIC_KEY`, `OPENAI_API_KEY`, `HL_API_BASE`, `SECRETS_BACKEND`.
- API routes: `/api/agent/intent`, `/api/agent/tools/strategy/start`, `/api/agent/wallet`, `/api/agent/wallet/deposit`.
- LLM stack: OpenAI Agents SDK pinned to `gpt-5.1-med` with compile/portfolio/notification tools.
