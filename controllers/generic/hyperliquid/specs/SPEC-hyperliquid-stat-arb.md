# SPEC: Hyperliquid Directional Stat-Arb — Phase 1

**Date:** 2026-03-19
**Status:** Approved — build now
**Goal:** Directional trading on Hyperliquid perps using BTC divergence signals

---

## Strategy

When an alt diverges from its BTC-implied price (z-score spike), go long or short
the alt perp to capture mean reversion. Single leg, no hedge. BTC reversal as exit signal.

---

## Files to Create

```
controllers/generic/hyperliquid/
├── __init__.py               # Exports HyperliquidController + Config
├── controller.py             # ~80 lines, extends DirectionalTradingControllerBase
├── signal_engine.py          # COPY from binary_options/signal_engine.py
├── fair_value.py             # COPY from binary_options/fair_value.py
└── specs/                    # This spec (already exists)

scripts/
└── hyperliquid_strategy.py   # COPY from binary_options_strategy.py, rename classes

conf/
├── scripts/hyperliquid_strategy.yml
└── controllers/hyperliquid.yml
```

**NO new modules for:** pair scanner, position manager, market manager, quote manager, exit monitor, action router, order types, spot feed. None of that. Keep it minimal.

---

## 1. signal_engine.py — COPY

**Source:** `controllers/generic/binary_options/signal_engine.py` (820 lines)

Copy as-is. It imports only from `.config` and `.fair_value` (sibling imports) plus stdlib.

The only change needed: the `from .config import RuntimeBridge` import. Since we're NOT copying config.py's RuntimeBridge (too complex for Phase 1), we have two options:
- **Option A (preferred):** Copy RuntimeBridge class into our config.py (it's ~60 lines, standalone, reads a JSON file)
- **Option B:** Stub it out — hardcode params in config, no hot-reload

Go with Option A. RuntimeBridge is valuable and standalone.

## 2. fair_value.py — COPY

**Source:** `controllers/generic/binary_options/fair_value.py` (505 lines)

Copy as-is. Contains:
- `MispricingProfile` — spot mispricing tracking (NEEDED)
- `BtcImpliedProfile` — BTC-implied divergence (NEEDED — this IS our signal)
- `compute_model_prob()` — Black-Scholes (NOT needed but harmless, leave it)
- `compute_edge()` — model vs market (NOT needed but harmless, leave it)
- `halflife_to_alpha()` — EMA smoothing (NEEDED)
- `compute_hourly_volatility()` — vol estimation (NEEDED)

Zero hbot imports. Pure math. Just copy it.

## 3. config.py — NEW (~100 lines)

```python
"""Configuration for Hyperliquid directional controller."""
import json
import logging
import os
import time

from decimal import Decimal
from typing import Optional
from pydantic import Field

from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop

logger = logging.getLogger(__name__)


class HyperliquidControllerConfig(DirectionalTradingControllerConfigBase):
    """Config for Hyperliquid directional stat-arb."""
    controller_type: str = "directional_trading"
    controller_name: str = "hyperliquid"

    # Connector — defaults to hyperliquid_perpetual
    connector_name: str = "hyperliquid_perpetual"
    trading_pair: str = "SOL-USD"

    # Signal thresholds
    edge_z_threshold: float = Field(default=1.5, description="Z-score threshold to enter")
    btc_z_threshold: float = Field(default=1.75, description="BTC z-score threshold")

    # BTC reference pair (for correlation signal)
    btc_connector_name: str = "hyperliquid_perpetual"
    btc_trading_pair: str = "BTC-USD"

    # Signal engine params
    baseline_halflife_secs: float = 35.0
    current_halflife_secs: float = 12.0
    mispricing_halflife_secs: float = 23.0

    # Runtime bridge (optional hot-reload)
    runtime_json_path: str = ""

    # Override defaults from DirectionalTradingControllerConfigBase
    leverage: int = 1
    total_amount_quote: Decimal = Decimal("10")
    max_executors_per_side: int = 1
    cooldown_time: int = 60
    stop_loss: Optional[Decimal] = Decimal("0.01")
    take_profit: Optional[Decimal] = Decimal("0.02")
    trailing_stop: Optional[TrailingStop] = None
    time_limit: Optional[int] = 3600  # 1 hour max

    def update_markets(self, markets: dict) -> dict:
        """Register both the trading pair AND BTC pair for price data."""
        markets = super().update_markets(markets)
        if self.btc_connector_name not in markets:
            markets[self.btc_connector_name] = set()
        markets[self.btc_connector_name].add(self.btc_trading_pair)
        return markets


# --- RuntimeBridge (copied from binary_options/config.py) ---

class RuntimeBridge:
    """Hot-reload trading params from a JSON file."""

    def __init__(self, path: str, poll_interval: float = 5.0):
        self._path = path
        self._poll = poll_interval
        self._last_check = 0.0
        self._last_mtime = 0.0
        self._data: dict = {}
        if path and os.path.isfile(path):
            self._load()

    def check(self):
        now = time.time()
        if now - self._last_check < self._poll:
            return
        self._last_check = now
        if not self._path or not os.path.isfile(self._path):
            return
        mtime = os.path.getmtime(self._path)
        if mtime != self._last_mtime:
            self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                self._data = json.load(f)
            self._last_mtime = os.path.getmtime(self._path)
            logger.info(f"RuntimeBridge: reloaded {self._path}")
        except Exception as e:
            logger.warning(f"RuntimeBridge: failed to load {self._path}: {e}")

    def get(self, coin: str, key: str, default=None):
        coins = self._data.get("coins", {})
        coin_data = coins.get(coin, {})
        return coin_data.get(key, default)

    @property
    def data(self) -> dict:
        return self._data
```

## 4. controller.py — NEW (~80-100 lines)

This is the core. Extends `DirectionalTradingControllerBase` — override only `update_processed_data()`.

```python
"""Hyperliquid directional stat-arb controller.

Extends DirectionalTradingControllerBase. Sets signal to 1 (long) or -1 (short)
based on BTC divergence z-score from our signal engine. The base class handles
all executor lifecycle (TP/SL/trailing, cooldown, max executors).
"""
from __future__ import annotations

import logging
from typing import List

from hummingbot.core.data_type.common import PriceType
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import DirectionalTradingControllerBase
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction, StopExecutorAction

from .config import HyperliquidControllerConfig, RuntimeBridge
from .signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class HyperliquidController(DirectionalTradingControllerBase):

    def __init__(self, config: HyperliquidControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

        # Runtime bridge for hot-reload
        self._rb = RuntimeBridge(config.runtime_json_path) if config.runtime_json_path else None

        # Signal engine — reuse from binary_options
        signal_config = {
            "baseline_halflife_secs": config.baseline_halflife_secs,
            "current_halflife_secs": config.current_halflife_secs,
            "mispricing_halflife_secs": config.mispricing_halflife_secs,
            "edge_z_threshold": config.edge_z_threshold,
            "btc_z_threshold": config.btc_z_threshold,
        }
        self._signal_engine = SignalEngine(signal_config, self._rb)
        self._coin = config.trading_pair.split("-")[0]  # e.g. "SOL" from "SOL-USD"

    async def update_processed_data(self):
        """Feed prices to signal engine, set signal for base class."""
        # Hot-reload check
        if self._rb:
            self._rb.check()

        # Get current prices from connector
        try:
            spot_price = float(self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.trading_pair, PriceType.MidPrice))
            btc_price = float(self.market_data_provider.get_price_by_type(
                self.config.btc_connector_name, self.config.btc_trading_pair, PriceType.MidPrice))
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")
            self.processed_data = {"signal": 0, "features": {}}
            return

        # Tick the signal engine
        signals = self._signal_engine.tick(
            coin=self._coin,
            spot_price=spot_price,
            btc_price=btc_price,
            market_duration_seconds=3600,  # dummy, not used for perps
        )

        if not signals:
            self.processed_data = {"signal": 0, "features": {}}
            return

        # Extract z-scores
        z_score = signals.get("z_score", 0.0)
        btc_z = signals.get("btc_z_score", 0.0)
        threshold = self.config.edge_z_threshold

        # Determine signal: positive z = alt overpriced vs BTC → short, negative = underpriced → long
        if z_score > threshold:
            signal = -1  # alt overpriced relative to BTC, short it
        elif z_score < -threshold:
            signal = 1   # alt underpriced relative to BTC, long it
        else:
            signal = 0

        self.processed_data = {
            "signal": signal,
            "features": signals,
            "z_score": z_score,
            "btc_z_score": btc_z,
            "spot_price": spot_price,
            "btc_price": btc_price,
        }

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """Base class handles creation. We add BTC reversal exit."""
        actions = super().determine_executor_actions()

        # BTC reversal exit: if we have active positions and BTC z reverses, close
        btc_z = self.processed_data.get("btc_z_score", 0.0)
        btc_threshold = self.config.btc_z_threshold

        if abs(btc_z) > btc_threshold:
            for executor in self.executors_info:
                if executor.is_active and executor.is_trading:
                    # BTC moving hard — close as safety measure
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=executor.id
                    ))

        return actions

    def to_format_status(self) -> List[str]:
        z = self.processed_data.get("z_score", 0)
        btc_z = self.processed_data.get("btc_z_score", 0)
        sig = self.processed_data.get("signal", 0)
        spot = self.processed_data.get("spot_price", 0)
        btc = self.processed_data.get("btc_price", 0)
        return [
            f"Pair: {self.config.trading_pair} | Signal: {sig} | "
            f"Z: {z:.3f} | BTC_Z: {btc_z:.3f} | "
            f"Spot: {spot:.2f} | BTC: {btc:.2f}"
        ]
```

## 5. __init__.py

```python
from .controller import HyperliquidController
from .config import HyperliquidControllerConfig

__all__ = ["HyperliquidController", "HyperliquidControllerConfig"]
```

## 6. scripts/hyperliquid_strategy.py — COPY + rename

Copy `scripts/binary_options_strategy.py`, rename:
- `BinaryOptionsStrategyConfig` → `HyperliquidStrategyConfig`
- `BinaryOptionsStrategy` → `HyperliquidStrategy`
- `script_file_name` → `hyperliquid_strategy.py`
- `controllers_config` default → `["hyperliquid.yml"]`

## 7. conf/controllers/hyperliquid.yml

```yaml
controller_name: hyperliquid
controller_type: directional_trading
connector_name: hyperliquid_perpetual
trading_pair: SOL-USD
btc_connector_name: hyperliquid_perpetual
btc_trading_pair: BTC-USD
total_amount_quote: 10
leverage: 1
max_executors_per_side: 1
cooldown_time: 60
stop_loss: 0.01
take_profit: 0.02
time_limit: 3600
edge_z_threshold: 1.5
btc_z_threshold: 1.75
runtime_json_path: ""
```

## 8. conf/scripts/hyperliquid_strategy.yml

```yaml
script_file_name: hyperliquid_strategy.py
max_global_drawdown_quote: 20.0
max_controller_drawdown_quote: 10.0
controllers_config:
  - hyperliquid.yml
```

---

## Signal Engine Adaptation Notes

The signal engine expects a `tick()` call with `coin, spot_price, btc_price, market_duration_seconds`.
For perps, `market_duration_seconds` is meaningless (no expiry). Pass a dummy value (3600).

The signal engine internally:
1. Updates `BtcImpliedProfile` with BTC price delta
2. Updates `MispricingProfile` with spot vs BTC-implied price
3. Computes z-scores
4. Returns signal dict: `{z_score, btc_z_score, mispricing, vol, confidence}`

The controller maps this to `signal = 1 / -1 / 0` and the base class handles the rest.

**Important:** Check that `SignalEngine.__init__` signature matches what controller passes.
The binary_options signal engine takes `(config: dict, runtime_bridge: RuntimeBridge)`.
Config is a plain dict of params, not a Pydantic model. This should work as-is.

---

## What We're NOT Building

- Pair scanner / rotation
- Market manager
- Quote manager / MM mode
- Custom exit monitor (using BTC z reversal + hbot TP/SL)
- Custom position tracker (base class handles it)
- Evaluator / Optuna integration
- Dashboard
- Funding rate signal

---

## Build Checklist

1. [ ] Create `controllers/generic/hyperliquid/` directory
2. [ ] Copy `signal_engine.py` from `binary_options/`
3. [ ] Copy `fair_value.py` from `binary_options/`
4. [ ] Create `config.py` (with RuntimeBridge)
5. [ ] Create `controller.py`
6. [ ] Create `__init__.py`
7. [ ] Create `scripts/hyperliquid_strategy.py`
8. [ ] Create `conf/controllers/hyperliquid.yml`
9. [ ] Create `conf/scripts/hyperliquid_strategy.yml`
10. [ ] Verify imports resolve (signal_engine → fair_value → config)
11. [ ] Test: `python -c "from controllers.generic.hyperliquid import HyperliquidController"`
