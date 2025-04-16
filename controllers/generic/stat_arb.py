from decimal import Decimal
from typing import List

import numpy as np
from pydantic import Field
from statsmodels.regression.linear_model import OLS

from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class StatArbConfig(ControllerConfigBase):
    """
    Configuration for a statistical arbitrage controller that trades two cointegrated assets.
    """
    controller_type: str = "generic"
    controller_name: str = "stat_arb"
    candles_config: List[CandlesConfig] = []
    connector_pair_dominant: ConnectorPair = ConnectorPair(connector_name="binance_perpetual", trading_pair="POPCAT-USDT")
    connector_pair_hedge: ConnectorPair = ConnectorPair(connector_name="binance_perpetual", trading_pair="CAKE-USDT")
    interval: str = "3m"
    lookback_period: int = Field(
        default=200,
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the lookback period for cointegration analysis:",
        }
    )
    entry_threshold: Decimal = Field(
        default=Decimal("2.0"),
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the Z-score threshold to enter positions:",
        }
    )
    take_profit: Decimal = Field(
        default=Decimal("0.0008"),
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the take profit percentage for individual positions:",
        }
    )
    position_hold_time: int = Field(
        default=120,
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the position hold time in seconds:",
        }
    )
    tp_global: Decimal = Field(
        default=Decimal("0.01"),
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the global take profit threshold for combined positions:",
        }
    )
    sl_global: Decimal = Field(
        default=Decimal("0.05"),
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the global stop loss threshold for combined positions:",
        }
    )
    max_position_deviation: Decimal = Field(
        default=Decimal("0.1"),
        json_schema_extra={
            "prompt_on_new": True,
            "is_updatable": True,
            "prompt": "Enter the maximum allowed deviation between long and short positions:",
        }
    )

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

    def determine_executor_actions(self) -> List[ExecutorAction]:
        return []

    async def update_processed_data(self):
        """
        Update processed data with the latest market information and statistical calculations
        needed for the statistical arbitrage strategy.
        """
        # Fetch candle data for both assets
        dominant_df = self.market_data_provider.get_candles_df(
            connector_name=self.config.connector_pair_dominant.connector_name,
            trading_pair=self.config.connector_pair_dominant.trading_pair,
            interval=self.config.interval,
            max_records=self.config.lookback_period + 20
        )

        hedge_df = self.market_data_provider.get_candles_df(
            connector_name=self.config.connector_pair_hedge.connector_name,
            trading_pair=self.config.connector_pair_hedge.trading_pair,
            interval=self.config.interval,
            max_records=self.config.lookback_period + 20
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
            self.logger().warning(f"Not enough data points for analysis. Required: {self.config.lookback_period}, Available: {min_length}")
            return

        # Use the most recent data points
        dominant_prices = dominant_prices[-self.config.lookback_period:]
        hedge_prices = hedge_prices[-self.config.lookback_period:]

        # Calculate hedge ratio using OLS regression
        # This is the beta in the cointegration relationship
        model = OLS(dominant_prices, hedge_prices)
        results = model.fit()
        hedge_ratio = results.params[0]
        # Calculate the spread
        spread = dominant_prices - hedge_ratio * hedge_prices
        # Calculate z-score
        mean_spread = np.mean(spread)
        std_spread = np.std(spread)
        if std_spread == 0:
            self.logger().warning("Standard deviation of spread is zero, cannot calculate z-score")
            return
        # Current values
        current_dominant_price = dominant_prices[-1]
        current_hedge_price = hedge_prices[-1]
        current_spread = spread[-1]
        current_z_score = (current_spread - mean_spread) / std_spread
        # Get current positions
        # For dominant asset
        dom_connector = self.config.connector_pair_dominant.connector_name
        dom_trading_pair = self.config.connector_pair_dominant.trading_pair
        positions_dominant = next((position for position in self.positions_held if position.connector_name == dom_connector and position.trading_pair == dom_trading_pair), None)
        hedge_connector = self.config.connector_pair_hedge.connector_name
        hedge_trading_pair = self.config.connector_pair_hedge.trading_pair
        positions_hedge = next((position for position in self.positions_held if position.connector_name == hedge_connector and position.trading_pair == hedge_trading_pair), None)
        # Get position stats
        position_dominant_quote = positions_dominant[0].amount_quote if positions_dominant else Decimal("0")
        position_hedge_quote = positions_hedge[0].amount_quote if positions_hedge else Decimal("0")
        imbalance = position_dominant_quote - position_hedge_quote
        position_dominant_pnl_quote = positions_dominant[0].global_pnl_quote if positions_dominant else Decimal("0")
        position_hedge_pnl_quote = positions_hedge[0].global_pnl_quote if positions_hedge else Decimal("0")
        pair_pnl_pct = (position_dominant_pnl_quote + position_hedge_pnl_quote) / (position_dominant_quote + position_hedge_quote) if (position_dominant_quote + position_hedge_quote) != 0 else Decimal("0")
        # Get active executors
        active_executors_dominant_placed = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == dom_connector and e.trading_pair == dom_trading_pair and e.is_active and not e.is_trading
        )
        active_executors_hedge_placed = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == hedge_connector and e.trading_pair == hedge_trading_pair and e.is_active and not e.is_trading
        )
        active_executors_dominant_filled = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == dom_connector and e.trading_pair == dom_trading_pair and e.is_active and e.is_trading
        )
        active_executors_hedge_filled = self.filter_executors(
            self.executors_info,
            filter_func=lambda e: e.connector_name == hedge_connector and e.trading_pair == hedge_trading_pair and e.is_active and e.is_trading
        )
        min_price_dominant = Decimal(str(min([executor.price for executor in active_executors_dominant_placed]))) if active_executors_dominant_placed else None
        max_price_dominant = Decimal(str(max([executor.price for executor in active_executors_dominant_placed]))) if active_executors_dominant_placed else None
        min_price_hedge = Decimal(str(min([executor.price for executor in active_executors_hedge_placed]))) if active_executors_hedge_placed else None
        max_price_hedge = Decimal(str(max([executor.price for executor in active_executors_hedge_placed]))) if active_executors_hedge_placed else None
        num_active_orders_dominant = len(active_executors_dominant_placed)
        num_active_orders_hedge = len(active_executors_hedge_placed)
        num_active_orders_dominant_filled = len(active_executors_dominant_filled)
        num_active_orders_hedge_filled = len(active_executors_hedge_filled)
        # Funding Rate
        funding_info_dominant = self.market_data_provider.get_funding_info(
            connector_name=self.config.connector_pair_dominant.connector_name,
            trading_pair=self.config.connector_pair_dominant.trading_pair
        )
        funding_info_hedge = self.market_data_provider.get_funding_info(
            connector_name=self.config.connector_pair_hedge.connector_name,
            trading_pair=self.config.connector_pair_hedge.trading_pair
        )
        # Generate trading signal based on z-score
        signal = 0
        entry_threshold = float(self.config.entry_threshold)
        if current_z_score > entry_threshold:
            # Spread is too high, expect it to revert: short dominant, long hedge
            signal = -1
        elif current_z_score < -entry_threshold:
            # Spread is too low, expect it to revert: long dominant, short hedge
            signal = 1
        # Update processed data
        self.processed_data = {
            "dominant_price": Decimal(str(current_dominant_price)),
            "hedge_price": Decimal(str(current_hedge_price)),
            "spread": Decimal(str(current_spread)),
            "z_score": Decimal(str(current_z_score)),
            "hedge_ratio": Decimal(str(hedge_ratio)),
            "position_dominant_quote": position_dominant_quote,
            "position_hedge_quote": position_hedge_quote,
            "signal": signal,
            # Store full dataframes for reference
            "dominant_df": dominant_df,
            "hedge_df": hedge_df,
            "imbalance": Decimal(str(imbalance)),
            "min_price_dominant": min_price_dominant,
            "max_price_dominant": max_price_dominant,
            "min_price_hedge": min_price_hedge,
            "max_price_hedge": max_price_hedge,
            "num_active_orders_dominant": num_active_orders_dominant,
            "num_active_orders_hedge": num_active_orders_hedge,
            "num_active_orders_dominant_filled": num_active_orders_dominant_filled,
            "num_active_orders_hedge_filled": num_active_orders_hedge_filled,
            "funding_info_dominant": funding_info_dominant,
            "funding_info_hedge": funding_info_hedge,
            "pair_pnl_pct": pair_pnl_pct,
        }

    def to_format_status(self) -> List[str]:
        """
        Format the status of the controller for display.
        """
        status_lines = []
        status_lines.append(f"""
Dominant Pair: {self.config.connector_pair_dominant} | Hedge Pair: {self.config.connector_pair_hedge} | Timeframe: {self.config.interval} | Lookback Period: {self.config.lookback_period} | Entry Threshold: {self.config.entry_threshold}
Position Dominant: {self.processed_data['position_dominant_quote']} | Position Hedge: {self.processed_data['position_hedge_quote']} | Imbalance: {self.processed_data['imbalance']} |
Funding Dominant: {self.processed_data['funding_info_dominant'].rate} | Funding Hedge: {self.processed_data['funding_info_hedge'].rate}
Signal: {self.processed_data['signal']} | Z-Score: {self.processed_data['z_score']} | Spread: {self.processed_data['spread']}
Active Orders Dominant: {self.processed_data['num_active_orders_dominant']} | Active Orders Hedge: {self.processed_data['num_active_orders_hedge']}
Active Orders Dominant Filled: {self.processed_data['num_active_orders_dominant_filled']} | Active Orders Hedge Filled: {self.processed_data['num_active_orders_hedge_filled']}

Pair PnL PCT: {self.processed_data['pair_pnl_pct']}
""")
        return status_lines
