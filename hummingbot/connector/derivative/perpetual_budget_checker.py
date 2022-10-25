import typing

from hummingbot.connector.budget_checker import BudgetChecker
from hummingbot.core.data_type.order_candidate import PerpetualOrderCandidate
from hummingbot.connector.perpetual_trading import PerpetualTrading

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

    def _lock_available_collateral(self, order_candidate: PerpetualOrderCandidate):
        if not order_candidate.position_close:
            super()._lock_available_collateral(order_candidate)
