from decimal import Decimal
from typing import List

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation, ExecutorSimulatorBase
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.strategy_v2.models.executors import CloseType


class DCAExecutorSimulator(ExecutorSimulatorBase):

    @staticmethod
    def break_even_price_at_index(prices: List[Decimal], amounts: List[Decimal], index: int) -> Decimal:
        total_amount = sum(amounts[:index + 1])
        total_quote = sum([amounts[i] * prices[i] for i in range(index + 1)])
        return total_quote / total_amount

    def simulate(self, df: pd.DataFrame, config: DCAExecutorConfig, trade_cost: float) -> ExecutorSimulation:
        if config.mode == DCAMode.TAKER:
            raise NotImplementedError("Taker mode is not supported in DCAExecutorSimulator")
        potential_dca_stages = []
        side_multiplier = 1 if config.side == TradeType.BUY else -1
        last_timestamp = df['timestamp'].max()
        tl = config.time_limit if config.time_limit else None
        tl_timestamp = config.timestamp + tl if tl else last_timestamp

        # Trailing stop parameters
        trailing_sl_trigger_pct = config.trailing_stop.activation_price if config.trailing_stop else None
        trailing_sl_delta_pct = config.trailing_stop.trailing_delta if config.trailing_stop else None

        # Filter dataframe based on the conditions
        df_filtered = df[df['timestamp'] <= tl_timestamp].copy()
        df_filtered['net_pnl_pct'] = 0.0
        df_filtered['net_pnl_quote'] = 0.0
        df_filtered['cum_fees_quote'] = 0.0
        df_filtered['filled_amount_quote'] = 0.0
        df_filtered['current_position_average_price'] = float(config.prices[0])

        for i in range(len(config.prices)):
            is_last_order = i == len(config.prices) - 1
            price = config.prices[i]
            amount = config.amounts_quote[i]
            break_even_price = DCAExecutorSimulator.break_even_price_at_index(config.prices, config.amounts_quote, i) if i > 0 else price

            entry_condition = (df_filtered['close'] <= price) if config.side == TradeType.BUY else (df_filtered['close'] >= price)
            entry_timestamp = df_filtered[entry_condition]['timestamp'].min()
            if pd.isna(entry_timestamp):
                break
            returns_df = df_filtered[df_filtered['timestamp'] >= entry_timestamp]
            returns = returns_df['close'].pct_change().fillna(0)
            cumulative_returns = (((1 + returns).cumprod() - 1) * side_multiplier) - trade_cost
            take_profit_timestamp = None
            stop_loss_timestamp = None
            trailing_sl_timestamp = None
            next_order_timestamp = None

            # Trailing stop logic
            if trailing_sl_trigger_pct is not None and trailing_sl_delta_pct is not None:
                trailing_stop_activation_price = break_even_price * (1 + trailing_sl_trigger_pct * side_multiplier)
                trailing_stop_condition = None
                if config.side == TradeType.BUY:
                    ts_activated_condition = returns_df["close"] >= trailing_stop_activation_price
                    if ts_activated_condition.any():
                        returns_df.loc[ts_activated_condition, "ts_trigger_price"] = (returns_df[ts_activated_condition]["close"] * float(1 - trailing_sl_delta_pct)).cummax()
                        trailing_stop_condition = returns_df['close'] <= returns_df['ts_trigger_price']
                else:
                    ts_activated_condition = returns_df["close"] <= trailing_stop_activation_price
                    if ts_activated_condition.any():
                        returns_df.loc[ts_activated_condition, "ts_trigger_price"] = (returns_df[ts_activated_condition]["close"] * float(1 + trailing_sl_delta_pct)).cummin()
                        trailing_stop_condition = returns_df['close'] >= returns_df['ts_trigger_price']
                trailing_sl_timestamp = returns_df[trailing_stop_condition]['timestamp'].min() if trailing_stop_condition is not None else None

            if config.take_profit:
                take_profit_price = break_even_price * (1 + config.take_profit * side_multiplier)
                take_profit_condition = returns_df['close'] >= take_profit_price if config.side == TradeType.BUY else returns_df['close'] <= take_profit_price
                take_profit_timestamp = returns_df[take_profit_condition]['timestamp'].min()

            if is_last_order and config.stop_loss:
                stop_loss_price = break_even_price * (1 - config.stop_loss * side_multiplier)
                stop_loss_condition = returns_df['low'] <= stop_loss_price if config.side == TradeType.BUY else returns_df['high'] >= stop_loss_price
                stop_loss_timestamp = returns_df[stop_loss_condition]['timestamp'].min()
            else:
                next_order_condition = returns_df['close'] <= config.prices[i + 1] if config.side == TradeType.BUY else returns_df['close'] >= config.prices[i + 1]
                next_order_timestamp = returns_df[next_order_condition]['timestamp'].min()

            close_timestamp = min([timestamp for timestamp in [take_profit_timestamp, stop_loss_timestamp,
                                                               trailing_sl_timestamp, last_timestamp, next_order_timestamp] if not pd.isna(timestamp)])

            if close_timestamp == take_profit_timestamp:
                close_type = CloseType.TAKE_PROFIT
            elif close_timestamp == stop_loss_timestamp:
                close_type = CloseType.STOP_LOSS
            elif close_timestamp == trailing_sl_timestamp:
                close_type = CloseType.TRAILING_STOP
            elif close_timestamp == next_order_timestamp:
                close_type = None
            else:
                close_type = CloseType.TIME_LIMIT

            df_filtered[f'filled_amount_quote_{i}'] = 0.0
            df_filtered[f'net_pnl_quote_{i}'] = 0.0
            potential_dca_stages.append({
                'level': i,
                'entry_timestamp': entry_timestamp,
                'price': float(price),
                'amount': float(amount),
                'break_even_price': float(break_even_price),
                'close_timestamp': close_timestamp,
                'close_type': close_type,
                'cumulative_returns': cumulative_returns
            })

        if len(potential_dca_stages) == 0:
            return ExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.TIME_LIMIT)

        close_type = None

        for i, dca_stage in enumerate(potential_dca_stages):
            if dca_stage['close_type'] is None:
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], f'filled_amount_quote_{i}'] = dca_stage['amount']
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], f'net_pnl_quote_{i}'] = dca_stage['cumulative_returns'] * dca_stage['amount']
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], 'current_position_average_price'] = dca_stage['break_even_price']
            else:
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], f'filled_amount_quote_{i}'] = dca_stage['amount']
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], f'net_pnl_quote_{i}'] = dca_stage['cumulative_returns'] * dca_stage['amount']
                df_filtered.loc[df_filtered['timestamp'] >= dca_stage['entry_timestamp'], 'current_position_average_price'] = dca_stage['break_even_price']
                close_type = dca_stage['close_type']
                last_timestamp = dca_stage['close_timestamp']
                break

        df_filtered = df_filtered[df_filtered['timestamp'] <= last_timestamp].copy()
        df_filtered['filled_amount_quote'] = sum([df_filtered[f'filled_amount_quote_{i}'] for i in range(len(potential_dca_stages))])
        df_filtered['net_pnl_quote'] = sum([df_filtered[f'net_pnl_quote_{i}'] for i in range(len(potential_dca_stages))])
        df_filtered['cum_fees_quote'] = trade_cost * df_filtered['filled_amount_quote']
        df_filtered.loc[df_filtered["filled_amount_quote"] > 0, "net_pnl_pct"] = df_filtered["net_pnl_quote"] / df_filtered["filled_amount_quote"]

        if close_type is None:
            close_type = CloseType.FAILED

        # Construct and return ExecutorSimulation object
        simulation = ExecutorSimulation(
            config=config,
            executor_simulation=df_filtered,
            close_type=close_type
        )
        return simulation
