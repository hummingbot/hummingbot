import asyncio
from decimal import Decimal
from typing import Dict, List

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.smart_components.executors.executor_orchestrator import ExecutorOrchestrator
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class V2StrategyBase(ScriptStrategyBase):
    exchange = "binance_perpetual"
    trading_pair = "FIL-USDT"
    order_amount_quote = 30
    executor_refresh_time = 20
    closed_executors_buffer: int = 10
    spread = Decimal("0.002")
    position_mode = PositionMode.HEDGE
    leverage = 20
    account_config_set = False

    triple_barrier_config = TripleBarrierConfig(
        stop_loss=Decimal("0.01"),
        take_profit=Decimal("0.001"),
        time_limit=600,
        open_order_type=OrderType.LIMIT,
        take_profit_order_type=OrderType.LIMIT,
    )
    markets = {exchange: {trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.actions_queue = asyncio.Queue()
        self.executors_info: Dict[str, List[ExecutorInfo]] = {}
        self.executor_orchestrator = ExecutorOrchestrator(strategy=self)
        self.listen_to_executors_task: asyncio.Task = asyncio.create_task(self.listen_to_executor_actions())

    async def listen_to_executor_actions(self):
        """
        If a controller or another service sends actions to the queue, the orchestrator will execute them.
        """
        while True:
            action = await self.actions_queue.get()
            self.executor_orchestrator.execute_action(action)

    @property
    def is_perpetual(self) -> bool:
        return "perpetual" in self.exchange.lower()

    def on_stop(self):
        self.executor_orchestrator.stop()

    def on_tick(self):
        self.set_position_mode_and_leverage()
        self.update_executors_info()
        executor_actions: List[ExecutorAction] = self.determine_executor_actions()
        for action in executor_actions:
            self.executor_orchestrator.execute_action(action)

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        actions.extend(self.store_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """
        Create actions proposal based on the current state of the executors.
        """
        create_actions = []
        active_executors_by_side = self.get_active_executors_by_side_and_type(executor_type="position_executor")
        mid_price = self.get_price_by_type(self.exchange, self.trading_pair, PriceType.MidPrice)
        if len(active_executors_by_side[TradeType.BUY]) == 0:
            order_price = mid_price * (1 - self.spread)
            order_amount = self.order_amount_quote / order_price
            create_actions.append(CreateExecutorAction(
                executor_config=PositionExecutorConfig(
                    timestamp=self.current_timestamp,
                    trading_pair=self.trading_pair,
                    exchange=self.exchange,
                    side=TradeType.BUY,
                    amount=order_amount,
                    entry_price=order_price,
                    triple_barrier_config=self.triple_barrier_config,
                    leverage=self.leverage
                )
            ))
        if len(active_executors_by_side[TradeType.SELL]) == 0:
            order_price = mid_price * (1 + self.spread)
            order_amount = self.order_amount_quote / order_price
            create_actions.append(CreateExecutorAction(
                executor_config=PositionExecutorConfig(
                    timestamp=self.current_timestamp,
                    trading_pair=self.trading_pair,
                    exchange=self.exchange,
                    side=TradeType.SELL,
                    amount=order_amount,
                    entry_price=order_price,
                    triple_barrier_config=self.triple_barrier_config,
                    leverage=self.leverage
                )
            ))
        return create_actions

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        stop_actions = []
        active_executors_by_side = self.get_active_executors_by_side_and_type(executor_type="position_executor")
        for side, executors in active_executors_by_side.items():
            for executor in executors:
                if self.refresh_executor_condition(executor):
                    stop_actions.append(StopExecutorAction(executor_id=executor.id))
                elif self.early_stop_condition(executor):
                    stop_actions.append(StopExecutorAction(executor_id=executor.id))
        return stop_actions

    def store_actions_proposal(self) -> List[StoreExecutorAction]:
        """
        Create a list of actions to store the executors that have been stopped.
        """
        store_actions = []
        stopped_executors_by_side = self.get_stopped_executors_by_side_and_type(executor_type="position_executor")
        all_executors = stopped_executors_by_side[TradeType.BUY] + stopped_executors_by_side[TradeType.SELL]
        sorted_executors = sorted(all_executors, key=lambda x: x.timestamp, reverse=True)
        if len(sorted_executors) > self.closed_executors_buffer:
            for executor in sorted_executors[self.closed_executors_buffer:]:
                store_actions.append(StoreExecutorAction(executor_id=executor.id))
        return store_actions

    def refresh_executor_condition(self, executor: ExecutorInfo) -> bool:
        """
        Checks if the order needs to be refreshed.
        You can reimplement this method to add more conditions.
        """
        created_timestamp = executor.timestamp
        is_trading = executor.is_trading
        if created_timestamp + self.executor_refresh_time < self.current_timestamp and not is_trading:
            return True
        return False

    def early_stop_condition(self, executor: ExecutorInfo) -> bool:
        """
        If an executor has an active position, should we close it based on a condition. For example, if you have a
        signal that the market is going to long and you hold a short position, you can close it.
        """
        return False

    def get_active_executors_by_side_and_type(self, executor_type: str) -> Dict[TradeType, List[ExecutorInfo]]:
        active_executors = [executor for executor in self.executors_info.get("main", [])
                            if executor.status != SmartComponentStatus.TERMINATED
                            and executor.type == executor_type]
        long_executors = [executor for executor in active_executors if executor.custom_info["side"] == TradeType.BUY]
        short_executors = [executor for executor in active_executors if executor.custom_info["side"] == TradeType.SELL]
        return {TradeType.BUY: long_executors, TradeType.SELL: short_executors}

    def get_stopped_executors_by_side_and_type(self, executor_type: str) -> Dict[TradeType, List[ExecutorInfo]]:
        stopped_executors = [executor for executor in self.executors_info.get("main", [])
                             if executor.status == SmartComponentStatus.TERMINATED
                             and executor.type == executor_type]
        long_executors = [executor for executor in stopped_executors if executor.custom_info["side"] == TradeType.BUY]
        short_executors = [executor for executor in stopped_executors if executor.custom_info["side"] == TradeType.SELL]
        return {TradeType.BUY: long_executors, TradeType.SELL: short_executors}

    def get_price_by_type(self, connector: str, trading_pair: str, price_type: PriceType) -> Decimal:
        return self.connectors[connector].get_price_by_type(trading_pair, price_type)

    def set_position_mode_and_leverage(self):
        if not self.account_config_set and self.is_perpetual:
            self.connectors[self.exchange].set_position_mode(self.position_mode)
            self.set_leverage(self.exchange, self.trading_pair, self.leverage)
            self.account_config_set = True

    def update_executors_info(self):
        # In this method later on we can send updates to the active controllers
        self.executors_info: Dict[str, List[ExecutorInfo]] = self.executor_orchestrator.get_executors_report()

    def queue_executor_action(self, action: ExecutorAction):
        self.actions_queue.put_nowait(action)

    def set_leverage(self, connector: str, trading_pair: str, leverage: int):
        self.connectors[connector].set_leverage(trading_pair, leverage)

    def set_position_mode(self, connector: str, position_mode: PositionMode):
        self.connectors[connector].set_position_mode(position_mode)

    @staticmethod
    def executors_info_to_df(executors_info: List[ExecutorInfo]) -> pd.DataFrame:
        """
        Convert a list of executor handler info to a dataframe.
        """
        df = pd.DataFrame([ei.dict() for ei in executors_info])
        # Convert the enum values to integers
        df['status'] = df['status'].apply(lambda x: x.value)

        # Sort the DataFrame
        df.sort_values(by='status', ascending=True, inplace=True)

        # Convert back to enums for display
        df['status'] = df['status'].apply(SmartComponentStatus)
        return df[["id", "timestamp", "type", "status", "net_pnl_pct", "net_pnl_quote", "cum_fees_quote", "is_trading",
                   "filled_amount_quote", "close_type"]]

    def format_status(self) -> str:
        original_info = super().format_status()
        columns_to_show = ["id", "type", "status", "net_pnl_pct", "net_pnl_quote", "cum_fees_quote",
                           "filled_amount_quote", "is_trading", "close_type"]
        extra_info = []
        total_pnl_quote = 0
        total_volume_traded = 0
        for controller_id, executors_list in self.executors_info.items():
            extra_info.append(f"Controller: {controller_id}")
            executors_df = self.executors_info_to_df(executors_list)
            extra_info.extend([format_df_for_printout(executors_df[columns_to_show], table_format="psql")])
            total_pnl_quote += executors_df["net_pnl_quote"].sum()
            total_volume_traded += executors_df["filled_amount_quote"].sum()
        total_pnl_pct = total_pnl_quote / total_volume_traded if total_volume_traded > 0 else 0
        format_status = f"{original_info}\n\n" + "\n".join(extra_info) + \
                        f"\nTotal PnL Quote: {total_pnl_quote:.2f}\nTotal Volume Traded: {total_volume_traded:.2f}\nTotal PnL %: {total_pnl_pct:.2f}"
        return format_status
