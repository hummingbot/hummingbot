from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from hummingbot.smart_components.controllers.controller_base import ControllerBase


class BacktestingEngineBase:
    def __init__(self, controller: ControllerBase):
        """
        Initialize the BacktestExecutorBase.

        :param controller: The controller instance.
        :param start_date: Start date for backtesting.
        :param end_date: End date for backtesting.
        """
        self.controller = controller
        self.processed_data = None
        self.executors_df = None
        self.results = None

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

    def run_backtesting(self, initial_portfolio_usd=1000, trade_cost=0.0006,
                        start: Optional[str] = None, end: Optional[str] = None):
        # Load historical candles
        processed_data = self.get_data(start=start, end=end)

        # Apply the specific execution logic of the executor handler vectorized
        executors_df = self.simulate_execution(processed_data, initial_portfolio_usd=initial_portfolio_usd, trade_cost=trade_cost)

        # Store data for further analysis
        self.processed_data = processed_data
        self.executors_df = executors_df
        self.results = self.summarize_results(executors_df)
        return {
            "processed_data": processed_data,
            "executors_df": executors_df,
            "results": self.results
        }

    def simulate_execution(self, df: pd.DataFrame, initial_portfolio_usd: float, trade_cost: float):
        raise NotImplementedError

    def get_data(self, start: Optional[str] = None, end: Optional[str] = None):
        raise NotImplementedError

    @staticmethod
    def summarize_results(executors_df):
        if len(executors_df) > 0:
            net_pnl = executors_df["net_pnl"].sum()
            net_pnl_quote = executors_df["net_pnl_quote"].sum()
            total_executors = executors_df.shape[0]
            executors_with_position = executors_df[executors_df["net_pnl"] != 0]
            total_executors_with_position = executors_with_position.shape[0]
            total_volume = executors_with_position["amount"].sum() * 2
            total_long = (executors_with_position["side"] == "BUY").sum()
            total_short = (executors_with_position["side"] == "SELL").sum()
            correct_long = ((executors_with_position["side"] == "BUY") & (executors_with_position["net_pnl"] > 0)).sum()
            correct_short = ((executors_with_position["side"] == "SELL") & (executors_with_position["net_pnl"] > 0)).sum()
            accuracy_long = correct_long / total_long if total_long > 0 else 0
            accuracy_short = correct_short / total_short if total_short > 0 else 0
            close_types = executors_df.groupby("close_type")["timestamp"].count()

            # Additional metrics
            total_positions = executors_df.shape[0]
            win_signals = executors_df.loc[(executors_df["profitable"] > 0) & (executors_df["signal"] != 0)]
            loss_signals = executors_df.loc[(executors_df["profitable"] < 0) & (executors_df["signal"] != 0)]
            accuracy = win_signals.shape[0] / total_positions
            cumulative_returns = executors_df["net_pnl_quote"].cumsum()
            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - peak)
            max_draw_down = np.min(drawdown)
            max_drawdown_pct = max_draw_down / executors_df["inventory"].iloc[0]
            returns = executors_df["net_pnl_quote"] / net_pnl
            sharpe_ratio = returns.mean() / returns.std()
            total_won = win_signals.loc[:, "net_pnl_quote"].sum()
            total_loss = - loss_signals.loc[:, "net_pnl_quote"].sum()
            profit_factor = total_won / total_loss if total_loss > 0 else 1
            duration_minutes = (executors_df.close_time.max() - executors_df.index.min()).total_seconds() / 60
            avg_trading_time_minutes = (pd.to_datetime(executors_df["close_time"]) - executors_df.index).dt.total_seconds() / 60
            avg_trading_time = avg_trading_time_minutes.mean()

            return {
                "net_pnl": net_pnl,
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
                "duration_minutes": duration_minutes,
                "avg_trading_time_minutes": avg_trading_time,
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
            "duration_minutes": 0,
            "avg_trading_time_minutes": 0,
            "win_signals": 0,
            "loss_signals": 0,
        }
