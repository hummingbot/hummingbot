"""Hyperliquid directional stat-arb controller.

BTC-ALT divergence tracking: when ALT lags BTC movement, enter expecting
catch-up. Uses the three-layer EMA system from our signal engine.

Extends DirectionalTradingControllerBase — set signal to 1/-1/0 and the
base class handles PositionExecutor lifecycle (TP/SL/trailing/cooldown).
"""
from __future__ import annotations

import logging
import time
from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import PriceType
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction, StopExecutorAction

from .hyperliquid_signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class HyperliquidStatArbConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "hyperliquid_stat_arb"

    # BTC reference pair (same connector)
    btc_trading_pair: str = Field(
        default="BTC-USD",
        json_schema_extra={
            "prompt": "Enter the BTC reference trading pair: ",
            "prompt_on_new": True,
        })

    # Signal thresholds
    edge_z_threshold: float = Field(
        default=1.5,
        json_schema_extra={
            "prompt": "Enter the z-score threshold for entry: ",
            "prompt_on_new": True,
        })
    btc_z_threshold: float = Field(
        default=1.75,
        json_schema_extra={
            "prompt": "Enter the BTC z-score threshold for reversal exit: ",
            "prompt_on_new": True,
        })

    # Signal engine params
    baseline_halflife_secs: float = Field(default=35.0)
    current_halflife_secs: float = Field(default=12.0)

    def update_markets(self, markets: dict) -> dict:
        """Register both the trading pair AND BTC pair for price data."""
        markets = super().update_markets(markets)
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.btc_trading_pair)
        return markets


class HyperliquidStatArbController(DirectionalTradingControllerBase):

    def __init__(self, config: HyperliquidStatArbConfig, *args, **kwargs):
        self.config = config
        self._coin = config.trading_pair.split("-")[0]
        self._signal_engine = SignalEngine({
            "baseline_halflife_secs": config.baseline_halflife_secs,
            "current_halflife_secs": config.current_halflife_secs,
            "edge_z_threshold": config.edge_z_threshold,
            "btc_z_threshold": config.btc_z_threshold,
        })
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        """Feed prices to signal engine, set signal for base class."""
        try:
            spot_price = float(self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.trading_pair, PriceType.MidPrice))
            btc_price = float(self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.btc_trading_pair, PriceType.MidPrice))
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")
            self.processed_data["signal"] = 0
            self.processed_data["features"] = {}
            return

        signals = self._signal_engine.tick(
            coin=self._coin,
            spot_price=spot_price,
            btc_price=btc_price,
            now_ts=time.time(),
        )

        self.processed_data["signal"] = signals.get("signal", 0)
        self.processed_data["features"] = signals

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """Base class handles creation. Add BTC reversal exit."""
        actions = super().determine_executor_actions()

        features = self.processed_data.get("features", {})
        btc_z = features.get("btc_z_score", 0.0)

        if abs(btc_z) > self.config.btc_z_threshold:
            for executor in self.executors_info:
                if executor.is_active and executor.is_trading:
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=executor.id
                    ))

        return actions

    def to_format_status(self) -> List[str]:
        features = self.processed_data.get("features", {})
        sig = self.processed_data.get("signal", 0)
        z = features.get("z_score", 0)
        btc_z = features.get("btc_z_score", 0)
        spot = features.get("spot_price", 0)
        btc = features.get("btc_price", 0)
        events = features.get("total_events", 0)
        conf = features.get("confidence", "LOW")
        return [
            f"Signal: {sig} | Z: {z:.3f} | BTC_Z: {btc_z:.3f} | "
            f"Spot: {spot:.2f} | BTC: {btc:.2f} | Events: {events} | Conf: {conf}"
        ]
