from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.backtesting.backtesting_data_provider import BacktestingDataProvider
from hummingbot.smart_components.controllers.controller_base import ControllerConfigBase
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.executors import CloseType


class BacktestingEngineBase:
    def __init__(self):
        self.controller = None

    @staticmethod
    def filter_df_by_time(df, start: Optional[str] = None, end: Optional[str] = None):
        if start is not None:
            start_condition = pd.to_datetime(df["timestamp"], unit="ms") >= datetime.strptime(start, "%Y-%m-%d")
        else:
            start_condition = pd.Series([True] * len(df))
        if end is not None:
            end_condition = pd.to_datetime(df["timestamp"], unit="ms") <= datetime.strptime(end, "%Y-%m-%d")
        else:
            end_condition = pd.Series([True] * len(df))
        return df[start_condition & end_condition]

    def apply_triple_barrier_method(self, df, tp=1.0, sl=1.0, tl=5, trade_cost=0.0006):
        df.index = pd.to_datetime(df.timestamp, unit="ms")
        if "target" not in df.columns:
            df["target"] = 1
        df["tl"] = df.index + pd.Timedelta(seconds=tl)
        df.dropna(subset="target", inplace=True)

        df = self.apply_tp_sl_on_tl(df, tp=tp, sl=sl)

        df = self.get_bins(df, trade_cost)
        df["tp"] = df["target"] * tp
        df["sl"] = df["target"] * sl

        df["take_profit_price"] = df["close"] * (1 + df["tp"] * df["signal"])
        df["stop_loss_price"] = df["close"] * (1 - df["sl"] * df["signal"])

        return df

    @staticmethod
    def get_bins(df, trade_cost):
        # 1) prices aligned with events
        px = df.index.union(df["tl"].values).drop_duplicates()
        px = df.close.reindex(px, method="ffill")

        # 2) create out object
        df["trade_pnl"] = (px.loc[df["close_time"].values].values / px.loc[df.index] - 1) * df["signal"]
        df["net_pnl"] = df["trade_pnl"] - trade_cost
        df["profitable"] = np.sign(df["trade_pnl"] - trade_cost)
        df["close_price"] = px.loc[df["close_time"].values].values
        return df

    @staticmethod
    def apply_tp_sl_on_tl(df: pd.DataFrame, tp: float, sl: float):
        events = df[df["signal"] != 0].copy()
        if tp > 0:
            take_profit = tp * events["target"]
        else:
            take_profit = pd.Series(index=df.index)  # NaNs
        if sl > 0:
            stop_loss = - sl * events["target"]
        else:
            stop_loss = pd.Series(index=df.index)  # NaNs

        for loc, tl in events["tl"].fillna(df.index[-1]).items():
            df0 = df.close[loc:tl]  # path prices
            df0 = (df0 / df.close[loc] - 1) * events.at[loc, "signal"]  # path returns
            df.loc[loc, "stop_loss_time"] = df0[df0 < stop_loss[loc]].index.min()  # earliest stop loss.
            df.loc[loc, "take_profit_time"] = df0[df0 > take_profit[loc]].index.min()  # earliest profit taking.
        df["close_time"] = df[["tl", "take_profit_time", "stop_loss_time"]].dropna(how="all").min(axis=1)
        df["close_type"] = df[["take_profit_time", "stop_loss_time", "tl"]].dropna(how="all").idxmin(axis=1)
        df["close_type"].replace({"take_profit_time": "tp", "stop_loss_time": "sl"}, inplace=True)
        return df

    @staticmethod
    def simulate_position_executor(df: pd.DataFrame, position_executor_config: PositionExecutorConfig, trade_cost: float):
        # TODO: add order type limit support modifying the start time to compute the returns
        start_timestamp = df["timestamp"].min()
        last_timestamp = df["timestamp"].max()
        tp = float(position_executor_config.triple_barrier_config.take_profit)
        sl = float(position_executor_config.triple_barrier_config.stop_loss)
        tl = float(position_executor_config.triple_barrier_config.time_limit)
        if tl:
            tl_timestamp = start_timestamp + tl * 1000
            first_tl_timestamp = df[df["timestamp"] > tl_timestamp]["timestamp"].min()
            last_timestamp = first_tl_timestamp if not pd.isna(first_tl_timestamp) else first_tl_timestamp
        df_filtered = df.loc[df["timestamp"] <= last_timestamp].copy()
        returns = df_filtered["close"].pct_change().fillna(0).values
        cumulative_returns = (1 + returns).cumprod() - 1
        df_filtered.loc[:, "net_pnl_pct"] = cumulative_returns if position_executor_config.side == TradeType.BUY else - cumulative_returns
        first_tp_timestamp = last_timestamp
        first_sl_timestamp = last_timestamp
        if tp:
            first_tp_timestamp = df_filtered[df_filtered["net_pnl_pct"] > tp]["timestamp"].min()
            first_tp_timestamp = first_tp_timestamp if not pd.isna(first_tp_timestamp) else last_timestamp
        if sl:
            first_sl_timestamp = df_filtered[df_filtered["net_pnl_pct"] < -sl]["timestamp"].min()
            first_sl_timestamp = first_sl_timestamp if not pd.isna(first_sl_timestamp) else last_timestamp
        close_timestamp = min(first_tp_timestamp, first_sl_timestamp, last_timestamp)
        if close_timestamp == last_timestamp:
            close_type = CloseType.TIME_LIMIT
        elif close_timestamp == first_tp_timestamp:
            close_type = CloseType.TAKE_PROFIT
        else:
            close_type = CloseType.STOP_LOSS
        processed_df = df_filtered.loc[df_filtered["timestamp"] <= close_timestamp][["timestamp", "close", "net_pnl_pct"]]
        amount = float(position_executor_config.amount)
        try:
            processed_df["net_pnl_quote"] = processed_df["net_pnl_pct"] * amount * processed_df["close"]
            processed_df["cum_fees_quote"] = trade_cost * amount * processed_df["close"].iloc[0]
            processed_df["filled_amount_quote"] = amount * processed_df["close"].iloc[0]
        except Exception as e:
            print(e)
            print(processed_df)
            processed_df["net_pnl_quote"] = 0
            processed_df["cum_fees_quote"] = 0
            processed_df["filled_amount_quote"] = 0
            close_type = CloseType.FAILED
        return {
            "processed_df": processed_df,
            "close_timestamp": close_timestamp,
            "close_type": close_type,
            "config": position_executor_config,
        }

    async def run_backtesting(self, controller_config: ControllerConfigBase, start: int, end: int, trade_cost=0.0006):
        # Load historical candles
        controller_class = controller_config.get_controller_class()
        backtesting_data_provider = BacktestingDataProvider(connectors={}, start_time=start, end_time=end)
        self.controller = controller_class(config=controller_config, market_data_provider=backtesting_data_provider,
                                           actions_queue=None)

        await self.initialize_backtesting_data_provider()
        await self.controller.update_processed_data()
        executors_info = self.simulate_execution(trade_cost=trade_cost)
        results = self.summarize_results(executors_info)
        return {
            "executors": executors_info,
            "results": results,
            "processed_data": self.controller.processed_data,
        }

    async def initialize_backtesting_data_provider(self):
        for config in self.controller.config.candles_config:
            await self.controller.market_data_provider.initialize_candles_feed(config)

    def simulate_execution(self, trade_cost: float):
        raise NotImplementedError

    def get_data(self, start: Optional[str] = None, end: Optional[str] = None):
        raise NotImplementedError

    @staticmethod
    def summarize_results(executors_info, total_amount_quote=1000):
        if len(executors_info) > 0:
            executors_df = pd.DataFrame([ei.to_dict() for ei in executors_info])
            net_pnl_quote = executors_df["net_pnl_quote"].sum()
            total_executors = executors_df.shape[0]
            executors_with_position = executors_df[executors_df["net_pnl_quote"] != 0]
            total_executors_with_position = executors_with_position.shape[0]
            total_volume = executors_with_position["filled_amount_quote"].sum() * 2
            total_long = (executors_with_position["side"] == TradeType.BUY).sum()
            total_short = (executors_with_position["side"] == TradeType.SELL).sum()
            correct_long = ((executors_with_position["side"] == TradeType.BUY) & (executors_with_position["net_pnl_quote"] > 0)).sum()
            correct_short = ((executors_with_position["side"] == TradeType.SELL) & (executors_with_position["net_pnl_quote"] > 0)).sum()
            accuracy_long = correct_long / total_long if total_long > 0 else 0
            accuracy_short = correct_short / total_short if total_short > 0 else 0
            executors_df["close_type_name"] = executors_df["close_type"].apply(lambda x: x.name)
            close_types = executors_df.groupby("close_type_name")["timestamp"].count()

            # Additional metrics
            total_positions = executors_df.shape[0]
            win_signals = executors_df[executors_df["net_pnl_quote"] > 0]
            loss_signals = executors_df[executors_df["net_pnl_quote"] < 0]
            accuracy = win_signals.shape[0] / total_positions
            cumulative_returns = executors_df["net_pnl_quote"].cumsum()
            executors_df["cumulative_returns"] = cumulative_returns
            executors_df["cumulative_volume"] = executors_df["filled_amount_quote"].cumsum()
            executors_df["inventory"] = total_amount_quote + cumulative_returns

            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - peak)
            max_draw_down = np.min(drawdown)
            max_drawdown_pct = max_draw_down / executors_df["inventory"].iloc[0]
            returns = pd.to_numeric(executors_df["cumulative_returns"] / executors_df["cumulative_volume"])
            sharpe_ratio = returns.mean() / returns.std()
            total_won = win_signals.loc[:, "net_pnl_quote"].sum()
            total_loss = - loss_signals.loc[:, "net_pnl_quote"].sum()
            profit_factor = total_won / total_loss if total_loss > 0 else 1
            net_pnl_pct = net_pnl_quote / total_amount_quote

            return {
                "net_pnl": net_pnl_pct,
                "net_pnl_quote": net_pnl_quote,
                "total_executors": total_executors,
                "total_executors_with_position": total_executors_with_position,
                "total_volume": total_volume,
                "total_long": total_long,
                "total_short": total_short,
                "close_types": close_types,
                "accuracy_long": accuracy_long,
                "accuracy_short": accuracy_short,
                "total_positions": total_positions,
                "accuracy": accuracy,
                "max_drawdown_usd": max_draw_down,
                "max_drawdown_pct": max_drawdown_pct,
                "sharpe_ratio": sharpe_ratio,
                "profit_factor": profit_factor,
                "win_signals": win_signals.shape[0],
                "loss_signals": loss_signals.shape[0],
            }
        return {
            "net_pnl": 0,
            "net_pnl_quote": 0,
            "total_executors": 0,
            "total_executors_with_position": 0,
            "total_volume": 0,
            "total_long": 0,
            "total_short": 0,
            "close_types": 0,
            "accuracy_long": 0,
            "accuracy_short": 0,
            "total_positions": 0,
            "accuracy": 0,
            "max_drawdown_usd": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "profit_factor": 0,
            "win_signals": 0,
            "loss_signals": 0,
        }
