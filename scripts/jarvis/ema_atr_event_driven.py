import os
from decimal import Decimal
from typing import Any, Dict, Optional, Set

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import PositionAction
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.event_driven_strategy_v2_base import EventDrivenStrategyV2Base


class EmaAtrConfig(BaseClientModel):
    """
    Reference EMA + ATR event-driven strategy configuration.
    """

    script_file_name: str = os.path.basename(__file__)
    connector_name: str = Field("hyperliquid_perpetual", description="Connector name to trade on.")
    trading_pair: str = Field("BTC-PERP", description="Trading pair (HB format).")
    timeframe: str = Field("1m", description="Market data timeframe the strategy listens to.")
    fast_ema_period: int = Field(12, ge=1, description="Fast EMA length.")
    slow_ema_period: int = Field(26, ge=2, description="Slow EMA length.")
    atr_period: int = Field(14, ge=1, description="ATR smoothing length.")
    atr_threshold: Decimal = Field(Decimal("30"), description="Minimum ATR required to trade.")
    risk_pct_per_trade: Decimal = Field(Decimal("0.03"), description="Quote balance percentage to risk per trade.")
    md_topic_prefix: str = Field("md", description="Event bus topic prefix for market data.")


class EmaAtrStrategy(EventDrivenStrategyV2Base):
    """
    Reference event-driven EMA cross + ATR filter strategy used by Jarvis.
    Subscribes to shared market data topics (`md.<symbol>.<timeframe>`) and reacts immediately to EMA crosses.
    """

    markets: Dict[str, Set[str]] = {}

    def __init__(self, connectors: Dict[str, Any], config: EmaAtrConfig):
        super().__init__(connectors, config)
        self.config = config
        self._md_bus = None
        self._md_subscription = None
        self._last_cross: Optional[str] = None

    @classmethod
    def init_markets(cls, config: EmaAtrConfig):
        cls.markets = {config.connector_name: {config.trading_pair}}

    def bind_market_data_bus(self, bus: Any):
        """
        Injects an EventBus-compatible instance (must expose async publish/subscribe).
        """
        self._md_bus = bus

    async def _start_loops(self):
        if self._md_bus is None:
            raise RuntimeError("Market data bus must be bound before starting the EMA ATR strategy.")
        topic = self._topic_name()
        subscription = await self._md_bus.subscribe(topic)
        self._md_subscription = self._track_subscription(subscription)
        self._spawn_task(self._consume_market_data(subscription))

    async def _consume_market_data(self, subscription):
        async for payload in subscription:
            if self._stopping:
                break
            if not isinstance(payload, dict):
                continue
            await self._handle_market_data(payload)

    async def _handle_market_data(self, payload: Dict[str, Any]):
        ema_fast = self._to_decimal(payload.get("ema_fast"))
        ema_slow = self._to_decimal(payload.get("ema_slow"))
        atr_value = self._to_decimal(payload.get("atr"))
        if ema_fast is None or ema_slow is None or atr_value is None:
            return

        previous_cross = self._last_cross
        if ema_fast > ema_slow:
            self._last_cross = "bullish"
        elif ema_fast < ema_slow:
            self._last_cross = "bearish"
        else:
            self._last_cross = previous_cross

        if atr_value < self.config.atr_threshold:
            return

        has_position = self._has_open_long_position()
        if self._last_cross == "bullish" and not has_position:
            await self._open_long()
        elif self._last_cross == "bearish" and has_position:
            await self._close_long()

    async def _open_long(self):
        connector = self._connector
        mid_price = connector.get_mid_price(self.config.trading_pair)
        if mid_price is None or mid_price <= 0:
            return
        price = Decimal(str(mid_price))
        if price <= Decimal("0"):
            return
        _, quote_asset = split_hb_trading_pair(self.config.trading_pair)
        quote_balance = self._to_decimal(connector.get_available_balance(quote_asset))
        if quote_balance is None or quote_balance <= Decimal("0"):
            return
        risk_cap = max(quote_balance * self.config.risk_pct_per_trade, Decimal("0"))
        if risk_cap <= Decimal("0"):
            return
        amount = connector.quantize_order_amount(
            self.config.trading_pair,
            (risk_cap / price)
        )
        if amount <= Decimal("0"):
            return
        self.buy(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
            position_action=PositionAction.OPEN,
        )

    async def _close_long(self):
        connector = self._connector
        position = self._get_open_position()
        if position is None or position.amount <= Decimal("0"):
            return
        amount = connector.quantize_order_amount(self.config.trading_pair, Decimal(position.amount))
        if amount <= Decimal("0"):
            return
        mid_price = connector.get_mid_price(self.config.trading_pair)
        price = self._to_decimal(mid_price) or Decimal("0")
        if price <= Decimal("0"):
            return
        price = connector.quantize_order_price(self.config.trading_pair, price)
        self.sell(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
            position_action=PositionAction.CLOSE,
        )

    def _topic_name(self) -> str:
        return f"{self.config.md_topic_prefix}.{self.config.trading_pair}.{self.config.timeframe}"

    @property
    def _connector(self):
        return self.connectors[self.config.connector_name]

    def _has_open_long_position(self) -> bool:
        return self._get_open_position() is not None

    def _get_open_position(self) -> Optional[Position]:
        connector = self._connector
        if not hasattr(connector, "account_positions"):
            return None
        for position in connector.account_positions.values():
            if position.trading_pair == self.config.trading_pair and Decimal(position.amount) > Decimal("0"):
                return position
        return None

    @staticmethod
    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None
