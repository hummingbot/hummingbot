import typing
from dataclasses import dataclass
from decimal import Decimal

from hummingbot.connector.budget_checker import BudgetChecker, OrderCandidate
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import TradeFee, TradeType

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

    def _get_collateral_token(self, order_candidate: PerpetualOrderCandidate) -> str:
        trading_pair = order_candidate.trading_pair
        if order_candidate.order_side == TradeType.BUY:
            collateral_token = self._exchange.get_buy_collateral_token(trading_pair)
        else:
            collateral_token = self._exchange.get_sell_collateral_token(trading_pair)
        return collateral_token

    def _get_base_required_collateral(self, order_candidate: PerpetualOrderCandidate) -> Decimal:
        if order_candidate.position_close:
            required_collateral = self._get_close_base_required_collateral()
        else:
            required_collateral = self._get_open_base_required_collateral(order_candidate)
        return required_collateral

    @staticmethod
    def _get_close_base_required_collateral() -> Decimal:
        required_collateral = Decimal("0")
        return required_collateral

    def _get_open_base_required_collateral(self, order_candidate: PerpetualOrderCandidate) -> Decimal:
        order_size, size_token = self._get_order_size_and_size_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate)
        required_collateral = order_size * size_collateral_price / order_candidate.leverage
        return required_collateral

    def _get_fee(self, order_candidate: PerpetualOrderCandidate) -> TradeFee:
        if order_candidate.position_close:
            fee = self._get_close_fee()
        else:
            fee = self._get_open_fee(order_candidate)
        return fee

    @staticmethod
    def _get_close_fee() -> TradeFee:
        fee = TradeFee(percent=Decimal("0"))
        return fee

    def _get_open_fee(self, order_candidate: PerpetualOrderCandidate) -> TradeFee:
        _, size_token = self._get_order_size_and_size_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate)
        adjustment_base = size_token
        adjustment_quote = order_candidate.collateral_token

        fee = self._exchange.get_fee(
            adjustment_base,
            adjustment_quote,
            order_candidate.order_type,
            order_candidate.order_side,
            order_candidate.amount,
            size_collateral_price,
        )

        return fee

    def _lock_available_collateral(self, order_candidate: PerpetualOrderCandidate):
        if not order_candidate.position_close:
            self._locked_collateral[order_candidate.collateral_token] += order_candidate.collateral_amount
