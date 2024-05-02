from decimal import Decimal

from hummingbot.smart_components.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.smart_components.models.executors_info import ExecutorInfo


class DirectionalTradingBacktesting(BacktestingEngineBase):
    def simulate_execution(self, trade_cost: float):
        if "features" not in self.controller.processed_data:
            raise ValueError("Features not found in processed data")
        processed_features = self.controller.processed_data["features"].copy()
        active_executors = []
        stopped_executors_info = []
        connector_name = self.controller.config.connector_name
        trading_pair = self.controller.config.trading_pair
        for i, row in self.controller.processed_data["features"].iterrows():
            timestamp = row["timestamp"]
            self.controller.processed_data["signal"] = row["signal"]
            self.controller.processed_data["features"] = processed_features.loc[:i]
            self.controller.market_data_provider.prices = {f"{connector_name}_{trading_pair}": Decimal(row["close"])}
            self.controller.market_data_provider._time = timestamp
            executor_actions = self.controller.determine_executor_actions()
            for action in executor_actions:
                if isinstance(action, CreateExecutorAction):
                    if isinstance(action.executor_config, PositionExecutorConfig):
                        executor_data = self.simulate_position_executor(
                            df=processed_features.loc[i:],
                            position_executor_config=action.executor_config,
                            trade_cost=trade_cost
                        )
                        if executor_data["close_type"] == CloseType.FAILED:
                            continue
                        active_executors.append(executor_data)
                    else:
                        raise NotImplementedError(f"Executor type {action.executor_config.__class__.__name__} not supported")
                elif isinstance(action, StopExecutorAction):
                    for executor in active_executors:
                        if executor["config"].id == action.executor_id:
                            executor["close_type"] = CloseType.EARLY_STOP
                            executor["close_timestamp"] = timestamp
                            processed_df = executor["processed_df"]
                            final_result = processed_df.loc[processed_df["timestamp"] == timestamp]
                            stopped_executors_info.append(ExecutorInfo(
                                id=executor["config"].id,
                                timestamp=executor["config"].timestamp,
                                type=executor["config"].type,
                                close_timestamp=executor["close_timestamp"],
                                close_type=executor["close_type"],
                                status=SmartComponentStatus.TERMINATED,
                                config=executor["config"],
                                net_pnl_pct=final_result["net_pnl_pct"].values[0],
                                net_pnl_quote=final_result["net_pnl_quote"].values[0],
                                cum_fees_quote=final_result["cum_fees_quote"].values[0],
                                filled_amount_quote=final_result["filled_amount_quote"].values[0],
                                is_active=False,
                                is_trading=False,
                                custom_info={"side": executor["config"].side, "close_price": row["close"]},
                            ))
                            active_executors = [e for e in active_executors if e["config"].id != action.executor_id]
            active_executors_info = []
            for executor in active_executors:
                if executor["close_timestamp"] <= row["timestamp"]:
                    processed_df = executor["processed_df"]
                    final_result = processed_df.iloc[-1]
                    stopped_executors_info.append(ExecutorInfo(
                        id=executor["config"].id,
                        timestamp=executor["config"].timestamp,
                        type=executor["config"].type,
                        close_timestamp=executor["close_timestamp"],
                        close_type=executor["close_type"],
                        status=SmartComponentStatus.TERMINATED,
                        config=executor["config"],
                        net_pnl_pct=final_result["net_pnl_pct"],
                        net_pnl_quote=final_result["net_pnl_quote"],
                        cum_fees_quote=final_result["cum_fees_quote"],
                        filled_amount_quote=final_result["filled_amount_quote"],
                        is_active=False,
                        is_trading=False,
                        custom_info={"side": executor["config"].side, "close_price": row["close"]},
                    ))
                    active_executors = [e for e in active_executors if e["config"].id != executor["config"].id]
                else:
                    current_stats = executor["processed_df"].loc[executor["processed_df"]["timestamp"] == timestamp]
                    active_executors_info.append(ExecutorInfo(
                        id=executor["config"].id,
                        timestamp=executor["config"].timestamp,
                        type=executor["config"].type,
                        close_timestamp=None,
                        close_type=None,
                        status=SmartComponentStatus.RUNNING,
                        config=executor["config"],
                        net_pnl_pct=current_stats["net_pnl_pct"].values[0],
                        net_pnl_quote=current_stats["net_pnl_quote"].values[0],
                        cum_fees_quote=current_stats["cum_fees_quote"].values[0],
                        filled_amount_quote=current_stats["filled_amount_quote"].values[0],
                        is_active=True,
                        is_trading=True,
                        custom_info={"side": executor["config"].side, "close_price": row["close"]},
                    ))
            self.controller.executors_info = active_executors_info + stopped_executors_info
        return self.controller.executors_info
