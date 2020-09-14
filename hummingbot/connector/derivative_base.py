from decimal import Decimal
from hummingbot.connector.exchange_base import ExchangeBase


NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class DerivativeBase(ExchangeBase):
    """
    DerivativeBase provide extra funtionality in addition to the ExchangeBase for derivative exchanges
    """

    def __init__(self):
        super().__init__()
