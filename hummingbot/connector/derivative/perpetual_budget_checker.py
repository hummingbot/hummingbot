import typing

from hummingbot.connector.budget_checker import BudgetChecker, OrderCandidate
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import TradeType, TradeFee

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


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

    def _get_collateral_token(self, order_candidate: OrderCandidate) -> str:
        trading_pair = order_candidate.trading_pair
        if order_candidate.order_side == TradeType.BUY:
            collateral_token = self._exchange.get_buy_collateral_token(trading_pair)
        else:
            collateral_token = self._exchange.get_sell_collateral_token(trading_pair)
        return collateral_token

    def _get_fee(self, order_candidate: OrderCandidate) -> TradeFee:
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
