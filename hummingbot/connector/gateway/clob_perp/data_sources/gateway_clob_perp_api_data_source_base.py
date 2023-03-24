import asyncio
import time
from abc import abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway.clob.clob_constants import DECIMAL_NaN
from hummingbot.connector.gateway.clob.clob_types import OrderType
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.core.data_type.common import PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.events import AccountEvent, MarketEvent, OrderBookDataSourceEvent


class GatewayCLOBPerpAPIDataSourceBase(GatewayCLOBAPIDataSourceBase):

    def __init__(self):
        super().__init__()

    @staticmethod
    def supported_stream_events() -> List[Enum]:
        return [
            MarketEvent.TradeUpdate,
            MarketEvent.OrderUpdate,
            AccountEvent.BalanceEvent,
            OrderBookDataSourceEvent.TRADE_EVENT,
            OrderBookDataSourceEvent.DIFF_EVENT,
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
            OrderBookDataSourceEvent.FUNDING_INFO_EVENT
        ]

    @staticmethod
    async def _sleep(delay: float):
        await asyncio.sleep(delay)

    @staticmethod
    def _time() -> float:
        return time.time()

    @property
    @abstractmethod
    def supported_position_modes(self) -> List[PositionMode]:
        ...

    @abstractmethod
    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        ...

    @abstractmethod
    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        ...

    @abstractmethod
    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = DECIMAL_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        ...

    @abstractmethod
    async def fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        ...

    @abstractmethod
    async def set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        ...

    @abstractmethod
    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        ...

    @abstractmethod
    async def fetch_positions(self) -> List[Position]:
        ...
        ...

    @abstractmethod
    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ...

    @abstractmethod
    async def parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # This function should enqueue a FundingInfoUpdate obj into message_queue as presented in the function argument
        ...
