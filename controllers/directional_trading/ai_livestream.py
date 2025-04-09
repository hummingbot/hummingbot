from decimal import Decimal
from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.remote_iface.mqtt import ExternalTopicFactory
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class AILivestreamControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "ai_livestream"
    candles_config: List[CandlesConfig] = []
    long_threshold: float = Field(default=0.5, json_schema_extra={"is_updatable": True})
    short_threshold: float = Field(default=0.5, json_schema_extra={"is_updatable": True})
    topic: str = "hbot/predictions"


class AILivestreamController(DirectionalTradingControllerBase):
    def __init__(self, config: AILivestreamControllerConfig, *args, **kwargs):
        self.config = config
        super().__init__(config, *args, **kwargs)
        # Start ML signal listener
        self._init_ml_signal_listener()

    def _init_ml_signal_listener(self):
        """Initialize a listener for ML signals from the MQTT broker"""
        try:
            normalized_pair = self.config.trading_pair.replace("-", "_").lower()
            topic = f"{self.config.topic}/{normalized_pair}/ML_SIGNALS"
            self._ml_signal_listener = ExternalTopicFactory.create_async(
                topic=topic,
                callback=self._handle_ml_signal,
                use_bot_prefix=False,
            )
            self.logger().info("ML signal listener initialized successfully")
        except Exception as e:
            self.logger().error(f"Failed to initialize ML signal listener: {str(e)}")
            self._ml_signal_listener = None

    def _handle_ml_signal(self, signal: dict, topic: str):
        """Handle incoming ML signal"""
        # self.logger().info(f"Received ML signal: {signal}")
        short, neutral, long = signal["probabilities"]
        if short > self.config.short_threshold:
            self.processed_data["signal"] = -1
        elif long > self.config.long_threshold:
            self.processed_data["signal"] = 1
        else:
            self.processed_data["signal"] = 0
        self.processed_data["features"] = signal

    async def update_processed_data(self):
        pass

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal):
        """
        Get the executor config based on the trade_type, price and amount. This method can be overridden by the
        subclasses if required.
        """
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=trade_type,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config.new_instance_with_adjusted_volatility(
                volatility_factor=self.processed_data["features"].get("target_pct", 0.01)),
            leverage=self.config.leverage,
        )

    def to_format_status(self) -> List[str]:
        lines = []
        features = self.processed_data.get("features", {})
        lines.append(f"Signal: {self.processed_data.get('signal', 'N/A')}")
        lines.append(f"Timestamp: {features.get('timestamp', 'N/A')}")
        lines.append(f"Probabilities: {features.get('probabilities', 'N/A')}")
        lines.append(f"Target Pct: {features.get('target_pct', 'N/A')}")
        return lines
