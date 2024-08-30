from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation, ExecutorSimulatorBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.executors import CloseType


class PositionExecutorSimulator(ExecutorSimulatorBase):
    def simulate(self, df: pd.DataFrame, config: PositionExecutorConfig, trade_cost: float) -> ExecutorSimulation:
        if config.triple_barrier_config.open_order_type == OrderType.LIMIT:
            entry_condition = (df['close'] < config.entry_price) if config.side == TradeType.BUY else (df['close'] > config.entry_price)
            start_timestamp = df[entry_condition]['timestamp'].min()
        else:
            start_timestamp = df['timestamp'].min()
        last_timestamp = df['timestamp'].max()

        # Set up barriers
        tp = Decimal(config.triple_barrier_config.take_profit) if config.triple_barrier_config.take_profit else None
        trailing_sl_trigger_pct = None
        trailing_sl_delta_pct = None
        if config.triple_barrier_config.trailing_stop:
            trailing_sl_trigger_pct = config.triple_barrier_config.trailing_stop.activation_price
            trailing_sl_delta_pct = config.triple_barrier_config.trailing_stop.trailing_delta
        tl = config.triple_barrier_config.time_limit if config.triple_barrier_config.time_limit else None
        tl_timestamp = config.timestamp + tl if tl else last_timestamp

        # Filter dataframe based on the conditions
        df_filtered = df[df['timestamp'] <= tl_timestamp].copy()
        df_filtered['net_pnl_pct'] = 0.0
        df_filtered['net_pnl_quote'] = 0.0
        df_filtered['cum_fees_quote'] = 0.0
        df_filtered['filled_amount_quote'] = 0.0
        df_filtered["current_position_average_price"] = float(config.entry_price)

        if pd.isna(start_timestamp):
            return ExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.TIME_LIMIT)

        entry_price = df.loc[df['timestamp'] == start_timestamp, 'close'].values[0]
        side_multiplier = 1 if config.side == TradeType.BUY else -1

        returns_df = df_filtered[df_filtered['timestamp'] >= start_timestamp]
        returns = returns_df['close'].pct_change().fillna(0)
        cumulative_returns = (((1 + returns).cumprod() - 1) * side_multiplier) - trade_cost
        df_filtered.loc[df_filtered['timestamp'] >= start_timestamp, 'net_pnl_pct'] = cumulative_returns
        df_filtered.loc[df_filtered['timestamp'] >= start_timestamp, 'filled_amount_quote'] = float(config.amount) * entry_price
        df_filtered['net_pnl_quote'] = df_filtered['net_pnl_pct'] * df_filtered['filled_amount_quote']
        df_filtered['cum_fees_quote'] = trade_cost * df_filtered['filled_amount_quote']

        # Make sure the trailing stop pct rises linearly to the net p/l pct when above the trailing stop trigger pct (if any)
        if trailing_sl_trigger_pct is not None and trailing_sl_delta_pct is not None:
            df_filtered.loc[(df_filtered['net_pnl_pct'] > trailing_sl_trigger_pct).cummax(), 'ts'] = (
                df_filtered['net_pnl_pct'] - float(trailing_sl_delta_pct)
            ).cummax()

        # Determine the earliest close event
        first_tp_timestamp = df_filtered[df_filtered['net_pnl_pct'] > tp]['timestamp'].min() if tp else None
        if config.triple_barrier_config.stop_loss:
            sl = Decimal(config.triple_barrier_config.stop_loss)
            sl_price = entry_price * (1 - sl * side_multiplier)
            sl_condition = df_filtered['low'] <= sl_price if config.side == TradeType.BUY else df_filtered['high'] >= sl_price
        first_sl_timestamp = df_filtered[sl_condition]['timestamp'].min() if sl else None
        first_trailing_sl_timestamp = df_filtered[(~df_filtered['ts'].isna()) & (df_filtered['net_pnl_pct'] < df_filtered['ts'])]['timestamp'].min() if trailing_sl_delta_pct and trailing_sl_trigger_pct else None
        close_timestamp = min([timestamp for timestamp in [first_tp_timestamp, first_sl_timestamp, tl_timestamp, first_trailing_sl_timestamp] if not pd.isna(timestamp)])

        # Determine the close type
        if close_timestamp == first_tp_timestamp:
            close_type = CloseType.TAKE_PROFIT
        elif close_timestamp == first_sl_timestamp:
            close_type = CloseType.STOP_LOSS
        elif close_timestamp == first_trailing_sl_timestamp:
            close_type = CloseType.TRAILING_STOP
        else:
            close_type = CloseType.TIME_LIMIT

        # Set the final state of the DataFrame
        df_filtered = df_filtered[df_filtered['timestamp'] <= close_timestamp]

        # Construct and return ExecutorSimulation object
        simulation = ExecutorSimulation(
            config=config,
            executor_simulation=df_filtered,
            close_type=close_type
        )
        return simulation
