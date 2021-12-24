import typing
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from hummingbot.connector.budget_checker import BudgetChecker, OrderCandidate
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.data_type.trade_fee import TradeFee
from hummingbot.core.event.events import TradeType

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


@dataclass
class PerpetualOrderCandidate(OrderCandidate):
    leverage: Decimal = Decimal("1")
    position_close: bool = False


class PerpetualBudgetChecker(BudgetChecker):
    def __init__(self, exchange: "ExchangeBase"):
        """
        In the case of derived instruments, the collateral can be any token.
        To get this information, this class uses the `get_buy_collateral_token`
        and `get_sell_collateral_token` methods provided by the `PerpetualTrading` interface.
        """
        super().__init__(exchange)
        self._validate_perpetual_connector()

    def _validate_perpetual_connector(self):
        if not isinstance(self._exchange, PerpetualTrading):
            raise TypeError(
                f"{self.__class__} must be passed an exchange implementing the {PerpetualTrading} interface."
            )

    def _get_order_collateral_token(self, order_candidate: PerpetualOrderCandidate) -> Optional[str]:
        if order_candidate.position_close:
            oc_token = None  # the contract is the collateral
        else:
            oc_token = self._get_collateral_token(order_candidate)
        return oc_token

    def _get_order_collateral_amount(
        self, order_candidate: PerpetualOrderCandidate, order_collateral_token: str
    ) -> Decimal:
        if order_candidate.position_close:
            oc_amount = Decimal("0")  # the contract is the collateral
        else:
            oc_amount = self._get_collateral_amount(order_candidate)
        return oc_amount

    def _populate_percent_fee_collateral_entry(
        self, order_candidate: PerpetualOrderCandidate, fee: TradeFee
    ) -> OrderCandidate:
        if not order_candidate.position_close:
            order_candidate = super()._populate_percent_fee_collateral_entry(order_candidate, fee)
        return order_candidate

    def _get_returns_token(self, order_candidate: PerpetualOrderCandidate) -> Optional[str]:
        if order_candidate.position_close:
            r_token = self._get_collateral_token(order_candidate)
        else:
            r_token = None  # the contract is the returns
        return r_token

    def _get_returns_amount(self, order_candidate: PerpetualOrderCandidate) -> Decimal:
        if order_candidate.position_close:
            r_amount = self._get_collateral_amount(order_candidate)
        else:
            r_amount = Decimal("0")  # the contract is the returns
        return r_amount

    def _get_collateral_amount(self, order_candidate: PerpetualOrderCandidate) -> Decimal:
        if order_candidate.position_close:
            order_candidate = self._flip_order_side(order_candidate)
        order_size, size_token = self._get_order_size_and_size_token(order_candidate)
        if order_candidate.position_close:
            order_candidate = self._flip_order_side(order_candidate)
        order_token = self._get_collateral_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate, order_token)
        amount = order_size * size_collateral_price / order_candidate.leverage
        return amount

    def _get_collateral_token(self, order_candidate: PerpetualOrderCandidate) -> str:
        trading_pair = order_candidate.trading_pair
        if order_candidate.order_side == TradeType.BUY:
            token = self._exchange.get_buy_collateral_token(trading_pair)
        else:
            token = self._exchange.get_sell_collateral_token(trading_pair)
        return token

    def _lock_available_collateral(self, order_candidate: PerpetualOrderCandidate):
        if not order_candidate.position_close:
            super()._lock_available_collateral(order_candidate)

    @staticmethod
    def _flip_order_side(order_candidate: PerpetualOrderCandidate) -> PerpetualOrderCandidate:
        order_candidate.order_side = (
            TradeType.BUY if order_candidate.order_side == TradeType.SELL
            else TradeType.SELL
        )
        return order_candidate
