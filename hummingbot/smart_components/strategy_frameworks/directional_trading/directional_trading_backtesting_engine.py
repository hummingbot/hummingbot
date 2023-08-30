import pandas as pd

from hummingbot.smart_components.strategy_frameworks.backtesting_engine_base import BacktestingEngineBase


class DirectionalTradingBacktestingEngine(BacktestingEngineBase):
    def simulate_execution(self, df, initial_portfolio_usd, trade_cost):
        executors = []
        df["side"] = df["signal"].apply(lambda x: "BUY" if x > 0 else "SELL" if x < 0 else 0)
        for order_level in self.controller.config.order_levels:
            df = self.apply_triple_barrier_method(df,
                                                  tp=float(order_level.triple_barrier_conf.take_profit),
                                                  sl=float(order_level.triple_barrier_conf.stop_loss),
                                                  tl=int(order_level.triple_barrier_conf.time_limit),
                                                  trade_cost=trade_cost)
            for index, row in df[(df["side"] == order_level.side.name)].iterrows():
                last_close_time = self.level_executors[order_level.level_id]
                if index >= last_close_time + pd.Timedelta(seconds=order_level.cooldown_time):
                    row["order_level"] = order_level.level_id
                    row["amount"] = float(order_level.order_amount_usd)
                    row["net_pnl_quote"] = row["net_pnl"] * row["amount"]
                    executors.append(row)
                    self.level_executors[order_level.level_id] = row["close_time"]
        executors_df = pd.DataFrame(executors).sort_index()
        executors_df["inventory"] = initial_portfolio_usd + executors_df["net_pnl_quote"].cumsum().shift().fillna(0)
        return executors_df
