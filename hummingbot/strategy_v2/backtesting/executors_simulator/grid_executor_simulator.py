from decimal import Decimal
from typing import List

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation, ExecutorSimulatorBase
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig, GridLevel
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.utils.distributions import Distributions


class GridExecutorSimulator(ExecutorSimulatorBase):

    def _generate_grid_levels(self, config: GridExecutorConfig, mid_price: float) -> List[GridLevel]:
        """Generate grid levels based on configuration."""
        grid_levels = []
        
        # Get minimum notional and base amount increment 
        min_notional = max(
            float(config.min_order_amount_quote),
            5.0  # Assuming a minimum notional of 5 for most exchanges
        )
        min_base_increment = 1e-8  # Placeholder - in real implementation this would come from trading rules
        
        # Add safety margin to minimum notional
        min_notional_with_margin = min_notional * 1.05  # 5% margin for safety
        
        # Calculate minimum base amount that satisfies both min_notional and quantization
        min_base_amount = max(
            min_notional_with_margin / mid_price,  # Minimum from notional requirement
            min_base_increment
        )
        
        # Quantize the minimum base amount
        min_base_amount = round(min_base_amount / min_base_increment) * min_base_increment
        
        # Calculate grid range and minimum step size
        grid_range = (float(config.end_price) - float(config.start_price)) / float(config.start_price)
        min_step_size = max(
            float(config.min_spread_between_orders),
            1e-6  # Placeholder for minimum price increment
        )
        
        # Calculate maximum possible levels based on total amount
        max_possible_levels = int(float(config.total_amount_quote) / min_notional_with_margin)
        
        if max_possible_levels == 0:
            # If we can't even create one level, create a single level with minimum amount
            n_levels = 1
            quote_amount_per_level = min_notional_with_margin
        else:
            # Calculate optimal number of levels
            max_levels_by_step = int(grid_range / min_step_size)
            n_levels = min(max_possible_levels, max_levels_by_step)
            
            # Calculate quote amount per level ensuring it meets minimum after quantization
            base_amount_per_level = max(
                min_base_amount,
                (float(config.total_amount_quote) / (mid_price * n_levels)) // min_base_increment * min_base_increment
            )
            quote_amount_per_level = base_amount_per_level * mid_price
            
            # Adjust number of levels if total amount would be exceeded
            n_levels = min(n_levels, int(float(config.total_amount_quote) / float(quote_amount_per_level)))
        
        # Ensure we have at least one level
        n_levels = max(1, n_levels)
        
        # Generate price levels with even distribution
        if n_levels > 1:
            prices = Distributions.linear(n_levels, float(config.start_price), float(config.end_price))
            step = grid_range / (n_levels - 1)
        else:
            # For single level, use mid-point of range
            mid_price_val = (float(config.start_price) + float(config.end_price)) / 2
            prices = [mid_price_val]
            step = grid_range

        take_profit = max(step, float(config.triple_barrier_config.take_profit)) if config.coerce_tp_to_step else float(config.triple_barrier_config.take_profit)
        
        # Create grid levels
        for i, price in enumerate(prices):
            grid_levels.append(
                GridLevel(
                    id=f"L{i}",
                    price=Decimal(str(price)),
                    amount_quote=Decimal(str(quote_amount_per_level)),
                    take_profit=Decimal(str(take_profit)),
                    side=config.side,
                    open_order_type=config.triple_barrier_config.open_order_type,
                    take_profit_order_type=config.triple_barrier_config.take_profit_order_type,
                )
            )
        
        return grid_levels

    def simulate(self, df: pd.DataFrame, config: GridExecutorConfig, trade_cost: float) -> ExecutorSimulation:
        """
        Simulate grid execution based on market data and configuration.
        
        :param df: DataFrame containing market data with columns ['timestamp', 'open', 'high', 'low', 'close']
        :param config: GridExecutorConfig configuration
        :param trade_cost: Cost of trading as a percentage
        :return: ExecutorSimulation object containing the simulation results
        """
        # Initialize variables
        last_timestamp = df['timestamp'].max()
        tl = config.triple_barrier_config.time_limit if config.triple_barrier_config.time_limit else None
        tl_timestamp = config.timestamp + tl if tl else last_timestamp

        # Filter dataframe based on time limit
        df_filtered = df[:tl_timestamp].copy()
        
        # Initialize result columns
        df_filtered['net_pnl_pct'] = 0.0
        df_filtered['net_pnl_quote'] = 0.0
        df_filtered['cum_fees_quote'] = 0.0
        df_filtered['filled_amount_quote'] = 0.0
        df_filtered['current_position_average_price'] = 0.0
        
        # Get initial mid price
        initial_mid_price = float(df_filtered.iloc[0]['close'])
        
        # Generate grid levels based on configuration
        grid_levels = self._generate_grid_levels(config, initial_mid_price)
        
        # Track filled orders and position metrics
        filled_orders = []
        position_size_base = Decimal("0")
        position_size_quote = Decimal("0")
        position_fees_quote = Decimal("0")
        position_pnl_quote = Decimal("0")
        position_pnl_pct = Decimal("0")
        realized_pnl_quote = Decimal("0")
        realized_pnl_pct = Decimal("0")
        
        # Process each grid level
        for level in grid_levels:
            level_price = float(level.price)
            level_amount_quote = float(level.amount_quote)
            
            # Find timestamps where price hits the level
            if config.side == TradeType.BUY:
                condition = df_filtered['close'] <= level_price
            else:
                condition = df_filtered['close'] >= level_price
                
            level_timestamps = df_filtered[condition]['timestamp']
            
            if len(level_timestamps) > 0:
                # Get first timestamp when level is hit
                entry_timestamp = level_timestamps.iloc[0]
                
                # Calculate returns from entry point
                entry_price = df_filtered.loc[entry_timestamp, 'close']
                side_multiplier = 1 if config.side == TradeType.BUY else -1
                
                # Get subset of data from entry timestamp
                returns_df = df_filtered[entry_timestamp:].copy()
                returns = returns_df['close'].pct_change().fillna(0)
                cumulative_returns = (((1 + returns).cumprod() - 1) * side_multiplier) - trade_cost
                
                # Calculate take profit and stop loss conditions
                take_profit_price = level_price * (1 + float(level.take_profit)) if config.side == TradeType.BUY else level_price * (1 - float(level.take_profit))
                stop_loss_price = None
                if config.triple_barrier_config.stop_loss:
                    stop_loss_price = level_price * (1 - float(config.triple_barrier_config.stop_loss) * side_multiplier)
                
                # Check for take profit condition
                take_profit_condition = (returns_df['close'] >= take_profit_price) if config.side == TradeType.BUY else (returns_df['close'] <= take_profit_price)
                take_profit_timestamp = returns_df[take_profit_condition]['timestamp'].min() if take_profit_condition.any() else None
                
                # Check for stop loss condition
                stop_loss_timestamp = None
                if stop_loss_price:
                    stop_loss_condition = (returns_df['low'] <= stop_loss_price) if config.side == TradeType.BUY else (returns_df['high'] >= stop_loss_price)
                    stop_loss_timestamp = returns_df[stop_loss_condition]['timestamp'].min() if stop_loss_condition.any() else None
                
                # Determine exit timestamp
                exit_timestamp = None
                close_type = CloseType.TIME_LIMIT  # Default to time limit if no other conditions are met
                
                if take_profit_timestamp and (exit_timestamp is None or take_profit_timestamp < exit_timestamp):
                    exit_timestamp = take_profit_timestamp
                    close_type = CloseType.TAKE_PROFIT
                if stop_loss_timestamp and (exit_timestamp is None or stop_loss_timestamp < exit_timestamp):
                    exit_timestamp = stop_loss_timestamp
                    close_type = CloseType.STOP_LOSS
                if exit_timestamp is None:  # If neither TP nor SL triggered, check if we reached time limit
                    exit_timestamp = tl_timestamp if tl else df_filtered.index.max()
                    
                # Update metrics for this level
                if exit_timestamp:
                    returns_df_level = df_filtered[entry_timestamp:exit_timestamp].copy()
                    returns_level = returns_df_level['close'].pct_change().fillna(0)
                    cumulative_returns_level = (((1 + returns_level).cumprod() - 1) * side_multiplier) - trade_cost
                    
                    # Update position metrics
                    filled_orders.append({
                        'entry_timestamp': entry_timestamp,
                        'exit_timestamp': exit_timestamp,
                        'entry_price': entry_price,
                        'exit_price': df_filtered.loc[exit_timestamp, 'close'],
                        'amount_quote': level_amount_quote,
                        'pnl_pct': cumulative_returns_level.iloc[-1] if len(cumulative_returns_level) > 0 else 0.0,
                        'close_type': close_type
                    })
                    
                    # Update overall metrics
                    realized_pnl_quote += Decimal(str(cumulative_returns_level.iloc[-1] * level_amount_quote if len(cumulative_returns_level) > 0 else 0.0))
                    realized_pnl_pct += Decimal(str(cumulative_returns_level.iloc[-1] if len(cumulative_returns_level) > 0 else 0.0))
                    position_fees_quote += Decimal(str(trade_cost * level_amount_quote))

        # Calculate final metrics
        total_filled_amount = sum([order['amount_quote'] for order in filled_orders])
        df_filtered['filled_amount_quote'] = total_filled_amount
        df_filtered['net_pnl_quote'] = float(realized_pnl_quote)
        df_filtered['cum_fees_quote'] = float(position_fees_quote)
        df_filtered['net_pnl_pct'] = float(realized_pnl_quote) / total_filled_amount if total_filled_amount > 0 else 0.0
        
        # Determine final close type based on the last filled order
        final_close_type = CloseType.TIME_LIMIT
        if filled_orders:
            final_close_type = filled_orders[-1]['close_type']
        
        # Return the simulation results
        return ExecutorSimulation(
            config=config,
            executor_simulation=df_filtered,
            close_type=final_close_type
        )