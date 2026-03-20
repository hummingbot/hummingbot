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
    controller_type: str = "generic"
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

    def get_controller_class(self):
        from .controller import HyperliquidController
        return HyperliquidController

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
