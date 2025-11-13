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

CLI snippets

- Start orchestrator (to be implemented): python -m jarvis.api.server
- Create DirectBuy (cURL): POST /intents { “intent”: “DirectBuy”, “params”: { “symbol”: “BTC-USD”, “price”: “90000”, “sizeQuote”: “100” } }

References

- Hummingbot v2.10.0; StrategyV2 executors; Hyperliquid connector.

# Event-Driven Strategy V2 – Quick Reference

## Opt-in from a strategy

```python
from hummingbot.strategy_v2.event_driven_strategy_v2_base import EventDrivenStrategyV2Base


class MyEventDrivenStrategy(EventDrivenStrategyV2Base):
    markets = {"exchange": {"HBOT-USDT"}}

    def create_actions_proposal(self):
        # Return a list of CreateExecutorAction
        return []

    def stop_actions_proposal(self):
        return []

    def store_actions_proposal(self):
        return []
```

## TradingCore behaviour

- Strategies with `is_event_driven = True`:
  1. `TradingCore` calls `strategy.start_event_driven()` before registering as a clock iterator.
  2. The clock still manages lifecycle callbacks (`c_start`, `c_tick`, `c_stop`).

## Background task tuning

- Override `info_update_interval` / `action_loop_interval` on subclasses for slower/faster cadences.
- Call `self.trigger_event(...)` inside `_action_loop` derivations if custom notifications required.

## Hyperliquid WS positions

```python
positions_payload = {
    "assetPositions": [{
        "position": {
            "coin": "BTC",
            "szi": "0.8",
            "entryPx": "29000",
            "unrealizedPnl": "15.2",
            "leverage": {"value": 5}
        }
    }]
}

await connector._process_positions_ws(positions_payload["assetPositions"])
```

- Emits `AccountEvent.PositionUpdate` with normalised `PositionUpdateEvent` payload.
- REST `_update_positions()` remains the reconciliation path on reconnects/fills.
