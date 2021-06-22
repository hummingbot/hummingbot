from decimal import Decimal
from typing import Dict, List
from hummingbot.core.event.events import PositionMode, FundingInfo
from hummingbot.connector.derivative.position import Position


NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class PerpetualTrading:
    """
    A base class (interface) that defines what perpetual trading is for Hummingbot.
    """

    def __init__(self):
        super().__init__()
        self._account_positions: List[Position] = []
        self._position_mode: PositionMode = None
        self._leverages: Dict[str, int] = {}
        self._funding_info: Dict[str, FundingInfo] = {}
        self._funding_payment_span: List[int] = [0, 0]

    @property
    def account_positions(self) -> List[Position]:
        """
        Returns a list current active open positions
        """
        return self._account_positions

    @property
    def funding_payment_span(self) -> List[int]:
        """
        Time span(in seconds) before and after funding period when exchanges consider active positions eligible for
        funding payment.
        :return: a list of seconds (before and after)
        """
        return self._funding_payment_span

    @property
    def position_mode(self) -> PositionMode:
        return self._position_mode

    @position_mode.setter
    def position_mode(self, value: PositionMode):
        """
        Sets position mode for perpetual trading, a child class might need to override this to set position mode on
        the exchange
        :param value: the position mode
        """
        self._position_mode = value

    def get_leverage(self, trading_pair: str) -> int:
        """
        Gets leverage level of a particular market
        :param trading_pair: the market trading pair
        :return: leverage level
        """
        return self._leverages[trading_pair]

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        """
        Sets leverage level, e.g. 2x, 10x, etc..
        A child class may need to override this to set leverage level on the exchange
        :param trading_pair: the market trading pair
        :param leverage: leverage to be used
        """
        self._leverages[trading_pair] = leverage

    def supported_position_modes(self) -> List[PositionMode]:
        """
        Returns a list of position modes supported by the connector
        """
        raise NotImplementedError

    def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Returns funding information
        :param trading_pair: the market trading pair
        :return: funding info
        """
        return self._funding_info[trading_pair]
