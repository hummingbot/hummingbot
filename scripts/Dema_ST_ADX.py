import os
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import Field, field_validator

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import MarketDict, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class DEMASTADXTokenConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    # markets: Dict[str, List[str]] = {}
    markets: MarketDict = MarketDict()
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    exchange: str = Field(default="hyperliquid_perpetual")
    trading_pairs: List[str] = Field(default=["HYPE-USD"])
    candles_exchange: str = Field(default="binance_perpetual")
    candles_pairs: List[str] = Field(default=["HYPE-USDT"])
    candles_interval: str = Field(default="5m")
    candles_length: int = Field(default=15, gt=0)

    # DEMA Configuration
    dema_length: int = Field(default=200, gt=0)

    # SuperTrend Configuration
    supertrend_length: int = Field(default=12, gt=0)
    supertrend_multiplier: float = Field(default=3.0, gt=0)

    # Order Configuration
    order_amount_quote: Decimal = Field(default=Decimal("100"), gt=0)
    leverage: int = Field(default=5, gt=0)
    position_mode: PositionMode = Field(default=PositionMode.ONEWAY)

    # Executor Timeout Configuration
    executor_timeout: int = Field(default=60, gt=0)

    # Startup Entry Configuration
    enable_startup_entry: bool = Field(default=False)

    # ADX Configuration
    adx_length: int = Field(default=14, gt=0)
    adx_threshold_choppy: float = Field(default=20.0, gt=0)
    adx_threshold_trending: float = Field(default=25.0, gt=0)
    adx_threshold_extreme: float = Field(default=45.0, gt=0)
    adx_slope_period: int = Field(default=5, gt=0)  # For trend acceleration/deceleration

    # Position sizing based on ADX
    enable_adx_position_sizing: bool = Field(default=False)
    position_size_weak_trend: Decimal = Field(default=Decimal("0.5"), gt=0)  # 50% size when ADX 20-25
    position_size_strong_trend: Decimal = Field(default=Decimal("1.0"), gt=0)  # 100% size when ADX > 25
    position_size_extreme_trend: Decimal = Field(default=Decimal("0.7"), gt=0)  # 70% size when ADX > 45

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v: str) -> PositionMode:
        if v.upper() in PositionMode.__members__:
            return PositionMode[v.upper()]
        raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")

    @field_validator('trading_pairs', mode="before")
    @classmethod
    def validate_trading_pairs(cls, v) -> List[str]:
        if isinstance(v, str):
            return [pair.strip() for pair in v.split(',')]
        return v

    @field_validator('candles_pairs', mode="before")
    @classmethod
    def validate_candles_pairs(cls, v) -> List[str]:
        if isinstance(v, str):
            return [pair.strip() for pair in v.split(',')]
        return v


class DEMASTADXTokenStrategy(StrategyV2Base):
    """
    This strategy uses DEMA and SuperTrend indicators to generate trading signals.
    Supports multiple trading pairs with candles from different exchanges.
    """

    account_config_set = False

    @classmethod
    def init_markets(cls, config: DEMASTADXTokenConfig):
        cls.markets = {config.exchange: set(config.trading_pairs)}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DEMASTADXTokenConfig):
        self.max_records = max(config.dema_length, config.supertrend_length, config.candles_length) + 20
        if len(config.candles_config) == 0:
            for candles_pair in config.candles_pairs:
                config.candles_config.append(CandlesConfig(
                    connector=config.candles_exchange,
                    trading_pair=candles_pair,
                    interval=config.candles_interval,
                    max_records=self.max_records
                ))
        super().__init__(connectors, config)
        self.config = config
        # Store indicators per trading pair
        self.current_dema = {}
        self.current_supertrend_direction = {}
        self.prev_supertrend_direction = {}
        self.current_price = {}
        self.prev_price = {}
        self.prev_dema = {}
        self.current_signal = {}
        self.is_startup = {}
        # ADX tracking
        self.current_adx = {}
        self.prev_adx = {}
        self.current_plus_di = {}
        self.current_minus_di = {}
        self.adx_slope = {}
        self.market_condition = {}  # "CHOPPY", "WEAK_TREND", "STRONG_TREND", "EXTREME_TREND"
        self.prev_market_condition = {}

    def start(self, clock: Clock, timestamp: float) -> None:  # clock is required by base class
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()
        # Initialize startup flag for each trading pair
        for candles_pair in self.config.candles_pairs:
            self.is_startup[candles_pair] = True

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        create_actions = []

        # Check signals for each trading pair
        for i, trading_pair in enumerate(self.config.trading_pairs):
            candles_pair = self.config.candles_pairs[i]
            signal = self.get_signal(self.config.candles_exchange, candles_pair)
            active_longs, active_shorts = self.get_active_executors_by_side(self.config.exchange, trading_pair)

            if signal is not None and signal != 0:  # Only process non-zero signals
                mid_price = self.market_data_provider.get_price_by_type(self.config.exchange,
                                                                        trading_pair,
                                                                        PriceType.MidPrice)

                # Dynamic position sizing based on ADX
                base_amount = self.config.order_amount_quote
                if self.config.enable_adx_position_sizing:
                    market_condition = self.market_condition.get(candles_pair, "CHOPPY")
                    if market_condition == "WEAK_TREND":
                        base_amount *= self.config.position_size_weak_trend
                    elif market_condition == "STRONG_TREND":
                        base_amount *= self.config.position_size_strong_trend
                    elif market_condition == "EXTREME_TREND":
                        base_amount *= self.config.position_size_extreme_trend
                        # Log warning about extreme trend
                        self.logger().warning(f"{trading_pair}: ADX > {self.config.adx_threshold_extreme}, reducing size to {self.config.position_size_extreme_trend}")

                if signal == 1 and len(active_longs) == 0:
                    create_actions.append(CreateExecutorAction(
                        executor_config=PositionExecutorConfig(
                            timestamp=self.current_timestamp,
                            connector_name=self.config.exchange,
                            trading_pair=trading_pair,
                            side=TradeType.BUY,
                            entry_price=mid_price,
                            amount=base_amount / mid_price,
                            triple_barrier_config=TripleBarrierConfig(),  # Default config with all barriers disabled
                            leverage=self.config.leverage
                        )))
                elif signal == -1 and len(active_shorts) == 0:
                    create_actions.append(CreateExecutorAction(
                        executor_config=PositionExecutorConfig(
                            timestamp=self.current_timestamp,
                            connector_name=self.config.exchange,
                            trading_pair=trading_pair,
                            side=TradeType.SELL,
                            entry_price=mid_price,
                            amount=base_amount / mid_price,
                            triple_barrier_config=TripleBarrierConfig(),  # Default config with all barriers disabled
                            leverage=self.config.leverage
                        )))
        return create_actions

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        stop_actions = []

        # Check signals for each trading pair
        for i, trading_pair in enumerate(self.config.trading_pairs):
            candles_pair = self.config.candles_pairs[i]

            # Get current SuperTrend direction for stop logic
            current_supertrend_direction = self.current_supertrend_direction.get(candles_pair)
            active_longs, active_shorts = self.get_active_executors_by_side(self.config.exchange, trading_pair)

            if current_supertrend_direction is not None:
                # Stop positions when SuperTrend reverses
                if current_supertrend_direction == -1 and len(active_longs) > 0:
                    stop_actions.extend([StopExecutorAction(
                        controller_id=e.controller_id or "main",
                        executor_id=e.id
                    ) for e in active_longs])
                elif current_supertrend_direction == 1 and len(active_shorts) > 0:
                    stop_actions.extend([StopExecutorAction(
                        controller_id=e.controller_id or "main",
                        executor_id=e.id
                    ) for e in active_shorts])

            # NEW: ADX-based stops
            adx_value = self.current_adx.get(candles_pair, 0)
            adx_slope = self.adx_slope.get(candles_pair, 0)

            # Stop if market becomes choppy
            if adx_value < self.config.adx_threshold_choppy:
                all_positions = active_longs + active_shorts
                for executor in all_positions:
                    # Only close profitable positions in choppy markets
                    if executor.net_pnl_pct > 0.002:  # 0.2% profit threshold
                        stop_actions.append(StopExecutorAction(
                            controller_id=executor.controller_id or "main",
                            executor_id=executor.id
                        ))
                        self.logger().info(f"Closing {trading_pair} position due to choppy market (ADX={adx_value:.1f})")

            # Stop on trend exhaustion (high ADX + negative slope)
            elif adx_value > self.config.adx_threshold_extreme and adx_slope < -1:
                all_positions = active_longs + active_shorts
                for executor in all_positions:
                    if executor.net_pnl_pct > 0:  # Any profit
                        stop_actions.append(StopExecutorAction(
                            controller_id=executor.controller_id or "main",
                            executor_id=executor.id
                        ))
                        self.logger().info(f"Closing {trading_pair} position due to trend exhaustion (ADX={adx_value:.1f}, slope={adx_slope:.2f})")

            # Check for timeout on unfilled executors
            all_active_executors = active_longs + active_shorts
            for executor in all_active_executors:
                executor_age = self.current_timestamp - executor.timestamp
                # Stop executors that are active but not trading (unfilled) and have exceeded timeout
                if executor.is_active and not executor.is_trading and executor_age > self.config.executor_timeout:
                    stop_actions.append(StopExecutorAction(
                        controller_id=executor.controller_id or "main",
                        executor_id=executor.id
                    ))

        return stop_actions

    def get_active_executors_by_side(self, connector_name: str, trading_pair: str):
        active_executors_by_trading_pair = self.filter_executors(
            executors=self.get_all_executors(),
            filter_func=lambda e: e.connector_name == connector_name and e.trading_pair == trading_pair and e.is_active
        )
        active_longs = [e for e in active_executors_by_trading_pair if e.side == TradeType.BUY]
        active_shorts = [e for e in active_executors_by_trading_pair if e.side == TradeType.SELL]
        return active_longs, active_shorts

    def get_signal(self, connector_name: str, trading_pair: str) -> Optional[float]:
        candles = self.market_data_provider.get_candles_df(connector_name,
                                                           trading_pair,
                                                           self.config.candles_interval,
                                                           self.max_records)

        if candles is None or candles.empty:
            return None

        # Calculate indicators
        candles.ta.dema(length=self.config.dema_length, append=True)
        candles.ta.supertrend(length=self.config.supertrend_length, multiplier=self.config.supertrend_multiplier, append=True)

        # Calculate ADX with directional indicators
        candles.ta.adx(length=self.config.adx_length, append=True)

        # Store previous ADX value before updating
        if trading_pair in self.current_adx:
            self.prev_adx[trading_pair] = self.current_adx[trading_pair]
        else:
            # Initialize prev_adx on first run
            if len(candles) > 1:
                self.prev_adx[trading_pair] = candles[f"ADX_{self.config.adx_length}"].iloc[-2]
            else:
                self.prev_adx[trading_pair] = candles[f"ADX_{self.config.adx_length}"].iloc[-1]

        # Get ADX values
        self.current_adx[trading_pair] = candles[f"ADX_{self.config.adx_length}"].iloc[-1]
        self.current_plus_di[trading_pair] = candles[f"DMP_{self.config.adx_length}"].iloc[-1]
        self.current_minus_di[trading_pair] = candles[f"DMN_{self.config.adx_length}"].iloc[-1]

        # Calculate ADX slope for trend acceleration/deceleration
        if len(candles) > self.config.adx_slope_period:
            current_adx = self.current_adx[trading_pair]
            past_adx = candles[f"ADX_{self.config.adx_length}"].iloc[-self.config.adx_slope_period - 1]
            self.adx_slope[trading_pair] = (current_adx - past_adx) / self.config.adx_slope_period
        else:
            self.adx_slope[trading_pair] = 0

        # Store previous market condition before updating
        if trading_pair in self.market_condition:
            self.prev_market_condition[trading_pair] = self.market_condition[trading_pair]
        else:
            self.prev_market_condition[trading_pair] = "CHOPPY"  # Default to choppy

        # Determine market condition
        adx_value = self.current_adx[trading_pair]
        if adx_value < self.config.adx_threshold_choppy:
            self.market_condition[trading_pair] = "CHOPPY"
        elif adx_value < self.config.adx_threshold_trending:
            self.market_condition[trading_pair] = "WEAK_TREND"
        elif adx_value < self.config.adx_threshold_extreme:
            self.market_condition[trading_pair] = "STRONG_TREND"
        else:
            self.market_condition[trading_pair] = "EXTREME_TREND"

        # Get current values
        self.current_price[trading_pair] = candles["close"].iloc[-1]
        self.current_dema[trading_pair] = candles[f"DEMA_{self.config.dema_length}"].iloc[-1]
        self.current_supertrend_direction[trading_pair] = candles[f"SUPERTd_{self.config.supertrend_length}_{self.config.supertrend_multiplier}"].iloc[-1]

        # Get previous values for trend change detection
        if len(candles) > 1:
            self.prev_supertrend_direction[trading_pair] = candles[f"SUPERTd_{self.config.supertrend_length}_{self.config.supertrend_multiplier}"].iloc[-2]
            self.prev_price[trading_pair] = candles["close"].iloc[-2]
            self.prev_dema[trading_pair] = candles[f"DEMA_{self.config.dema_length}"].iloc[-2]
        else:
            self.prev_supertrend_direction[trading_pair] = self.current_supertrend_direction[trading_pair]
            self.prev_price[trading_pair] = self.current_price[trading_pair]
            self.prev_dema[trading_pair] = self.current_dema[trading_pair]

        # Generate long and short conditions
        current_price = self.current_price[trading_pair]
        current_dema = self.current_dema[trading_pair]
        current_supertrend_direction = self.current_supertrend_direction[trading_pair]
        prev_supertrend_direction = self.prev_supertrend_direction[trading_pair]

        # self.logger().info(f"Current Price: {current_price}, Current DEMA: {current_dema}, Current SuperTrend Direction: {current_supertrend_direction}, Previous SuperTrend Direction: {prev_supertrend_direction}")

        # Check if this is the first signal check after startup
        is_startup_check = self.is_startup.get(trading_pair, False)

        # Get ADX values for conditions
        current_adx_val = self.current_adx[trading_pair]
        prev_adx_val = self.prev_adx.get(trading_pair, 0)
        adx_crossed_threshold = prev_adx_val < self.config.adx_threshold_choppy <= current_adx_val
        adx_above_threshold = current_adx_val >= self.config.adx_threshold_choppy

        # Long Entry Conditions:
        # 1. ADX crosses threshold with established bullish trend: ST already positive + Price > DEMA + ADX crosses above threshold
        # 2. ADX already established and ST flips: ADX above threshold + ST turns positive + Price > DEMA
        # 3. STARTUP: Price above DEMA AND SuperTrend is green (no flip required)
        long_condition_1 = (current_supertrend_direction == 1 and
                            current_price > current_dema and
                            adx_crossed_threshold)

        long_condition_2 = (adx_above_threshold and
                            current_price > current_dema and
                            current_supertrend_direction == 1 and
                            prev_supertrend_direction == -1)

        long_condition_startup = (is_startup_check and
                                  self.config.enable_startup_entry and
                                  current_price > current_dema and
                                  adx_above_threshold and
                                  current_supertrend_direction == 1)
        # self.logger().info(f"Long Condition 1: {long_condition_1}")
        # self.logger().info(f"Long Condition 2: {long_condition_2}")
        # self.logger().info(f"Long Condition Startup: {long_condition_startup}")
        # Short Entry Conditions:
        # 1. ADX crosses threshold with established bearish trend: ST already negative + Price < DEMA + ADX crosses above threshold
        # 2. ADX already established and ST flips: ADX above threshold + ST turns negative + Price < DEMA
        # 3. STARTUP: Price below DEMA AND SuperTrend is red (no flip required)
        short_condition_1 = (current_supertrend_direction == -1 and
                             current_price < current_dema and
                             adx_crossed_threshold)

        short_condition_2 = (adx_above_threshold and
                             current_price < current_dema and
                             current_supertrend_direction == -1 and
                             prev_supertrend_direction == 1)

        short_condition_startup = (is_startup_check and
                                   self.config.enable_startup_entry and
                                   current_price < current_dema and
                                   adx_above_threshold and
                                   current_supertrend_direction == -1)
        # self.logger().info(f"Short Condition 1: {short_condition_1}")
        # self.logger().info(f"Short Condition 2: {short_condition_2}")
        # self.logger().info(f"Short Condition Startup: {short_condition_startup}")
        # Determine signal
        if long_condition_1 or long_condition_2 or long_condition_startup:
            signal = 1
        elif short_condition_1 or short_condition_2 or short_condition_startup:
            signal = -1
        else:
            signal = 0

        # TO-DO (understand this part better)
        # Additional filter: Ensure directional agreement
        if signal == 1 and self.current_plus_di[trading_pair] <= self.current_minus_di[trading_pair]:
            signal = 0  # Cancel long if -DI is stronger
        elif signal == -1 and self.current_minus_di[trading_pair] <= self.current_plus_di[trading_pair]:
            signal = 0  # Cancel short if +DI is stronger

        # Reset startup flag after first signal check
        if is_startup_check:
            self.is_startup[trading_pair] = False

        self.current_signal[trading_pair] = signal
        return signal

    def apply_initial_setting(self):
        if not self.account_config_set:
            for connector_name, connector in self.connectors.items():
                if self.is_perpetual(connector_name):
                    connector.set_position_mode(self.config.position_mode)
                    for trading_pair in self.config.trading_pairs:
                        connector.set_leverage(trading_pair, self.config.leverage)
            self.account_config_set = True

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        # Create compact trading pairs overview
        lines.extend(["", "  Trading Pairs Overview:"])

        # Header for the grid
        header = f"{'Pair':<12} {'Price':<8} {'DEMA':<8} {'ST Dir':<6} {'ADX':<5} {'Condition':<10} {'Signal':<7} {'Long':<4} {'Short':<5}"
        lines.append(f"    {header}")
        lines.append(f"    {'-' * len(header)}")

        # Display each trading pair in compact format
        for i, candles_pair in enumerate(self.config.candles_pairs):
            # Get indicator values for this pair
            price = self.current_price.get(candles_pair, 0)
            dema = self.current_dema.get(candles_pair, 0)
            st_dir = self.current_supertrend_direction.get(candles_pair, 0)
            signal = self.current_signal.get(candles_pair, 0)

            # Format signal and direction display
            signal_text = "LONG" if signal == 1 else "SHORT" if signal == -1 else "NONE"
            st_text = "UP" if st_dir == 1 else "DOWN" if st_dir == -1 else "NONE"

            # Get ADX values
            adx = self.current_adx.get(candles_pair, 0)
            condition = self.market_condition.get(candles_pair, "UNKNOWN")

            # Get active positions for this pair
            if i < len(self.config.trading_pairs):
                actual_trading_pair = self.config.trading_pairs[i]
                active_longs, active_shorts = self.get_active_executors_by_side(self.config.exchange, actual_trading_pair)
            else:
                active_longs, active_shorts = [], []

            # Format the row
            pair_display = candles_pair.replace('-', '/') if len(candles_pair) > 12 else candles_pair
            row = f"{pair_display:<12} {price:>7.3f} {dema:>7.3f} {st_text:>6} {adx:>4.1f} {condition:<10} {signal_text:>7} {len(active_longs):>4} {len(active_shorts):>5}"
            lines.append(f"    {row}")

        # Add configuration info
        lines.extend([
            "",
            f"  Config: DEMA({self.config.dema_length}) | SuperTrend({self.config.supertrend_length}, {self.config.supertrend_multiplier})"
        ])

        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        # Active Position Executors
        active_executors = self.filter_executors(
            executors=self.get_all_executors(),
            filter_func=lambda e: e.is_active
        )

        if active_executors:
            lines.extend(["", "  Active Position Executors:"])
            for executor_info in active_executors:
                lines.extend([
                    f"    ID: {executor_info.id} | Type: {executor_info.type} | Status: {executor_info.status.value}",
                    f"    Pair: {executor_info.trading_pair} | Exchange: {executor_info.connector_name} | Side: {executor_info.side}",
                    f"    Net PnL: {executor_info.net_pnl_quote:.6f} ({executor_info.net_pnl_pct * 100:.2f}%)",
                    f"    Filled Amount: {executor_info.filled_amount_quote:.4f} | Fees: {executor_info.cum_fees_quote:.6f}",
                    f"    Active: {executor_info.is_active} | Trading: {executor_info.is_trading}",
                    "    ---"
                ])
        else:
            lines.extend(["", "  No active position executors."])

        return "\n".join(lines)
