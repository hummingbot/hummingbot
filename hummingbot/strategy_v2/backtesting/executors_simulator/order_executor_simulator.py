import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation, ExecutorSimulatorBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executors import CloseType


class OrderExecutorSimulator(ExecutorSimulatorBase):
    def simulate(self, df: pd.DataFrame, config: OrderExecutorConfig, trade_cost: float) -> ExecutorSimulation:
        df_filtered = df.copy()
        df_filtered['net_pnl_pct'] = 0.0
        df_filtered['net_pnl_quote'] = 0.0
        df_filtered['cum_fees_quote'] = 0.0
        df_filtered['filled_amount_quote'] = 0.0
        df_filtered['current_position_average_price'] = 0.0

        if df_filtered.empty:
            return ExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.FAILED)

        # Determine fill timestamp based on execution strategy
        if config.execution_strategy == ExecutionStrategy.MARKET:
            # Market orders fill immediately at first candle
            fill_timestamp = df_filtered['timestamp'].iloc[0]
        elif config.execution_strategy == ExecutionStrategy.LIMIT_CHASER:
            # Limit chaser chases the market price, effectively fills at first candle
            fill_timestamp = df_filtered['timestamp'].iloc[0]
        elif config.execution_strategy == ExecutionStrategy.LIMIT_MAKER:
            # Limit maker: best of configured price or current market price
            first_close = df_filtered['close'].iloc[0]
            if config.side == TradeType.BUY:
                effective_price = min(float(config.price), first_close)
                entry_condition = df_filtered['close'] <= effective_price
            else:
                effective_price = max(float(config.price), first_close)
                entry_condition = df_filtered['close'] >= effective_price
            fill_timestamp = df_filtered[entry_condition]['timestamp'].min()
        else:
            # LIMIT order: fill when price reaches the limit price
            if config.side == TradeType.BUY:
                entry_condition = df_filtered['close'] <= float(config.price)
            else:
                entry_condition = df_filtered['close'] >= float(config.price)
            fill_timestamp = df_filtered[entry_condition]['timestamp'].min()

        if pd.isna(fill_timestamp):
            # A maker/limit order whose price the market never crossed within the window
            # is a RESTING order, not a failure. Keep it active (zero fill) over the whole
            # window so the controller's own refresh/cancel logic governs its lifetime; if it
            # is never cancelled it simply expires unfilled at the end. Returning FAILED here
            # dropped the order, so controllers that gate re-quoting on "is a level already
            # resting?" re-quoted every tick, flooding the sim with phantom fills.
            return ExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.EXPIRED)

        # Determine entry price
        entry_price = df_filtered.loc[fill_timestamp, 'close']

        # Once filled, the order executor holds the position with no PnL tracking
        amount_quote = float(config.amount) * entry_price
        df_filtered.loc[fill_timestamp:, 'filled_amount_quote'] = amount_quote
        df_filtered.loc[fill_timestamp:, 'current_position_average_price'] = entry_price
        df_filtered.loc[fill_timestamp:, 'cum_fees_quote'] = trade_cost * amount_quote

        # Trim to fill timestamp - the executor stops immediately after fill
        df_filtered = df_filtered[:fill_timestamp]

        return ExecutorSimulation(
            config=config,
            executor_simulation=df_filtered,
            close_type=CloseType.POSITION_HOLD
        )
