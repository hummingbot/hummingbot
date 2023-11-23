import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.strategy_frameworks.backtesting_engine_base import BacktestingEngineBase
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase


class MarketMakingBacktestingEngine(BacktestingEngineBase):

    def __init__(self, controller: ControllerBase):
        super().__init__(controller)
        self.level_executors = {level.level_id: {
            "last_cooldown_time": pd.Timestamp.min,
            "last_order_refresh_time": pd.Timestamp.min,
        } for level in self.controller.config.order_levels}

    def simulate_execution(self, df, initial_portfolio_usd, trade_cost):
        executors = []
        for order_level in self.controller.config.order_levels:
            order_level_df = df.copy()
            order_level_df["side"] = order_level_df.apply(lambda x: 1 if order_level.side == TradeType.BUY else -1, axis=1)
            df_triple_barrier = self.apply_triple_barrier_method(order_level_df,
                                                                 tp=float(order_level.triple_barrier_conf.take_profit),
                                                                 sl=float(order_level.triple_barrier_conf.stop_loss),
                                                                 tl=int(order_level.triple_barrier_conf.time_limit),
                                                                 trade_cost=trade_cost)
            order_level_df["target"] = order_level_df["spread_multiplier"]
            # Here we are applying the triple barrier method to evaluate if at some point if we place an order will be
            # executed or not. We are going to loop over the executed orders and then index the real output with the
            # previous dataframe to get the real pnl.
            df_order_executed_limit = self.apply_triple_barrier_method(order_level_df.copy(),
                                                                       tp=None,
                                                                       sl=float(order_level.spread_factor),
                                                                       tl=int(order_level.order_refresh_time))

            for index, row in df_order_executed_limit.iterrows():
                orders_info = self.level_executors[order_level.level_id]
                cooldown_condition = index >= orders_info["last_cooldown_time"] + pd.Timedelta(seconds=order_level.cooldown_time)
                order_refresh_condition = index >= orders_info["last_order_refresh_time"] + pd.Timedelta(seconds=order_level.order_refresh_time)
                if order_refresh_condition and cooldown_condition:
                    if row["close_type"] == "sl":
                        triple_barrier_row = df_triple_barrier.loc[row["close_time"]]
                        triple_barrier_row["order_level"] = order_level.level_id
                        triple_barrier_row["amount"] = float(order_level.order_amount_usd)
                        triple_barrier_row["net_pnl_quote"] = triple_barrier_row["net_pnl"] * triple_barrier_row["amount"]
                        executors.append(triple_barrier_row)
                        self.level_executors[order_level.level_id]["last_cooldown_time"] = triple_barrier_row["close_time"]
                    elif row["close_type"] == "tl":
                        self.level_executors[order_level.level_id]["last_order_refresh_time"] = row["close_time"]
        executors_df = pd.DataFrame(executors).sort_index()
        executors_df["inventory"] = initial_portfolio_usd
        if len(executors_df) > 0:
            executors_df["inventory"] = initial_portfolio_usd + executors_df["net_pnl_quote"].cumsum().shift().fillna(0)
        return executors_df
