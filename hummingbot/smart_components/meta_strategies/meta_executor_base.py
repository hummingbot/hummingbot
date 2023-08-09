import asyncio
import datetime
import glob
import os

import pandas as pd

from hummingbot import data_path
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.meta_strategies.data_types import MetaExecutorStatus
from hummingbot.smart_components.meta_strategies.meta_strategy_base import MetaStrategyBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MetaExecutorBase:
    def __init__(self, strategy: ScriptStrategyBase, meta_strategy: MetaStrategyBase, update_interval: float = 1.0):
        self.strategy = strategy
        self.ms = meta_strategy
        self.update_interval = update_interval
        self.terminated = asyncio.Event()
        self.level_executors = {level.level_id: None for level in self.ms.config.order_levels}
        self.status = MetaExecutorStatus.NOT_STARTED

    def start(self):
        self.ms.start()
        safe_ensure_future(self.control_loop())

    def terminate_control_loop(self):
        self.terminated.set()

    def on_stop(self):
        self.ms.stop()

    def on_start(self):
        pass

    async def control_task(self):
        raise NotImplementedError

    def get_csv_path(self) -> str:
        today = datetime.datetime.today()
        csv_path = data_path() + f"{self.ms.get_csv_prefix()}/{today.day:02d}-{today.month:02d}-{today.year}.csv"
        return csv_path

    def store_executor(self, executor: PositionExecutor, order_level: str):
        if executor:
            csv_path = self.get_csv_path()
            executor_data = executor.to_json()
            if not os.path.exists(csv_path):
                headers = executor_data.keys()
                df_header = pd.DataFrame(columns=headers)
                df_header.to_csv(csv_path, mode='a', header=True, index=False)
            df = pd.DataFrame([executor_data])
            df.to_csv(csv_path, mode='a', header=False, index=False)
            self.level_executors[order_level] = None

    def create_executor(self, position_config: PositionConfig, order_level: str):
        executor = PositionExecutor(self.strategy, position_config)
        self.level_executors[order_level] = executor

    async def control_loop(self):
        self.on_start()
        self.status = MetaExecutorStatus.ACTIVE
        while not self.terminated.is_set():
            await self.control_task()
            await asyncio.sleep(self.update_interval)
        self.status = MetaExecutorStatus.TERMINATED
        self.on_stop()

    def close_open_positions(self, connector_name: str = None, trading_pair: str = None):
        # we are going to close all the open positions when the bot stops
        connector = self.strategy.connectors[connector_name]
        for pos_key, position in connector.account_positions.items():
            if position.trading_pair == trading_pair:
                if position.position_side == PositionSide.LONG:
                    self.sell(connector_name=connector_name,
                              trading_pair=position.trading_pair,
                              amount=abs(position.amount),
                              order_type=OrderType.MARKET,
                              price=connector.get_mid_price(position.trading_pair),
                              position_action=PositionAction.CLOSE)
                elif position.position_side == PositionSide.SHORT:
                    self.buy(connector_name=connector_name,
                             trading_pair=position.trading_pair,
                             amount=abs(position.amount),
                             order_type=OrderType.MARKET,
                             price=connector.get_mid_price(position.trading_pair),
                             position_action=PositionAction.CLOSE)

    def get_closed_executors_df(self):
        dfs = [pd.read_csv(file) for file in glob.glob(data_path() + self.ms.get_csv_prefix())]
        return pd.concat(dfs)

    def get_active_executors_df(self):
        executors = [executor.to_json() for executor in self.level_executors.values() if executor]
        return pd.DataFrame(executors)

    @staticmethod
    def summarize_executors_df(executors_df):
        if len(executors_df) > 0:
            net_pnl = executors_df["net_pnl"].sum()
            net_pnl_quote = executors_df["net_pnl_quote"].sum()
            total_executors = executors_df.shape[0]
            total_volume = executors_df["amount"].sum() * 2
            total_long = (executors_df["side"] == "BUY").sum()
            total_short = (executors_df["side"] == "SELL").sum()
            close_types = executors_df.groupby("close_type").count()
            take_profit = (executors_df["close_type"] == "TAKE_PROFIT").sum()
            stop_loss = (executors_df["close_type"] == "STOP_LOSS").sum()
            time_limit = (executors_df["close_type"] == "TIME_LIMIT").sum()
            expired = (executors_df["close_type"] == "EXPIRED").sum()
            early_stop = (executors_df["close_type"] == "EARLY_STOP").sum()
            return {
                "net_pnl": net_pnl,
                "net_pnl_quote": net_pnl_quote,
                "total_executors": total_executors,
                "total_volume": total_volume,
                "total_long": total_long,
                "total_short": total_short,
                "close_types": close_types,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "time_limit": time_limit,
                "expired": expired,
                "early_stop": early_stop,
            }
        return {
            "net_pnl": 0,
            "net_pnl_quote": 0,
            "total_executors": 0,
            "total_volume": 0,
            "total_long": 0,
            "total_short": 0,
            "close_types": 0,
            "take_profit": 0,
            "stop_loss": 0,
            "time_limit": 0,
            "expired": 0,
            "early_stop": 0,
        }

    def closed_executors_info(self):
        closed_executors = self.get_closed_executors_df()
        return self.summarize_executors_df(closed_executors)

    def active_executors_info(self):
        active_executors = self.get_active_executors_df()
        return self.summarize_executors_df(active_executors)

    def to_format_status(self) -> str:
        """
        Base status for meta executors.
        """
        lines = []
        lines.extend(["\n################################## Active Executors ##################################"])

        for level_id, executor in self.level_executors.items():
            lines.extend([f"|Level: {level_id}"])
            if executor:
                lines.extend(executor.to_format_status())
            else:
                lines.extend(["|  No active executor."])
        lines.extend(["\n################################## Performance ##################################"])
        closed_executors_info = self.closed_executors_info()
        active_executors_info = self.active_executors_info()
        lines.extend([f"""
Active executors: {active_executors_info["total_executors"]} | Unrealized PNL (%): {active_executors_info["net_pnl"]}
Closed executors: {closed_executors_info["total_executors"]} | Realized PNL (%): {closed_executors_info["net_pnl"]}
"""])
        return "\n".join(lines)
