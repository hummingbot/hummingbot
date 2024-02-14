from typing import List, Optional, Set

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.smart_components.models.executor_actions import ExecutorAction
from hummingbot.smart_components.models.executors_info import ExecutorHandlerInfo, ExecutorInfo
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase, ControllerConfigBase


class GenericController(ControllerBase):
    def __init__(self, config: ControllerConfigBase):
        super().__init__(config)
        self._executor_handler_info: Optional[ExecutorHandlerInfo] = None

    async def determine_actions(self) -> Optional[List[ExecutorAction]]:
        """
        Determine actions based on the provided executor handler report.
        """
        pass

    async def update_executor_handler_report(self, executor_handler_info: ExecutorHandlerInfo):
        """
        Update the executor handler report.
        """
        self._executor_handler_info = executor_handler_info

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
        return markets_dict

    def to_format_status(self) -> list:
        """
        Formats the status of the controller.
        """
        lines = []
        executor_handler_report = self._executor_handler_info
        if executor_handler_report is not None:
            active_position_executors = executor_handler_report.active_position_executors
            active_dca_executors = executor_handler_report.active_dca_executors
            active_arbitrage_executors = executor_handler_report.active_arbitrage_executors
            closed_position_executors = executor_handler_report.closed_position_executors
            closed_dca_executors = executor_handler_report.closed_dca_executors
            closed_arbitrage_executors = executor_handler_report.closed_arbitrage_executors

            if len(active_position_executors) > 0:
                lines.append("Active Position Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(active_position_executors), table_format="psql")])
            if len(active_dca_executors) > 0:
                lines.append("Active DCA Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(active_dca_executors), table_format="psql")])
            if len(active_arbitrage_executors) > 0:
                lines.append("Active Arbitrage Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(active_arbitrage_executors), table_format="psql")])
            if len(closed_position_executors) > 0:
                lines.append("Closed Position Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(closed_position_executors), table_format="psql")])
            if len(closed_dca_executors) > 0:
                lines.append("Closed DCA Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(closed_dca_executors), table_format="psql")])
            if len(closed_arbitrage_executors) > 0:
                lines.append("Closed Arbitrage Executors:")
                lines.extend([format_df_for_printout(self.executors_info_to_df(closed_arbitrage_executors), table_format="psql")])
        return lines

    @staticmethod
    def executors_info_to_df(executors_info: List[ExecutorInfo]) -> pd.DataFrame:
        """
        Convert a list of executor handler info to a dataframe.
        """
        df = pd.DataFrame([ei.dict() for ei in executors_info])
        return df[["id", "timestamp", "type", "status", "net_pnl_pct", "net_pnl_quote", "cum_fees_quote", "is_trading", "close_type"]]
