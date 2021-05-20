from decimal import Decimal
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import PositionMode


NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class DerivativeBase(ExchangeBase):
    """
    DerivativeBase provide extra funtionality in addition to the ExchangeBase for derivative exchanges
    """

    def __init__(self):
        super().__init__()
        self._funding_info = {}
        self._account_positions = {}
        self._position_mode = None
        self._leverage = {}
        self._funding_payment_span = [0, 0]  # time span(in seconds) before and after funding period when exchanges consider active positions eligible for funding payment

    def set_position_mode(self, position_mode: PositionMode):
        """
        Should set the _position_mode parameter. i.e self._position_mode = position_mode
        This should also be overwritten if the derivative exchange requires interraction to set mode,
        in addition to setting the _position_mode object.
        :param position_mode: ONEWAY or HEDGE position mode
        """
        self._position_mode = position_mode
        return

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        """
        Should set the _leverage parameter. i.e self._leverage = leverage
        This should also be overwritten if the derivative exchange requires interraction to set leverage,
        in addition to setting the _leverage object.
        :param _leverage: leverage to be used
        """
        self._leverage = leverage
        return

    def supported_position_modes(self):
        """
        returns a list containing the modes supported by the derivative
        ONEWAY and/or HEDGE modes
        """
        return [PositionMode.ONEWAY]

    def get_funding_info(self, trading_pair):
        """
        return a dictionary as follows:
        self._trading_info[trading_pair] = {
        "indexPrice": (i.e "21.169488483519444444")
        "markPrice": price used for both pnl on most derivatives (i.e "21.210103847902463671")
        "nextFundingTime": next funding time in unix timestamp (i.e "1612780270")
        "rate": next funding rate as a decimal and not percentage (i.e 0.00007994084744229488)
        }
        """
        raise NotImplementedError
