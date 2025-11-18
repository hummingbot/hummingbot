# Event-Driven Strategy V2 – Implementation Notes

**Status: Implemented (jarvis branch).**

These notes capture the live architecture that enables Hummingbot strategies to operate without the per-second `Clock.tick()` loop. Event-driven strategies spin up their own asyncio tasks, consume shared market data over Redis Streams, and still use every helper provided by `ScriptStrategyBase`.

## Overview

- `EventDrivenStrategyV2Base` extends `ScriptStrategyBase`, sets `is_event_driven = True`, and provides async `start_event_driven()` / `stop_event_driven()` entrypoints plus helpers for spawning and tracking tasks/subscriptions.
- `TradingCore` detects the `is_event_driven` flag: it still boots connectors + clock, but it no longer registers the strategy as a clock iterator—only `start_event_driven()` is awaited. Legacy strategies stay untouched.
- The Hyperliquid connector now treats websocket `assetPositions` messages as the authoritative source for open interest, updating `_perpetual_trading` immediately and emitting `PositionUpdate` events. REST polling remains a reconciliation fallback.

## Key Components

- `hummingbot/strategy/event_driven_strategy_v2_base.py`
  - Inherits from `ScriptStrategyBase`.
  - Manages lifecycle with `_spawn_task()` (wraps `safe_ensure_future`) and `_track_subscription()` so shutdown cancels tasks and closes async iterators deterministically.
  - Overrides `on_tick()` to a no-op; subclasses implement `_start_loops()` to launch their event-driven logic.

- `hummingbot/core/trading_core.py`
  - `_start_strategy_execution()` waits on `start_event_driven()` when `is_event_driven` is present, skipping `clock.add_iterator`.
  - `stop_strategy()` invokes `stop_event_driven()` before clearing the strategy reference.
  - Connectors, KillSwitch, metrics collectors, and markets recorder behave exactly as before.

- Hyperliquid websocket positions
  - `hummingbot/connector/derivative/hyperliquid_perpetual/hyperliquid_perpetual_derivative.py` parses `"assetPositions"` payloads in the `"user"` channel, updates `_perpetual_trading`, and emits `AccountEvent.PositionUpdate`.
  - Zero-size payloads clear the stored position immediately; REST `_update_positions()` only runs on startup/reconnect or as periodic reconciliation.

## Quick Reference

### Opt-in from a strategy

```python
from hummingbot.strategy.event_driven_strategy_v2_base import EventDrivenStrategyV2Base


class MyEventDrivenStrategy(EventDrivenStrategyV2Base):
    markets = {"hyperliquid_perpetual": {"BTC-PERP"}}

    async def _start_loops(self):
        self._spawn_task(self._signal_loop())

    async def _signal_loop(self):
        while not self._stopping:
            # ingest market data, place orders, etc.
            ...
```

### TradingCore behaviour

- Event-driven strategies:
  1. Connectors + clock start as usual.
  2. `TradingCore` awaits `strategy.start_event_driven()` instead of registering the strategy on the clock.
  3. Shutdown awaits `strategy.stop_event_driven()` and then proceeds with existing teardown logic.
- Non event-driven strategies continue to run via the existing `Clock` iterator.

### Hyperliquid WS positions (example)

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

- Emits `AccountEvent.PositionUpdate` immediately; no polling delay.
- REST `_update_positions()` doubles as reconciliation on reconnects.

## Gotchas

- **Clock vs strategy**
  - Connectors stay on the `Clock` to keep order books, trades, and status polling fresh. Strategies must not rely on being iterators.
- **Task lifecycle**
  - Always use `_spawn_task()`/`_track_subscription()` so `stop_event_driven()` can cancel tasks and close streams cleanly.
- **Redis lag**
  - Redis Streams are the single fan-out path for shared market data; configure `maxlen` trimming and monitor consumer lag to keep latency under 50 ms.
- **Websocket schema variance**
  - Hyperliquid occasionally omits nested values (e.g., leverage dict). Parsing must tolerate missing keys and default sensibly.
- **Position removal**
  - Zero-size websocket updates imply the position is closed; remove it immediately or stale leverage data will leak into strategies.

## Testing Plan

- Unit tests
  - `test/hummingbot/strategy/test_event_driven_strategy_v2_base.py`: task management, idempotent start/stop, subscription cleanup.
  - `test/hummingbot/core/test_trading_core_event_driven.py`: verifies the `start_event_driven()`/`stop_event_driven()` gating logic.
  - `test/hummingbot/connector/derivative/hyperliquid_perpetual/test_positions_ws.py`: websocket payload parsing + `PositionUpdate` emission.
- Integration
  - Multi-module test runs a fake Hyperliquid client, Redis-backed EventBus, Market Data Service, and the EMA+ATR strategy to ensure EMA crosses trigger orders with sub-50 ms latency.

## Operational Guidance

- Event-driven strategies **must** inherit from `EventDrivenStrategyV2Base`.
- Market Data Service publishes to Redis Streams (`md.<symbol>.<timeframe>`); UserEngines consume via consumer groups for shared market data without duplicate subscriptions.
- Supervisord/systemd should monitor Market Data Service and UserEngine processes; restart them if no messages are published/consumed for >2× timeframe.
- When onboarding new connectors, follow the Hyperliquid WS-first approach: trust websocket payloads for positions/fills, and relegate REST to reconciliation only.
