from typing import List, Optional, Set

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.strategy_frameworks.data_types import BotAction, ExecutorHandlerReport


class GenericController(ControllerBase):
    def __init__(self, config: ControllerConfigBase):
        super().__init__(config)
        self._executor_handler_report = None

    def determine_actions(self) -> Optional[List[BotAction]]:
        """
        Determine actions based on the provided executor handler report.
        """
        pass

    def update_executor_handler_report(self, executor_handler_report: ExecutorHandlerReport):
        """
        Update the executor handler report.
        """
        self._executor_handler_report = executor_handler_report

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
        executor_handler_report = self._executor_handler_report
        if executor_handler_report is not None:
            active_position_executors_df = executor_handler_report.active_position_executors
            if not active_position_executors_df.empty:
                lines.append("Active Position Executors:")
                lines.append(format_df_for_printout(active_position_executors_df, table_format="psql"))
            if len(executor_handler_report.dca_executors) > 0:
                active_dca_executors_df = pd.DataFrame(executor_handler_report.dca_executors)
                lines.append("DCA Executors:")
                dca_cols_to_show = [
                    "status", "trading_pair", "side", "net_pnl_quote", "cum_fee_quote", "net_pnl_pct", "max_loss_quote",
                    "max_amount_quote", "target_position_average_price", "current_position_average_price", "leverage"]
                lines.append(format_df_for_printout(active_dca_executors_df[dca_cols_to_show], table_format="psql"))
        return lines
