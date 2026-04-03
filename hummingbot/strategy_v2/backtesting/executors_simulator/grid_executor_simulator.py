from decimal import Decimal
from typing import List, Dict, Any

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

    def simulate(self, market_data: List[Dict[str, Any]], config: GridExecutorConfig, trade_cost: float) -> ExecutorSimulation:
        """
        Simulate grid execution based on market data and configuration.
        
        :param market_data: List of market data dictionaries with keys ['timestamp', 'open', 'high', 'low', 'close']
        :param config: GridExecutorConfig configuration
        :param trade_cost: Cost of trading as a percentage
        :return: ExecutorSimulation object containing the simulation results
        """
        # Sort market data by timestamp to ensure chronological order
        sorted_market_data = sorted(market_data, key=lambda x: x['timestamp'])
        
        # Initialize variables
        last_timestamp = sorted_market_data[-1]['timestamp']
        tl = config.triple_barrier_config.time_limit if config.triple_barrier_config.time_limit else None
        tl_timestamp = config.timestamp + tl if tl else last_timestamp

        # Filter market data based on time limit
        df_filtered = [row for row in sorted_market_data if row['timestamp'] <= tl_timestamp]
        
        # Get initial mid price
        initial_mid_price = float(df_filtered[0]['close'])
        
        # Generate grid levels based on configuration
        grid_levels = self._generate_grid_levels(config, initial_mid_price)
        
        # Track filled orders and position metrics
        filled_orders = []
        realized_pnl_quote = Decimal("0")
        position_fees_quote = Decimal("0")
        
        # Process each grid level
        for level in grid_levels:
            level_price = float(level.price)
            level_amount_quote = float(level.amount_quote)
            
            # Find timestamps where price hits the level
            level_timestamps = []
            for row in df_filtered:
                if config.side == TradeType.BUY:
                    if row['close'] <= level_price:
                        level_timestamps.append(row['timestamp'])
                else:
                    if row['close'] >= level_price:
                        level_timestamps.append(row['timestamp'])
            
            if len(level_timestamps) > 0:
                # Get first timestamp when level is hit
                entry_timestamp = level_timestamps[0]
                
                # Find entry price
                entry_price = None
                for row in df_filtered:
                    if row['timestamp'] == entry_timestamp:
                        entry_price = row['close']
                        break
                
                side_multiplier = 1 if config.side == TradeType.BUY else -1
                
                # Get subset of data from entry timestamp
                returns_data = [row for row in df_filtered if row['timestamp'] >= entry_timestamp]
                
                # Calculate returns manually (equivalent to pct_change())
                returns = []
                for i in range(1, len(returns_data)):
                    prev_close = returns_data[i-1]['close']
                    curr_close = returns_data[i]['close']
                    if prev_close != 0:
                        returns.append((curr_close - prev_close) / prev_close)
                    else:
                        returns.append(0.0)
                
                # Calculate cumulative returns manually (equivalent to cumprod())
                cumulative_returns = []
                cumulative_product = 1.0
                for ret in returns:
                    cumulative_product *= (1 + ret)
                    cumulative_returns.append(((cumulative_product - 1) * side_multiplier) - trade_cost)
                
                # Calculate take profit and stop loss conditions
                take_profit_price = level_price * (1 + float(level.take_profit)) if config.side == TradeType.BUY else level_price * (1 - float(level.take_profit))
                stop_loss_price = None
                if config.triple_barrier_config.stop_loss:
                    stop_loss_price = level_price * (1 - float(config.triple_barrier_config.stop_loss) * side_multiplier)
                
                # Find take profit and stop loss timestamps
                take_profit_timestamp = None
                stop_loss_timestamp = None
                
                for row in returns_data:
                    # Check for take profit condition
                    if config.side == TradeType.BUY:
                        if row['close'] >= take_profit_price and take_profit_timestamp is None:
                            take_profit_timestamp = row['timestamp']
                        # Check for stop loss condition
                        if stop_loss_price is not None and row['low'] <= stop_loss_price and stop_loss_timestamp is None:
                            stop_loss_timestamp = row['timestamp']
                    else:
                        if row['close'] <= take_profit_price and take_profit_timestamp is None:
                            take_profit_timestamp = row['timestamp']
                        # Check for stop loss condition
                        if stop_loss_price is not None and row['high'] >= stop_loss_price and stop_loss_timestamp is None:
                            stop_loss_timestamp = row['timestamp']
                
                # Determine exit timestamp
                exit_timestamp = None
                close_type = CloseType.TIME_LIMIT  # Default to time limit if no other conditions are met
                
                if take_profit_timestamp is not None and (exit_timestamp is None or take_profit_timestamp < exit_timestamp):
                    exit_timestamp = take_profit_timestamp
                    close_type = CloseType.TAKE_PROFIT
                if stop_loss_timestamp is not None and (exit_timestamp is None or stop_loss_timestamp < exit_timestamp):
                    exit_timestamp = stop_loss_timestamp
                    close_type = CloseType.STOP_LOSS
                if exit_timestamp is None:  # If neither TP nor SL triggered, check if we reached time limit
                    exit_timestamp = tl_timestamp if tl else sorted_market_data[-1]['timestamp']
                    
                # Update metrics for this level
                if exit_timestamp:
                    # Calculate returns from entry to exit
                    returns_df_level = [row for row in df_filtered if entry_timestamp <= row['timestamp'] <= exit_timestamp]
                    returns_level = []
                    for i in range(1, len(returns_df_level)):
                        prev_close = returns_df_level[i-1]['close']
                        curr_close = returns_df_level[i]['close']
                        if prev_close != 0:
                            returns_level.append((curr_close - prev_close) / prev_close)
                        else:
                            returns_level.append(0.0)
                    
                    # Calculate cumulative returns for this level
                    cumulative_returns_level = 0.0
                    if len(returns_level) > 0:
                        cumulative_product = 1.0
                        for ret in returns_level:
                            cumulative_product *= (1 + ret)
                        cumulative_returns_level = ((cumulative_product - 1) * side_multiplier) - trade_cost
                    
                    # Find exit price
                    exit_price = None
                    for row in df_filtered:
                        if row['timestamp'] == exit_timestamp:
                            exit_price = row['close']
                            break
                    
                    # Update position metrics
                    filled_orders.append({
                        'entry_timestamp': entry_timestamp,
                        'exit_timestamp': exit_timestamp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'amount_quote': level_amount_quote,
                        'pnl_pct': cumulative_returns_level,
                        'close_type': close_type
                    })
                    
                    # Update overall metrics
                    realized_pnl_quote += Decimal(str(cumulative_returns_level * level_amount_quote))
                    position_fees_quote += Decimal(str(trade_cost * level_amount_quote))

        # Calculate final metrics
        total_filled_amount = sum([order['amount_quote'] for order in filled_orders])
        net_pnl_quote = float(realized_pnl_quote)
        net_pnl_pct = float(realized_pnl_quote) / total_filled_amount if total_filled_amount > 0 else 0.0
        cum_fees_quote = float(position_fees_quote)
        
        # Create result data structure
        result_data = []
        for row in df_filtered:
            result_row = row.copy()
            result_row['net_pnl_pct'] = net_pnl_pct
            result_row['net_pnl_quote'] = net_pnl_quote
            result_row['cum_fees_quote'] = cum_fees_quote
            result_row['filled_amount_quote'] = total_filled_amount
            result_row['current_position_average_price'] = 0.0  # Placeholder
            result_data.append(result_row)
        
        # Determine final close type based on the last filled order
        final_close_type = CloseType.TIME_LIMIT
        if filled_orders:
            final_close_type = filled_orders[-1]['close_type']
        
        # Return the simulation results
        return ExecutorSimulation(
            config=config,
            executor_simulation=result_data,  # Using list of dicts instead of DataFrame
            close_type=final_close_type
        )