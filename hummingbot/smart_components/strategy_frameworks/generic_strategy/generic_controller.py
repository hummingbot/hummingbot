from typing import List, Optional, Set

from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase
from hummingbot.smart_components.strategy_frameworks.data_types import BotAction, ExecutorHandlerReport


class GenericController(ControllerBase):

    def determine_actions(self, executor_handler_report: ExecutorHandlerReport) -> Optional[List[BotAction]]:
        """
        Determine actions based on the provided executor handler report.
        """
        pass

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
        return markets_dict
