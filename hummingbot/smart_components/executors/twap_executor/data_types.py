from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import validator

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.executors.data_types import ExecutorConfigBase


class TWAPMode(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class TWAPExecutorConfig(ExecutorConfigBase):
    type: str = "twap_executor"
    connector_name: str
    trading_pair: str
    side: TradeType
    leverage: int = 1
    total_amount_quote: Decimal
    total_duration: int
    order_interval: int
    mode: TWAPMode = TWAPMode.TAKER

    # MAKER mode specific parameters
    limit_order_buffer: Optional[Decimal] = Decimal("0.0005")
    order_resubmission_time: Optional[int] = Decimal("20")

    @validator('limit_order_buffer', 'order_resubmission_time', always=True)
    def validate_maker_params(cls, v, values):
        if values.get('mode') != TWAPMode.MAKER:
            return None
        return v

    @property
    def is_maker(self) -> bool:
        return self.mode == TWAPMode.MAKER

    @property
    def number_of_orders(self) -> int:
        return (self.total_duration // self.order_interval) + 1

    @property
    def order_amount_quote(self) -> Decimal:
        return self.total_amount_quote / self.number_of_orders

    @property
    def order_type(self) -> OrderType:
        return OrderType.LIMIT if self.is_maker else OrderType.MARKET
