import logging

from hummingbot.logger import HummingbotLogger

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.perpetual_trading import PerpetualTrading


s_logger = None


class BybitPerpetualDerivative(ExchangeBase, PerpetualTrading):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 bybit_api_key: str,
                 bybit_secret_key: str):
        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)

    async def _update_balances(self):
        pass
