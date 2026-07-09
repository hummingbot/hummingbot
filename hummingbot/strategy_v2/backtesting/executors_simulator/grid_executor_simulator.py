import math
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
from pydantic import Field

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation, ExecutorSimulatorBase
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig, GridLevel
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.utils.distributions import Distributions


class GridExecutorSimulation(ExecutorSimulation):
    """ExecutorSimulation subclass that carries grid-specific fill events and level data."""
    fill_events: List[Dict] = Field(default_factory=list)
    grid_level_prices: List[float] = Field(default_factory=list)
    grid_tp_prices: List[float] = Field(default_factory=list)
    grid_side: str = "BUY"
    grid_limit_price: Optional[float] = None

    def get_custom_info(self, last_entry: pd.Series) -> dict:
        base = super().get_custom_info(last_entry)
        base["fill_events"] = self.fill_events
        base["grid_level_prices"] = self.grid_level_prices
        base["grid_tp_prices"] = self.grid_tp_prices
        base["grid_side"] = self.grid_side
        base["grid_limit_price"] = self.grid_limit_price
        return base


class GridExecutorSimulator(ExecutorSimulatorBase):

    @staticmethod
    def _generate_grid_levels(config: GridExecutorConfig, mid_price: Decimal,
                              trading_rules=None) -> List[GridLevel]:
        """Generate grid levels mirroring the real GridExecutor._generate_grid_levels logic.

        When trading_rules is provided, uses exchange-specific min_notional_size,
        min_base_amount_increment, and min_price_increment for accurate quantization.
        """
        if trading_rules is not None:
            min_notional = max(config.min_order_amount_quote, trading_rules.min_notional_size)
            min_base_increment = trading_rules.min_base_amount_increment
        else:
            min_notional = max(config.min_order_amount_quote, Decimal("5"))
            min_base_increment = None

        min_notional_with_margin = min_notional * Decimal("1.05")

        if min_base_increment is not None:
            min_base_amount = max(
                min_notional_with_margin / mid_price,
                min_base_increment * Decimal(str(math.ceil(float(min_notional) / float(min_base_increment * mid_price))))
            )
            min_base_amount = Decimal(
                str(math.ceil(float(min_base_amount) / float(min_base_increment)))) * min_base_increment
        else:
            min_base_amount = min_notional_with_margin / mid_price

        min_quote_amount = min_base_amount * mid_price

        grid_range = (config.end_price - config.start_price) / config.start_price
        if trading_rules is not None:
            min_step_size = max(
                config.min_spread_between_orders,
                trading_rules.min_price_increment / mid_price
            )
        else:
            min_step_size = config.min_spread_between_orders

        max_possible_levels = int(config.total_amount_quote / min_quote_amount)

        if max_possible_levels == 0:
            n_levels = 1
            quote_amount_per_level = min_quote_amount
        else:
            max_levels_by_step = int(grid_range / min_step_size) if min_step_size > 0 else max_possible_levels
            n_levels = min(max_possible_levels, max_levels_by_step)
            if min_base_increment is not None:
                base_amount_per_level = max(
                    min_base_amount,
                    Decimal(str(math.floor(float(config.total_amount_quote / (mid_price * n_levels)) /
                                           float(min_base_increment)))) * min_base_increment
                )
                quote_amount_per_level = base_amount_per_level * mid_price
            else:
                quote_amount_per_level = config.total_amount_quote / n_levels
                if quote_amount_per_level < min_quote_amount:
                    quote_amount_per_level = min_quote_amount
            n_levels = min(n_levels, int(float(config.total_amount_quote) / float(quote_amount_per_level)))

        n_levels = max(1, n_levels)

        if n_levels > 1:
            prices = Distributions.linear(n_levels, float(config.start_price), float(config.end_price))
            step = grid_range / (n_levels - 1)
        else:
            prices = [(config.start_price + config.end_price) / 2]
            step = grid_range

        take_profit = max(step, config.triple_barrier_config.take_profit) if config.coerce_tp_to_step else config.triple_barrier_config.take_profit

        grid_levels = []
        for i, price in enumerate(prices):
            grid_levels.append(
                GridLevel(
                    id=f"L{i}",
                    price=Decimal(str(price)),
                    amount_quote=Decimal(str(quote_amount_per_level)),
                    take_profit=take_profit,
                    side=config.side,
                    open_order_type=config.triple_barrier_config.open_order_type,
                    take_profit_order_type=config.triple_barrier_config.take_profit_order_type,
                )
            )
        return grid_levels

    def simulate(self, df: pd.DataFrame, config: GridExecutorConfig, trade_cost: float,
                 trading_rules=None) -> ExecutorSimulation:
        """
        Simulate grid execution on historical OHLCV data.

        The grid executor works as follows:
        - Grid levels are placed as limit buy (or sell) orders at specific prices.
        - When a level fills, a take-profit sell (or buy) order is placed at level.price * (1 + tp).
        - When the TP fills, the level resets and can be re-entered (level recycling).
        - Global barriers (stop loss on aggregate PnL, time limit, global TP when price exits range) can close everything.

        :param df: DataFrame with columns [timestamp, open, high, low, close] indexed by timestamp.
        :param config: GridExecutorConfig.
        :param trade_cost: Trading cost as a fraction (e.g. 0.0002 = 0.02%).
        :param trading_rules: Optional TradingRule from the exchange connector for accurate quantization.
        :return: ExecutorSimulation with per-row evolving PnL.
        """
        side_multiplier = 1 if config.side == TradeType.BUY else -1
        last_timestamp = df['timestamp'].max()
        tl = config.triple_barrier_config.time_limit if config.triple_barrier_config.time_limit else None
        tl_timestamp = config.timestamp + tl if tl else last_timestamp

        df_filtered = df[:tl_timestamp].copy()
        df_filtered['net_pnl_pct'] = 0.0
        df_filtered['net_pnl_quote'] = 0.0
        df_filtered['cum_fees_quote'] = 0.0
        df_filtered['filled_amount_quote'] = 0.0
        df_filtered['current_position_average_price'] = 0.0

        if df_filtered.empty:
            return GridExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.TIME_LIMIT)

        initial_mid_price = Decimal(str(df_filtered.iloc[0]['close']))
        grid_levels = self._generate_grid_levels(config, initial_mid_price, trading_rules)

        if not grid_levels:
            return GridExecutorSimulation(config=config, executor_simulation=df_filtered, close_type=CloseType.TIME_LIMIT)

        stop_loss = float(config.triple_barrier_config.stop_loss) if config.triple_barrier_config.stop_loss else None
        limit_price = float(config.limit_price) if config.limit_price else None
        global_close_type = CloseType.TIME_LIMIT

        # Track per-level completed round-trip trades (entry fill -> tp fill)
        # Each completed trade contributes realized PnL
        # Active (open but not yet TP-filled) levels contribute unrealized PnL

        # State per level: None = not active, or (entry_timestamp, entry_price)
        level_state = [None] * len(grid_levels)  # None means available for entry
        level_prices = [float(level.price) for level in grid_levels]
        level_amounts_quote = [float(level.amount_quote) for level in grid_levels]
        level_tp = [float(level.take_profit) for level in grid_levels]

        # Compute TP price for each level
        tp_prices = []
        for i, level in enumerate(grid_levels):
            if config.side == TradeType.BUY:
                tp_prices.append(level_prices[i] * (1 + level_tp[i]))
            else:
                tp_prices.append(level_prices[i] * (1 - level_tp[i]))

        # Per-row tracking arrays
        n_rows = len(df_filtered)
        net_pnl_quote_arr = [0.0] * n_rows
        filled_amount_quote_arr = [0.0] * n_rows
        cum_fees_quote_arr = [0.0] * n_rows
        avg_price_arr = [0.0] * n_rows

        # Fill event tracking for visualization
        fill_events = []

        # Accumulated state
        total_realized_pnl = 0.0
        total_realized_fees = 0.0
        total_realized_amount = 0.0  # sum of all round-trip filled amounts (entry side)
        active_levels_info = {}  # level_idx -> {'entry_price': float, 'amount_quote': float}

        closes = df_filtered['close'].values
        highs = df_filtered['high'].values
        lows = df_filtered['low'].values
        timestamps = df_filtered['timestamp'].values

        terminated = False
        close_row_idx = n_rows - 1

        for row_idx in range(n_rows):
            close_price = closes[row_idx]
            high_price = highs[row_idx]
            low_price = lows[row_idx]

            # --- Check global TP: price exits grid range ---
            if config.side == TradeType.BUY and close_price > float(config.end_price):
                global_close_type = CloseType.TAKE_PROFIT
                close_row_idx = row_idx
                terminated = True
            elif config.side == TradeType.SELL and close_price < float(config.start_price):
                global_close_type = CloseType.TAKE_PROFIT
                close_row_idx = row_idx
                terminated = True

            # --- Check limit price condition ---
            if not terminated and limit_price is not None:
                limit_hit = False
                if config.side == TradeType.BUY:
                    limit_hit = close_price <= limit_price
                else:
                    limit_hit = close_price >= limit_price
                if limit_hit:
                    global_close_type = CloseType.POSITION_HOLD if config.keep_position else CloseType.STOP_LOSS
                    close_row_idx = row_idx
                    terminated = True

            # --- Process TP fills first (so levels can recycle within the same bar) ---
            levels_to_deactivate = []
            for lvl_idx in list(active_levels_info.keys()):
                tp_price = tp_prices[lvl_idx]
                tp_hit = False
                if config.side == TradeType.BUY:
                    tp_hit = high_price >= tp_price
                else:
                    tp_hit = low_price <= tp_price

                if tp_hit:
                    entry_info = active_levels_info[lvl_idx]
                    entry_price = entry_info['entry_price']
                    amount_quote = entry_info['amount_quote']
                    amount_base = amount_quote / entry_price

                    # PnL from the round-trip: buy at entry_price, sell at tp_price (or vice versa)
                    pnl_per_unit = (tp_price - entry_price) * side_multiplier
                    trade_pnl = pnl_per_unit * amount_base
                    # Fees: trade_cost on entry + trade_cost on exit
                    fees = trade_cost * amount_quote * 2
                    trade_pnl -= fees

                    total_realized_pnl += trade_pnl
                    total_realized_fees += fees
                    total_realized_amount += amount_quote
                    levels_to_deactivate.append(lvl_idx)

                    fill_events.append({
                        'timestamp': float(timestamps[row_idx]),
                        'price': tp_price,
                        'side': 'tp',
                        'level_idx': lvl_idx,
                        'amount_quote': amount_quote,
                    })

            for lvl_idx in levels_to_deactivate:
                del active_levels_info[lvl_idx]
                level_state[lvl_idx] = None  # Level recycled, available for re-entry

            # --- Process entry fills for inactive levels ---
            if not terminated:
                for lvl_idx in range(len(grid_levels)):
                    if level_state[lvl_idx] is not None:
                        continue  # Already active

                    level_price = level_prices[lvl_idx]
                    entry_hit = False
                    if config.side == TradeType.BUY:
                        entry_hit = low_price <= level_price
                    else:
                        entry_hit = high_price >= level_price

                    if entry_hit:
                        level_state[lvl_idx] = row_idx
                        active_levels_info[lvl_idx] = {
                            'entry_price': level_price,
                            'amount_quote': level_amounts_quote[lvl_idx],
                        }
                        fill_events.append({
                            'timestamp': float(timestamps[row_idx]),
                            'price': level_price,
                            'side': 'entry',
                            'level_idx': lvl_idx,
                            'amount_quote': level_amounts_quote[lvl_idx],
                        })

            # --- Compute current unrealized PnL for active levels ---
            unrealized_pnl = 0.0
            active_amount_quote = 0.0
            weighted_entry_sum = 0.0
            for lvl_idx, info in active_levels_info.items():
                entry_price = info['entry_price']
                amount_quote = info['amount_quote']
                amount_base = amount_quote / entry_price
                unrealized = (close_price - entry_price) * side_multiplier * amount_base
                # Deduct estimated entry + exit fees for active positions
                unrealized -= trade_cost * amount_quote * 2
                unrealized_pnl += unrealized
                active_amount_quote += amount_quote
                weighted_entry_sum += entry_price * amount_quote

            # For POSITION_HOLD, only report realized PnL (active positions are held, not closed)
            if terminated and global_close_type == CloseType.POSITION_HOLD:
                total_pnl = total_realized_pnl
                total_amount = total_realized_amount
                total_fees = total_realized_fees
            else:
                total_pnl = total_realized_pnl + unrealized_pnl
                total_amount = total_realized_amount + active_amount_quote
                total_fees = total_realized_fees + (trade_cost * active_amount_quote * 2)

            net_pnl_quote_arr[row_idx] = total_pnl
            filled_amount_quote_arr[row_idx] = total_amount
            cum_fees_quote_arr[row_idx] = total_fees
            if total_amount > 0 and (total_realized_amount + active_amount_quote) > 0 and weighted_entry_sum > 0:
                avg_price_arr[row_idx] = weighted_entry_sum / active_amount_quote if active_amount_quote > 0 else 0.0
            else:
                avg_price_arr[row_idx] = avg_price_arr[row_idx - 1] if row_idx > 0 else 0.0

            # --- Check global stop loss on aggregate PnL ---
            if stop_loss is not None and total_amount > 0:
                pnl_pct = total_pnl / total_amount if total_amount > 0 else 0.0
                if pnl_pct <= -stop_loss:
                    global_close_type = CloseType.STOP_LOSS
                    close_row_idx = row_idx
                    terminated = True

            if terminated:
                # Fill remaining rows with the final state
                for remaining_idx in range(row_idx + 1, n_rows):
                    net_pnl_quote_arr[remaining_idx] = total_pnl
                    filled_amount_quote_arr[remaining_idx] = total_amount
                    cum_fees_quote_arr[remaining_idx] = total_fees
                    avg_price_arr[remaining_idx] = avg_price_arr[row_idx]
                break

        # Write arrays back into the dataframe
        df_filtered['net_pnl_quote'] = net_pnl_quote_arr
        df_filtered['filled_amount_quote'] = filled_amount_quote_arr
        df_filtered['cum_fees_quote'] = cum_fees_quote_arr
        df_filtered['current_position_average_price'] = avg_price_arr
        df_filtered.loc[df_filtered['filled_amount_quote'] > 0, 'net_pnl_pct'] = (
            df_filtered['net_pnl_quote'] / df_filtered['filled_amount_quote']
        )

        # Trim to close timestamp
        df_filtered = df_filtered.iloc[:close_row_idx + 1].copy()

        # Double the filled_amount_quote on the last row to signal position close (convention from other simulators)
        if not df_filtered.empty:
            df_filtered.loc[df_filtered.index[-1], 'filled_amount_quote'] = (
                df_filtered['filled_amount_quote'].iloc[-1] * 2
            )

        return GridExecutorSimulation(
            config=config,
            executor_simulation=df_filtered,
            close_type=global_close_type,
            fill_events=fill_events,
            grid_level_prices=level_prices,
            grid_tp_prices=tp_prices,
            grid_side=config.side.name,
            grid_limit_price=limit_price,
        )
