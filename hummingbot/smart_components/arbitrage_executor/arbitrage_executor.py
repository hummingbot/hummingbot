import itertools
import logging

from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.arbitrage_executor.data_types import (
    ArbitrageConfig,
    ArbitrageExecutorStatus,
    ArbitrageOpportunity,
)
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ArbitrageExecutor(SmartComponentBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, arbitrage_config: ArbitrageConfig):
        connectors = set(exchange for exchange, trading_pair in arbitrage_config)
        self.arbitrage_config = arbitrage_config
        self.arbitrage_status = ArbitrageExecutorStatus.NOT_STARTED
        self.arbitrage_paths = self.generate_all_opportunities()
        super().__init__(strategy, list(connectors))

    def generate_all_opportunities(self):
        opportunities = []
        for pair1, pair2 in itertools.combinations(self.arbitrage_config.markets, 2):
            if self.validate_pair(pair1, pair2):
                opportunity = ArbitrageOpportunity(buying_market=pair1.exchange,
                                                   selling_market=pair2.exchange)
                opportunities.append(opportunity)
        return opportunities

    @staticmethod
    def validate_pair(pair1, pair2):
        base_asset1, quote_asset1 = pair1.trading_pair.split('/')
        base_asset2, quote_asset2 = pair2.trading_pair.split('/')
        return base_asset1 == base_asset2 and quote_asset1 == quote_asset2

    def control_task(self):
        pass
