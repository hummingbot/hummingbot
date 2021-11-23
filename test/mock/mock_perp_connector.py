from decimal import Decimal

from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import PositionMode
from test.mock.mock_paper_exchange import MockPaperExchange


class MockPerpConnector(MockPaperExchange, PerpetualTrading):
    def __init__(self, fee_percent: Decimal = Decimal("0")):
        MockPaperExchange.__init__(self, fee_percent)
        PerpetualTrading.__init__(self)
        self._budget_checker = PerpetualBudgetChecker(exchange=self)
        self._funding_payment_span = [0, 10]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def name(self):
        return "MockPerpConnector"

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        return self._budget_checker
