from hummingsim.backtest.backtest_market import BacktestMarket
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import PositionMode


class MockPerpConnector(BacktestMarket, PerpetualTrading):
    def __init__(self):
        BacktestMarket.__init__(self)
        PerpetualTrading.__init__(self)
        self._funding_payment_span = [0, 10]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]
