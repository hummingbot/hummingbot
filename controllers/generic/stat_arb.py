from decimal import Decimal
from typing import List

import numpy as np
from sklearn.linear_model import LinearRegression

from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair, PositionSummary
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction


class StatArbConfig(ControllerConfigBase):
    """
    Configuration for a statistical arbitrage controller that trades two cointegrated assets.
    """
    controller_type: str = "generic"
    controller_name: str = "stat_arb"
    candles_config: List[CandlesConfig] = []
    connector_pair_dominant: ConnectorPair = ConnectorPair(connector_name="binance_perpetual", trading_pair="SOL-USDT")
    connector_pair_hedge: ConnectorPair = ConnectorPair(connector_name="binance_perpetual", trading_pair="POPCAT-USDT")
    interval: str = "1m"
    lookback_period: int = 300
    entry_threshold: Decimal = Decimal("2.0")
    take_profit: Decimal = Decimal("0.0008")
    tp_global: Decimal = Decimal("0.01")
    sl_global: Decimal = Decimal("0.05")
    min_amount_quote: Decimal = Decimal("10")
    quoter_spread: Decimal = Decimal("0.0001")
    quoter_cooldown: int = 30
    quoter_refresh: int = 10
    max_orders_placed_per_side: int = 2
    max_orders_filled_per_side: int = 2
    max_position_deviation: Decimal = Decimal("0.1")
    pos_hedge_ratio: Decimal = Decimal("1.0")
    leverage: int = 20
    position_mode: PositionMode = PositionMode.HEDGE

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            take_profit=self.take_profit,
            open_order_type=OrderType.LIMIT_MAKER,
            take_profit_order_type=OrderType.LIMIT_MAKER,
        )

    def update_markets(self, markets: dict) -> dict:
        """Update markets dictionary with both trading pairs"""
        # Add dominant pair
        if self.connector_pair_dominant.connector_name not in markets:
            markets[self.connector_pair_dominant.connector_name] = set()
        markets[self.connector_pair_dominant.connector_name].add(self.connector_pair_dominant.trading_pair)

        # Add hedge pair
        if self.connector_pair_hedge.connector_name not in markets:
            markets[self.connector_pair_hedge.connector_name] = set()
        markets[self.connector_pair_hedge.connector_name].add(self.connector_pair_hedge.trading_pair)

        return markets


class StatArb(ControllerBase):
    """
    Statistical arbitrage controller that trades two cointegrated assets.
    """

    def __init__(self, config: StatArbConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.theoretical_dominant_quote = self.config.total_amount_quote * (1 / (1 + self.config.pos_hedge_ratio))
        self.theoretical_hedge_quote = self.config.total_amount_quote * (self.config.pos_hedge_ratio / (1 + self.config.pos_hedge_ratio))

        # Initialize processed data dictionary
        self.processed_data = {
            "dominant_price": None,
            "hedge_price": None,
            "spread": None,
            "z_score": None,
            "hedge_ratio": None,
            "position_dominant": Decimal("0"),
            "position_hedge": Decimal("0"),
            "active_orders_dominant": [],
            "active_orders_hedge": [],
            "pair_pnl": Decimal("0"),
            "signal": 0  # 0: no signal, 1: long dominant/short hedge, -1: short dominant/long hedge
        }

        # Setup candles config if not already set
        if len(self.config.candles_config) == 0:
            max_records = self.config.lookback_period + 20  # extra records for safety
            self.max_records = max_records
            self.config.candles_config = [
                CandlesConfig(
                    connector=self.config.connector_pair_dominant.connector_name,
                    trading_pair=self.config.connector_pair_dominant.trading_pair,
                    interval=self.config.interval,
                    max_records=max_records
                ),
                CandlesConfig(
                    connector=self.config.connector_pair_hedge.connector_name,
                    trading_pair=self.config.connector_pair_hedge.trading_pair,
                    interval=self.config.interval,
                    max_records=max_records
                )
            ]
        if "_perpetual" in self.config.connector_pair_dominant.connector_name:
            connector = self.market_data_provider.get_connector(self.config.connector_pair_dominant.connector_name)
            connector.set_position_mode(self.config.position_mode)
            connector.set_leverage(self.config.connector_pair_dominant.trading_pair, self.config.leverage)
        if "_perpetual" in self.config.connector_pair_hedge.connector_name:
            connector = self.market_data_provider.get_connector(self.config.connector_pair_hedge.connector_name)
            connector.set_position_mode(self.config.position_mode)
            connector.set_leverage(self.config.connector_pair_hedge.trading_pair, self.config.leverage)

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        The execution logic for the statistical arbitrage strategy.
        Market Data Conditions: Signal is generated based on the z-score of the spread between the two assets.
                                If signal == 1 --> long dominant/short hedge
                                If signal == -1 --> short dominant/long hedge
        Execution Conditions: If the signal is generated add position executors to quote from the dominant and hedge markets.
                              We compare the current position with the theoretical position for the dominant and hedge assets.
                              If the current position + the active placed amount is greater than the theoretical position, can't place more orders.
                              If the imbalance scaled pct is greater than the threshold, we avoid placing orders in the market passed on filtered_connector_pair.
                              If the pnl of total position is greater than the take profit or lower than the stop loss, we close the position.
        """
        actions: List[ExecutorAction] = []
        # Check global take profit and stop loss
        if self.processed_data["pair_pnl_pct"] > self.config.tp_global or self.processed_data["pair_pnl_pct"] < -self.config.sl_global:
            # Close all positions
            for position in self.positions_held:
                actions.extend(self.get_executors_to_reduce_position(position))
            return actions
        # Check the signal
        elif self.processed_data["signal"] != 0:
            actions.extend(self.get_executors_to_quote())
            actions.extend(self.get_executors_to_reduce_position_on_opposite_signal())

        # Get the executors to keep position after a cooldown is reached
        actions.extend(self.get_executors_to_keep_position())
        actions.extend(self.get_executors_to_refresh())

        return actions

    def get_executors_to_reduce_position_on_opposite_signal(self) -> List[ExecutorAction]:
        if self.processed_data["signal"] == 1:
            dominant_side, hedge_side = TradeType.SELL, TradeType.BUY
        elif self.processed_data["signal"] == -1:
            dominant_side, hedge_side = TradeType.BUY, TradeType.SELL
        else:
            return []
        # Get executors to stop
        dominant_active_executors_to_stop = self.filter_executors(self.executors_info, filter_func=lambda e: e.connector_name == self.config.connector_pair_dominant.connector_name and e.trading_pair == self.config.connector_pair_dominant.trading_pair and e.side == dominant_side)
        hedge_active_executors_to_stop = self.filter_executors(self.executors_info, filter_func=lambda e: e.connector_name == self.config.connector_pair_hedge.connector_name and e.trading_pair == self.config.connector_pair_hedge.trading_pair and e.side == hedge_side)
        stop_actions = [StopExecutorAction(controller_id=self.config.id, executor_id=executor.id, keep_position=False) for executor in dominant_active_executors_to_stop + hedge_active_executors_to_stop]

        # Get order executors to reduce positions
        reduce_actions: List[ExecutorAction] = []
        for position in self.positions_held:
            if position.connector_name == self.config.connector_pair_dominant.connector_name and position.trading_pair == self.config.connector_pair_dominant.trading_pair and position.side == dominant_side:
                reduce_actions.extend(self.get_executors_to_reduce_position(position))
            elif position.connector_name == self.config.connector_pair_hedge.connector_name and position.trading_pair == self.config.connector_pair_hedge.trading_pair and position.side == hedge_side:
                reduce_actions.extend(self.get_executors_to_reduce_position(position))
        return stop_actions + reduce_actions

    def get_executors_to_keep_position(self) -> List[ExecutorAction]:
        stop_actions: List[ExecutorAction] = []
        for executor in self.processed_data["executors_dominant_filled"] + self.processed_data["executors_hedge_filled"]:
            if self.market_data_provider.time() - executor.timestamp >= self.config.quoter_cooldown:
                # Create a new executor to keep the position
                stop_actions.append(StopExecutorAction(controller_id=self.config.id, executor_id=executor.id, keep_position=True))
        return stop_actions

    def get_executors_to_refresh(self) -> List[ExecutorAction]:
        refresh_actions: List[ExecutorAction] = []
        for executor in self.processed_data["executors_dominant_placed"] + self.processed_data["executors_hedge_placed"]:
            if self.market_data_provider.time() - executor.timestamp >= self.config.quoter_refresh:
                # Create a new executor to refresh the position
                refresh_actions.append(StopExecutorAction(controller_id=self.config.id, executor_id=executor.id, keep_position=False))
        return refresh_actions

    def get_executors_to_quote(self) -> List[ExecutorAction]:
        """
        Get Order Executor to quote from the dominant and hedge markets.
        """
        actions: List[ExecutorAction] = []
        trade_type_dominant = TradeType.BUY if self.processed_data["signal"] == 1 else TradeType.SELL
        trade_type_hedge = TradeType.SELL if self.processed_data["signal"] == 1 else TradeType.BUY

        # Analyze dominant active orders, max deviation and imbalance to create a new executor
        if self.processed_data["dominant_gap"] > Decimal("0") and \
           self.processed_data["filter_connector_pair"] != self.config.connector_pair_dominant and \
           len(self.processed_data["executors_dominant_placed"]) < self.config.max_orders_placed_per_side and \
           len(self.processed_data["executors_dominant_filled"]) < self.config.max_orders_filled_per_side:
            # Create Position Executor for dominant asset
            if trade_type_dominant == TradeType.BUY:
                price = self.processed_data["min_price_dominant"] * (1 - self.config.quoter_spread)
            else:
                price = self.processed_data["max_price_dominant"] * (1 + self.config.quoter_spread)
            dominant_executor_config = PositionExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_pair_dominant.connector_name,
                trading_pair=self.config.connector_pair_dominant.trading_pair,
                side=trade_type_dominant,
                entry_price=price,
                amount=self.config.min_amount_quote / self.processed_data["dominant_price"],
                triple_barrier_config=self.config.triple_barrier_config,
                leverage=self.config.leverage,
            )
            actions.append(CreateExecutorAction(controller_id=self.config.id, executor_config=dominant_executor_config))

        # Analyze hedge active orders, max deviation and imbalance to create a new executor
        if self.processed_data["hedge_gap"] > Decimal("0") and \
           self.processed_data["filter_connector_pair"] != self.config.connector_pair_hedge and \
           len(self.processed_data["executors_hedge_placed"]) < self.config.max_orders_placed_per_side and \
           len(self.processed_data["executors_hedge_filled"]) < self.config.max_orders_filled_per_side:
            # Create Position Executor for hedge asset
            if trade_type_hedge == TradeType.BUY:
                price = self.processed_data["min_price_hedge"] * (1 - self.config.quoter_spread)
            else:
                price = self.processed_data["max_price_hedge"] * (1 + self.config.quoter_spread)
            hedge_executor_config = PositionExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_pair_hedge.connector_name,
                trading_pair=self.config.connector_pair_hedge.trading_pair,
                side=trade_type_hedge,
                entry_price=price,
                amount=self.config.min_amount_quote / self.processed_data["hedge_price"],
                triple_barrier_config=self.config.triple_barrier_config,
                leverage=self.config.leverage,
            )
            actions.append(CreateExecutorAction(controller_id=self.config.id, executor_config=hedge_executor_config))
        return actions

    def get_executors_to_reduce_position(self, position: PositionSummary) -> List[ExecutorAction]:
        """
        Get Order Executor to reduce position.
        """
        if position.amount > Decimal("0"):
            # Close position
            config = OrderExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=position.connector_name,
                trading_pair=position.trading_pair,
                side=TradeType.BUY if position.side == TradeType.SELL else TradeType.SELL,
                amount=position.amount,
                position_action=PositionAction.CLOSE,
                execution_strategy=ExecutionStrategy.MARKET,
                leverage=self.config.leverage,
            )
            return [CreateExecutorAction(controller_id=self.config.id, executor_config=config)]
        return []

    async def update_processed_data(self):
        """
        Update processed data with the latest market information and statistical calculations
        needed for the statistical arbitrage strategy.
        """
        # Stat arb analysis
        spread, z_score = self.get_spread_and_z_score()

        # Generate trading signal based on z-score
        entry_threshold = float(self.config.entry_threshold)
        if z_score > entry_threshold:
            # Spread is too high, expect it to revert: long dominant, short hedge
            signal = 1
            dominant_side, hedge_side = TradeType.BUY, TradeType.SELL
        elif z_score < -entry_threshold:
            # Spread is too low, expect it to revert: short dominant, long hedge
            signal = -1
            dominant_side, hedge_side = TradeType.SELL, TradeType.BUY
        else:
            # No signal
            signal = 0
            dominant_side, hedge_side = None, None

        # Current prices
        dominant_price, hedge_price = self.get_pairs_prices()

        # Get current positions stats by signal
        positions_dominant = next((position for position in self.positions_held if position.connector_name == self.config.connector_pair_dominant.connector_name and position.trading_pair == self.config.connector_pair_dominant.trading_pair and (position.side == dominant_side or dominant_side is None)), None)
        positions_hedge = next((position for position in self.positions_held if position.connector_name == self.config.connector_pair_hedge.connector_name and position.trading_pair == self.config.connector_pair_hedge.trading_pair and (position.side == hedge_side or hedge_side is None)), None)
        # Get position stats
        position_dominant_quote = positions_dominant.amount_quote if positions_dominant else Decimal("0")
        position_hedge_quote = positions_hedge.amount_quote if positions_hedge else Decimal("0")
        position_dominant_pnl_quote = positions_dominant.global_pnl_quote if positions_dominant else Decimal("0")
        position_hedge_pnl_quote = positions_hedge.global_pnl_quote if positions_hedge else Decimal("0")
        pair_pnl_pct = (position_dominant_pnl_quote + position_hedge_pnl_quote) / (position_dominant_quote + position_hedge_quote) if (position_dominant_quote + position_hedge_quote) != 0 else Decimal("0")
        # Get active executors
        executors_dominant_placed, executors_dominant_filled = self.get_executors_dominant()
        executors_hedge_placed, executors_hedge_filled = self.get_executors_hedge()
        min_price_dominant = Decimal(str(min([executor.config.entry_price for executor in executors_dominant_placed]))) if executors_dominant_placed else None
        max_price_dominant = Decimal(str(max([executor.config.entry_price for executor in executors_dominant_placed]))) if executors_dominant_placed else None
        min_price_hedge = Decimal(str(min([executor.config.entry_price for executor in executors_hedge_placed]))) if executors_hedge_placed else None
        max_price_hedge = Decimal(str(max([executor.config.entry_price for executor in executors_hedge_placed]))) if executors_hedge_placed else None

        active_amount_dominant = Decimal(str(sum([executor.filled_amount_quote for executor in executors_dominant_filled])))
        active_amount_hedge = Decimal(str(sum([executor.filled_amount_quote for executor in executors_hedge_filled])))

        # Compute imbalance based on the hedge ratio
        dominant_gap = self.theoretical_dominant_quote - position_dominant_quote - active_amount_dominant
        hedge_gap = self.theoretical_hedge_quote - position_hedge_quote - active_amount_hedge
        imbalance = position_dominant_quote - position_hedge_quote
        imbalance_scaled = position_dominant_quote - position_hedge_quote * self.config.pos_hedge_ratio
        imbalance_scaled_pct = imbalance_scaled / position_dominant_quote if position_dominant_quote != Decimal("0") else Decimal("0")
        filter_connector_pair = None
        if imbalance_scaled_pct > self.config.max_position_deviation:
            # Avoid placing orders in the dominant market
            filter_connector_pair = self.config.connector_pair_dominant
        elif imbalance_scaled_pct < -self.config.max_position_deviation:
            # Avoid placing orders in the hedge market
            filter_connector_pair = self.config.connector_pair_hedge

        # Update processed data
        self.processed_data.update({
            "dominant_price": Decimal(str(dominant_price)),
            "hedge_price": Decimal(str(hedge_price)),
            "spread": Decimal(str(spread)),
            "z_score": Decimal(str(z_score)),
            "dominant_gap": Decimal(str(dominant_gap)),
            "hedge_gap": Decimal(str(hedge_gap)),
            "position_dominant_quote": position_dominant_quote,
            "position_hedge_quote": position_hedge_quote,
            "active_amount_dominant": active_amount_dominant,
            "active_amount_hedge": active_amount_hedge,
            "signal": signal,
            # Store full dataframes for reference
            "imbalance": Decimal(str(imbalance)),
            "imbalance_scaled_pct": Decimal(str(imbalance_scaled_pct)),
            "filter_connector_pair": filter_connector_pair,
            "min_price_dominant": min_price_dominant if min_price_dominant is not None else Decimal(str(dominant_price)),
            "max_price_dominant": max_price_dominant if max_price_dominant is not None else Decimal(str(dominant_price)),
            "min_price_hedge": min_price_hedge if min_price_hedge is not None else Decimal(str(hedge_price)),
            "max_price_hedge": max_price_hedge if max_price_hedge is not None else Decimal(str(hedge_price)),
            "executors_dominant_filled": executors_dominant_filled,
            "executors_hedge_filled": executors_hedge_filled,
            "executors_dominant_placed": executors_dominant_placed,
            "executors_hedge_placed": executors_hedge_placed,
            "pair_pnl_pct": pair_pnl_pct,
        })

    def get_spread_and_z_score(self):
        # Fetch candle data for both assets
        dominant_df = self.market_data_provider.get_candles_df(
            connector_name=self.config.connector_pair_dominant.connector_name,
            trading_pair=self.config.connector_pair_dominant.trading_pair,
            interval=self.config.interval,
            max_records=self.max_records
        )

        hedge_df = self.market_data_provider.get_candles_df(
            connector_name=self.config.connector_pair_hedge.connector_name,
            trading_pair=self.config.connector_pair_hedge.trading_pair,
            interval=self.config.interval,
            max_records=self.max_records
        )

        if dominant_df.empty or hedge_df.empty:
            self.logger().warning("Not enough candle data available for statistical analysis")
            return

        # Extract close prices
        dominant_prices = dominant_df['close'].values
        hedge_prices = hedge_df['close'].values

        # Ensure we have enough data and both series have the same length
        min_length = min(len(dominant_prices), len(hedge_prices))
        if min_length < self.config.lookback_period:
            self.logger().warning(
                f"Not enough data points for analysis. Required: {self.config.lookback_period}, Available: {min_length}")
            return

        # Use the most recent data points
        dominant_prices = dominant_prices[-self.config.lookback_period:]
        hedge_prices = hedge_prices[-self.config.lookback_period:]

        # Convert to numpy arrays
        dominant_prices_np = np.array(dominant_prices, dtype=float)
        hedge_prices_np = np.array(hedge_prices, dtype=float)

        # Calculate percentage returns
        dominant_pct_change = np.diff(dominant_prices_np) / dominant_prices_np[:-1]
        hedge_pct_change = np.diff(hedge_prices_np) / hedge_prices_np[:-1]

        # Convert to cumulative returns
        dominant_cum_returns = np.cumprod(dominant_pct_change + 1)
        hedge_cum_returns = np.cumprod(hedge_pct_change + 1)

        # Normalize to start at 1
        dominant_cum_returns = dominant_cum_returns / dominant_cum_returns[0] if len(dominant_cum_returns) > 0 else np.array([1.0])
        hedge_cum_returns = hedge_cum_returns / hedge_cum_returns[0] if len(hedge_cum_returns) > 0 else np.array([1.0])

        # Perform linear regression
        dominant_cum_returns_reshaped = dominant_cum_returns.reshape(-1, 1)
        reg = LinearRegression().fit(dominant_cum_returns_reshaped, hedge_cum_returns)
        alpha = reg.intercept_
        beta = reg.coef_[0]
        self.processed_data.update({
            "alpha": alpha,
            "beta": beta,
        })

        # Calculate spread as percentage difference from predicted value
        y_pred = alpha + beta * dominant_cum_returns
        spread_pct = (hedge_cum_returns - y_pred) / y_pred * 100

        # Calculate z-score
        mean_spread = np.mean(spread_pct)
        std_spread = np.std(spread_pct)
        if std_spread == 0:
            self.logger().warning("Standard deviation of spread is zero, cannot calculate z-score")
            return

        current_spread = spread_pct[-1]
        current_z_score = (current_spread - mean_spread) / std_spread

        return current_spread, current_z_score

    def get_pairs_prices(self):
        current_dominant_price = self.market_data_provider.get_price_by_type(
            connector_name=self.config.connector_pair_dominant.connector_name,
            trading_pair=self.config.connector_pair_dominant.trading_pair, price_type=PriceType.MidPrice)

        current_hedge_price = self.market_data_provider.get_price_by_type(
            connector_name=self.config.connector_pair_hedge.connector_name,
            trading_pair=self.config.connector_pair_hedge.trading_pair, price_type=PriceType.MidPrice)
        return current_dominant_price, current_hedge_price

    def get_executors_dominant(self):
        active_executors_dominant_placed = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == self.config.connector_pair_dominant.connector_name and e.trading_pair == self.config.connector_pair_dominant.trading_pair and e.is_active and not e.is_trading and e.type == "position_executor"
        )
        active_executors_dominant_filled = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == self.config.connector_pair_dominant.connector_name and e.trading_pair == self.config.connector_pair_dominant.trading_pair and e.is_active and e.is_trading and e.type == "position_executor"
        )
        return active_executors_dominant_placed, active_executors_dominant_filled

    def get_executors_hedge(self):
        active_executors_hedge_placed = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == self.config.connector_pair_hedge.connector_name and e.trading_pair == self.config.connector_pair_hedge.trading_pair and e.is_active and not e.is_trading and e.type == "position_executor"
        )
        active_executors_hedge_filled = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == self.config.connector_pair_hedge.connector_name and e.trading_pair == self.config.connector_pair_hedge.trading_pair and e.is_active and e.is_trading and e.type == "position_executor"
        )
        return active_executors_hedge_placed, active_executors_hedge_filled

    def to_format_status(self) -> List[str]:
        """
        Format the status of the controller for display.
        """
        status_lines = []
        status_lines.append(f"""
Dominant Pair: {self.config.connector_pair_dominant} | Hedge Pair: {self.config.connector_pair_hedge} |
Timeframe: {self.config.interval} | Lookback Period: {self.config.lookback_period} | Entry Threshold: {self.config.entry_threshold}

Positions targets:
Theoretical Dominant         : {self.theoretical_dominant_quote} | Theoretical Hedge: {self.theoretical_hedge_quote} | Position Hedge Ratio: {self.config.pos_hedge_ratio}
Position Dominant            : {self.processed_data['position_dominant_quote']:.2f} | Position Hedge: {self.processed_data['position_hedge_quote']:.2f} | Imbalance: {self.processed_data['imbalance']:.2f} | Imbalance Scaled: {self.processed_data['imbalance_scaled_pct']:.2f} %

Current Executors:
Active Orders Dominant       : {len(self.processed_data['executors_dominant_placed'])} | Active Orders Hedge       : {len(self.processed_data['executors_hedge_placed'])} |
Active Orders Dominant Filled: {len(self.processed_data['executors_dominant_filled'])} | Active Orders Hedge Filled: {len(self.processed_data['executors_hedge_filled'])}

Signal: {self.processed_data['signal']:.2f} | Z-Score: {self.processed_data['z_score']:.2f} | Spread: {self.processed_data['spread']:.2f}
Alpha : {self.processed_data['alpha']:.2f} | Beta: {self.processed_data['beta']:.2f}
Pair PnL PCT: {self.processed_data['pair_pnl_pct'] * 100:.2f} %
""")
        return status_lines
