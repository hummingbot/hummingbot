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
