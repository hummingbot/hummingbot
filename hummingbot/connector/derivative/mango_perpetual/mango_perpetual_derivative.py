from decimal import Decimal
from typing import List

from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.solana_base import SolanaBase

from hummingbot.core.event.events import (
    PositionMode,
)

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class MangoPerpetualDerivative(SolanaBase, PerpetualTrading):
    @property
    def base_path(self):
        pass

    def cancel(self, trading_pair: str, client_order_id: str):
        pass

    def c_stop_tracking_order(self, order_id):
        pass

    def get_price(self, trading_pair: str, is_buy: bool, amount: Decimal = s_decimal_NaN) -> Decimal:
        pass

    def supported_position_modes(self) -> List[PositionMode]:
        pass

    @property
    def name(self):
        pass
