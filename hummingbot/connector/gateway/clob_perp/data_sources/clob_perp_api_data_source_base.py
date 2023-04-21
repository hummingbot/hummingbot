from abc import abstractmethod
from decimal import Decimal
from typing import List, Tuple

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway.clob_spot.data_sources.clob_api_data_source_base import CLOBAPIDataSourceBase
from hummingbot.core.data_type.common import PositionMode
from hummingbot.core.data_type.funding_info import FundingInfo


class CLOBPerpAPIDataSourceBase(CLOBAPIDataSourceBase):
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
    async def fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        ...

    @abstractmethod
    async def set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        ...

    @abstractmethod
    async def trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        ...

    @abstractmethod
    async def fetch_positions(self) -> List[Position]:
        ...

    @abstractmethod
    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ...
