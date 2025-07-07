from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from pydantic import Field, field_validator

from hummingbot.core.data_type.common import MarketDict, OrderType, PriceType, TradeType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.funding_arbitrage_executor.data_types import FundingArbitrageExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class FundingRateArbitrageControllerConfig(ControllerConfigBase):
    """
    Configuration for the Funding Rate Arbitrage Controller.

    This controller monitors funding rates across multiple exchanges and tokens,
    identifies profitable arbitrage opportunities, and creates executors to
    capture funding rate differentials.
    """
    controller_type: str = "funding_rate_arbitrage"

    # Exchange and token configuration
    exchanges: Set[str] = Field(
        default="hyperliquid_perpetual,binance_perpetual",
        json_schema_extra={
            "prompt": "Enter the perpetual exchanges separated by commas (e.g., hyperliquid_perpetual,binance_perpetual): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    token: str = Field(
        default="WIF",
        json_schema_extra={
            "prompt": "Enter the token to monitor (e.g., WIF): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    # Position sizing
    position_size_quote: Decimal = Field(
        default=Decimal("100"),
        gt=0,
        json_schema_extra={
            "prompt": "Enter the position size in quote asset (e.g., 100 will open $100 long and $100 short): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    # Funding rate normalization and profitability calculation
    funding_profitability_interval_hours: int = Field(
        default=24,
        ge=1,
        json_schema_extra={
            "prompt": "Enter the time interval in hours to calculate funding profitability (e.g., 24 for daily): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    # Profitability thresholds
    min_funding_rate_profitability: Decimal = Field(
        default=Decimal("0.001"),
        gt=0,
        json_schema_extra={
            "prompt": "Enter the minimum funding rate profitability to enter a position (e.g., 0.001 for 0.1%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    profitability_to_take_profit: Decimal = Field(
        default=Decimal("0.01"),
        gt=0,
        json_schema_extra={
            "prompt": "Enter the profitability threshold to take profit (including PnL and funding received, e.g., 0.01 for 1%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    funding_rate_diff_stop_loss: Decimal = Field(
        default=Decimal("-0.001"),
        json_schema_extra={
            "prompt": "Enter the funding rate difference to stop the position (e.g., -0.001 for -0.1%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    # Risk management
    max_active_positions: int = Field(
        default=3,
        ge=1,
        json_schema_extra={
            "prompt": "Enter the maximum number of active arbitrage positions (e.g., 3): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    leverage: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "prompt": "Enter the leverage to use for trading (e.g., 20 for 20x leverage): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    # Risk management (add after existing risk management fields)
    stop_loss_pct: Optional[Decimal] = Field(
        default=Decimal("0.02"),
        ge=0,
        json_schema_extra={
            "prompt": "Enter the stop loss threshold as percentage (e.g., 0.02 for 2%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    max_position_duration_seconds: Optional[int] = Field(
        default=24 * 60 * 60,  # 24 hours
        gt=0,
        json_schema_extra={
            "prompt": "Enter maximum position duration in seconds (e.g., 86400 for 24 hours): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    asymmetric_fill_timeout_seconds: int = Field(
        default=300,  # 5 minutes
        ge=1,
        json_schema_extra={
            "prompt": "Enter timeout in seconds before closing positions if only one side is filled (e.g., 600 for 10 minutes): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    order_renewal_threshold_pct: Decimal = Field(
        default=Decimal("0.005"),  # 0.5%
        ge=0,
        json_schema_extra={
            "prompt": "Enter price movement threshold to trigger order renewal (e.g., 0.005 for 0.5%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    entry_limit_order_spread_bps: int = Field(
        default=2,
        ge=0,
        json_schema_extra={
            "prompt": "Enter spread in basis points for entry limit orders (e.g., 2 for 0.02%): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    @field_validator("exchanges", mode="before")
    @classmethod
    def validate_sets(cls, v):
        """Convert comma-separated strings to sets."""
        if isinstance(v, str):
            return set(item.strip() for item in v.split(",") if item.strip())
        return v

    @field_validator("exchanges")
    @classmethod
    def validate_exchanges(cls, v):
        """Validate that exchanges are perpetual futures exchanges."""
        perpetual_exchanges = {
            "binance_perpetual", "hyperliquid_perpetual", "bybit_perpetual",
            "dydx_perpetual", "coinbase_perpetual", "okx_perpetual"
        }
        invalid_exchanges = v - perpetual_exchanges
        if invalid_exchanges:
            raise ValueError(f"Invalid perpetual exchanges: {invalid_exchanges}. "
                             f"Valid options: {perpetual_exchanges}")
        return v

    @field_validator("token")
    @classmethod
    def validate_token(cls, v):
        """Validate token format."""
        if not v.isalnum() or len(v) > 10:
            raise ValueError(f"Invalid token format: {v}. "
                             f"Token should be alphanumeric and <= 10 characters.")
        return v

    @property
    def funding_payment_interval_map(self) -> Dict[str, int]:
        """
        Map of exchange to funding payment intervals in seconds.
        Similar to the existing v2 script approach.
        """
        return {
            "binance_perpetual": 60 * 60 * 8,  # 8 hours
            "hyperliquid_perpetual": 60 * 60 * 1,  # 1 hour
            "bybit_perpetual": 60 * 60 * 8,  # 8 hours
            "dydx_perpetual": 60 * 60 * 8,  # 8 hours
            "coinbase_perpetual": 60 * 60 * 8,  # 8 hours
            "okx_perpetual": 60 * 60 * 8,  # 8 hours
        }

    @property
    def funding_profitability_interval_seconds(self) -> int:
        """
        Convert funding profitability interval from hours to seconds.
        Used for calculating expected profitability over the specified time period.
        """
        return self.funding_profitability_interval_hours * 60 * 60

    def get_normalized_funding_rate_per_second(self, funding_rate: Decimal, exchange: str) -> Decimal:
        """
        Convert funding rate to per-second rate for comparison across exchanges.
        Similar to the existing v2 script's get_normalized_funding_rate_in_seconds method.

        Args:
            funding_rate: The raw funding rate from the exchange
            exchange: The exchange name

        Returns:
            Normalized funding rate per second
        """
        interval_seconds = self.funding_payment_interval_map.get(exchange, 60 * 60 * 8)
        return funding_rate / Decimal(interval_seconds)

    def calculate_funding_profitability(self, rate_per_second_1: Decimal, rate_per_second_2: Decimal) -> Decimal:
        """
        Calculate the expected profitability from funding rate differential over the configured interval.
        Similar to the existing v2 script's profitability calculation.

        Args:
            rate_per_second_1: Normalized funding rate per second for exchange 1
            rate_per_second_2: Normalized funding rate per second for exchange 2

        Returns:
            Expected profitability over the configured interval
        """
        funding_rate_diff = abs(rate_per_second_1 - rate_per_second_2)
        return funding_rate_diff * Decimal(self.funding_profitability_interval_seconds)

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Update the markets dict with required trading pairs."""
        quote_asset_map = {
            "hyperliquid_perpetual": "USD",
            "binance_perpetual": "USDT",
            "bybit_perpetual": "USDT",
            "dydx_perpetual": "USD",
            "coinbase_perpetual": "USD",
            "okx_perpetual": "USDT"
        }

        for exchange in self.exchanges:
            quote_asset = quote_asset_map.get(exchange, "USDT")
            trading_pair = f"{self.token}-{quote_asset}"
            markets = markets.add_or_update(exchange, trading_pair)

        return markets


class FundingRateArbitrageController(ControllerBase):
    """
    A controller that monitors funding rates across exchanges for a single token
    and creates executors to capture arbitrage opportunities.

    Following proper V2 patterns where:
    - Controller only creates executors when opportunities arise
    - Executors are self-sufficient and manage their own lifecycle
    - Controller focuses on a single token for simplicity
    """

    def __init__(self, config: FundingRateArbitrageControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

        # Data storage for funding rates and normalization
        self.funding_rates_data: Dict[str, object] = {}  # exchange -> FundingInfo
        self.normalized_rates_data: Dict[str, Decimal] = {}  # exchange -> normalized_rate

        # Track active executors count (but don't manage them)
        self._active_executors_count = 0

    async def update_processed_data(self):
        """
        Update processed data by fetching and normalizing funding rates.
        This is called by the framework before determine_executor_actions.
        """
        self._fetch_funding_rates()
        self._normalize_funding_rates()

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine if any executor actions should be taken.
        Only creates new executors when opportunities exist and capacity allows.
        """
        actions = []

        self.logger().info(f"Determining executor actions for {self.config.token}")

        # Update active executor count from framework
        self._active_executors_count = len([
            executor for executor in self.executors_info
            if executor.status == RunnableStatus.RUNNING
        ])

        self.logger().info(f"Active executors: {self._active_executors_count}/{self.config.max_active_positions}")

        # Only create new executors if under max capacity
        if self._active_executors_count < self.config.max_active_positions:
            opportunity = self._find_best_opportunity()
            if opportunity:
                self.logger().info(f"Best opportunity found: {opportunity}")
                executor_config = self._create_arbitrage_executor(opportunity)
                if executor_config:
                    action = CreateExecutorAction(
                        controller_id=self.config.id,
                        executor_config=executor_config
                    )
                    actions.append(action)
                    self.logger().info(f"Created arbitrage executor action for {self.config.token}: "
                                       f"{opportunity['long_exchange']} (long) vs {opportunity['short_exchange']} (short), "
                                       f"differential: {opportunity['funding_rate_differential']:.6f}")
                else:
                    self.logger().warning(f"Failed to create executor config for opportunity: {opportunity}")
            else:
                self.logger().info("No profitable opportunities found")
        else:
            self.logger().info(f"At maximum capacity ({self._active_executors_count}/{self.config.max_active_positions})")

        return actions

    def _fetch_funding_rates(self):
        """Fetch funding rate information for the token across all exchanges."""
        self.funding_rates_data = {}

        for exchange in self.config.exchanges:
            try:
                trading_pair = self._get_trading_pair_for_exchange(exchange)
                funding_info = self.market_data_provider.get_funding_info(exchange, trading_pair)

                if funding_info:
                    self.funding_rates_data[exchange] = funding_info
                else:
                    self.logger().warning(f"No funding info available for {exchange}:{trading_pair}")

            except Exception as e:
                self.logger().error(f"Error fetching funding rates for {exchange}: {e}")

    def _normalize_funding_rates(self):
        """Normalize funding rates using config parameters for comparison."""
        self.normalized_rates_data = {}

        # Only process exchanges that actually have funding data
        for exchange, funding_info in self.funding_rates_data.items():
            try:
                # Use config method to get normalized rate per second
                rate_per_second = self.config.get_normalized_funding_rate_per_second(
                    funding_info.rate, exchange
                )
                self.normalized_rates_data[exchange] = rate_per_second

            except Exception as e:
                self.logger().error(f"Error normalizing funding rate for {exchange}: {e}")

    def _find_best_opportunity(self) -> Optional[Dict]:
        """
        Find the best arbitrage opportunity for the token.
        Returns the opportunity with highest profitability above the minimum threshold.
        """
        if len(self.normalized_rates_data) < 2:
            return None

        best_opportunity = None
        highest_net_profitability = Decimal("0")

        exchanges = list(self.normalized_rates_data.keys())

        # Evaluate all exchange pairs
        for i, long_exchange in enumerate(exchanges):
            for short_exchange in exchanges[i + 1:]:
                opportunity = self._evaluate_exchange_pair(long_exchange, short_exchange)
                if opportunity and opportunity["net_profitability"] > highest_net_profitability:
                    highest_net_profitability = opportunity["net_profitability"]
                    best_opportunity = opportunity

                # Also check the reverse direction
                opportunity = self._evaluate_exchange_pair(short_exchange, long_exchange)
                if opportunity and opportunity["net_profitability"] > highest_net_profitability:
                    highest_net_profitability = opportunity["net_profitability"]
                    best_opportunity = opportunity

        return best_opportunity

    def _evaluate_exchange_pair(self, exchange_1: str, exchange_2: str) -> Optional[Dict]:
        """Evaluate if an exchange pair provides a profitable opportunity."""
        try:
            rate_per_second_1 = self.normalized_rates_data[exchange_1]
            rate_per_second_2 = self.normalized_rates_data[exchange_2]

            # Calculate expected profitability using config method
            expected_funding_profitability = self.config.calculate_funding_profitability(
                rate_per_second_1, rate_per_second_2
            )

            # Determine direction (we want to short higher rate, long lower rate)
            if rate_per_second_1 < rate_per_second_2:
                long_exchange = exchange_1
                short_exchange = exchange_2
                funding_rate_differential = rate_per_second_2 - rate_per_second_1
            else:
                long_exchange = exchange_2
                short_exchange = exchange_1
                funding_rate_differential = rate_per_second_1 - rate_per_second_2

            # If no meaningful differential, skip
            if funding_rate_differential <= 0:
                return None

            # Calculate estimated trading fees
            long_entry_fee, short_entry_fee, long_exit_fee, short_exit_fee, total_fees = self._calculate_estimated_trading_fees(long_exchange, short_exchange)

            # Net profitability calculation (like XEMM executor)
            net_profitability = expected_funding_profitability - total_fees

            if net_profitability >= self.config.min_funding_rate_profitability:
                return {
                    "long_exchange": long_exchange,
                    "short_exchange": short_exchange,
                    "funding_rate_differential": funding_rate_differential,
                    "expected_funding_pnl": expected_funding_profitability,
                    "estimated_fees": total_fees,
                    "fee_breakdown": {
                        "long_entry_fee": long_entry_fee,
                        "short_entry_fee": short_entry_fee,
                        "long_exit_fee": long_exit_fee,
                        "short_exit_fee": short_exit_fee,
                        "total_fees": total_fees
                    },
                    "net_profitability": net_profitability
                }

        except Exception as e:
            self.logger().error(f"Error evaluating exchange pair {exchange_1}-{exchange_2}: {e}")

        return None

    def _calculate_estimated_trading_fees(self, long_exchange: str, short_exchange: str) -> Tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        """
        Calculate estimated trading fees for entering and exiting positions.
        Uses connector APIs when available, similar to XEMM executor approach.
        Differentiates between maker and taker
        """
        try:
            long_trading_pair = self._get_trading_pair_for_exchange(long_exchange)
            short_trading_pair = self._get_trading_pair_for_exchange(short_exchange)

            # Entry: Use limit makers when possible for better pricing
            entry_order_type = OrderType.LIMIT_MAKER
            # Exit: Can use more aggressive pricing for faster execution
            exit_order_type = OrderType.MARKET

            # Calculate entry fees (long position on long_exchange, short position on short_exchange)
            long_entry_fee = self._get_connector_trading_fee(
                long_exchange, long_trading_pair, entry_order_type, TradeType.BUY, is_entry=True
            )
            short_entry_fee = self._get_connector_trading_fee(
                short_exchange, short_trading_pair, entry_order_type, TradeType.SELL, is_entry=True
            )

            # Calculate exit fees (close long position, close short position)
            long_exit_fee = self._get_connector_trading_fee(
                long_exchange, long_trading_pair, exit_order_type, TradeType.SELL, is_entry=False
            )
            short_exit_fee = self._get_connector_trading_fee(
                short_exchange, short_trading_pair, exit_order_type, TradeType.BUY, is_entry=False
            )
            total_fees = long_entry_fee + short_entry_fee + long_exit_fee + short_exit_fee
            return long_entry_fee, short_entry_fee, long_exit_fee, short_exit_fee, total_fees

        except Exception as e:
            self.logger().error(f"Error calculating trading fees: {e}")
            return Decimal("0.0004"), Decimal("0.0004"), Decimal("0.0004"), Decimal("0.0004"), Decimal("0.0016")  # 4 trades total

    def _get_connector_trading_fee(self, exchange: str, trading_pair: str, order_type: OrderType,
                                   trade_type: TradeType, is_entry: bool) -> Decimal:
        """
        Get trading fee using the V2 standard pattern.
        Controllers use market data provider for fee calculation when available.
        """
        try:
            # Try to get fee info from market data provider's connectors
            if hasattr(self.market_data_provider, 'connectors') and exchange in self.market_data_provider.connectors:
                connector = self.market_data_provider.connectors[exchange]

                # Get current price for fee calculation
                current_price = self.market_data_provider.get_price_by_type(
                    exchange, trading_pair, PriceType.MidPrice
                )

                if current_price and current_price > 0:
                    # Calculate order amount based on position size
                    order_amount = self.config.position_size_quote / current_price
                    base_asset, quote_asset = trading_pair.split("-")

                    # Use connector's get_fee method
                    fee_info = connector.get_fee(
                        base_currency=base_asset,
                        quote_currency=quote_asset,
                        order_type=order_type,
                        order_side=trade_type,
                        amount=order_amount,
                        price=current_price,
                        is_maker=(order_type == OrderType.LIMIT_MAKER)
                    )

                    # Return the percentage fee
                    return fee_info.percent

        except Exception as e:
            self.logger().debug(f"Could not get connector fee for {exchange}, using estimate: {e}")

        # Fallback to hardcoded estimates when connector is not available
        return self._get_estimated_exchange_fee(exchange, order_type)

    def _get_estimated_exchange_fee(self, exchange: str, order_type: OrderType) -> Decimal:
        """Get estimated fee for an exchange, differentiating maker vs taker."""
        if order_type == OrderType.LIMIT_MAKER:
            # Maker fees (limit orders)
            maker_fee_estimates = {
                "binance_perpetual": Decimal("0.0002"),
                "hyperliquid_perpetual": Decimal("0.0000"),  # No maker fees
                "dydx_perpetual": Decimal("0.0003"),
                "bybit_perpetual": Decimal("0.0002"),
                "gate_io_perpetual": Decimal("0.0002"),
                "kucoin_perpetual": Decimal("0.0002"),
                "okx_perpetual": Decimal("0.0002")
            }
            return maker_fee_estimates.get(exchange, Decimal("0.0002"))
        else:
            # Taker fees (market orders)
            taker_fee_estimates = {
                "binance_perpetual": Decimal("0.0004"),
                "hyperliquid_perpetual": Decimal("0.0002"),
                "dydx_perpetual": Decimal("0.0005"),
                "bybit_perpetual": Decimal("0.0006"),
                "gate_io_perpetual": Decimal("0.0004"),
                "kucoin_perpetual": Decimal("0.0006"),
                "okx_perpetual": Decimal("0.0005")
            }
            return taker_fee_estimates.get(exchange, Decimal("0.0005"))

    def _create_arbitrage_executor(self, opportunity: Dict) -> Optional[FundingArbitrageExecutorConfig]:
        """Create a FundingArbitrageExecutorConfig from an opportunity."""
        try:
            long_trading_pair = self._get_trading_pair_for_exchange(opportunity["long_exchange"])
            short_trading_pair = self._get_trading_pair_for_exchange(opportunity["short_exchange"])

            executor_config = FundingArbitrageExecutorConfig(
                timestamp=self.market_data_provider.time(),
                long_market=ConnectorPair(
                    connector_name=opportunity["long_exchange"],
                    trading_pair=long_trading_pair
                ),
                short_market=ConnectorPair(
                    connector_name=opportunity["short_exchange"],
                    trading_pair=short_trading_pair
                ),
                position_size_quote=self.config.position_size_quote,
                leverage=self.config.leverage,
                entry_limit_order_spread_bps=self.config.entry_limit_order_spread_bps,
                take_profit_pct=self.config.profitability_to_take_profit,
                stop_loss_pct=self.config.stop_loss_pct,
                min_funding_rate_differential=self.config.funding_rate_diff_stop_loss,
                max_position_duration_seconds=self.config.max_position_duration_seconds,
                asymmetric_fill_timeout_seconds=self.config.asymmetric_fill_timeout_seconds,
                order_renewal_threshold_pct=self.config.order_renewal_threshold_pct,
            )
            return executor_config

        except Exception as e:
            self.logger().error(f"Error creating executor config: {e}")
            self.logger().error(f"Error type: {type(e)}")
            import traceback
            self.logger().error(f"Full traceback: {traceback.format_exc()}")
            return None

    def _get_trading_pair_for_exchange(self, exchange: str) -> str:
        """Get the trading pair for a given exchange."""
        quote_asset_map = {
            "hyperliquid_perpetual": "USD",
            "binance_perpetual": "USDT",
            "bybit_perpetual": "USDT",
            "dydx_perpetual": "USD",
            "coinbase_perpetual": "USD",
            "okx_perpetual": "USDT"
        }
        quote_asset = quote_asset_map.get(exchange, "USDT")
        return f"{self.config.token}-{quote_asset}"

    def _get_order_type_info(self) -> Dict[str, str]:
        """Get formatted order type information for display."""
        return {
            "entry_type": "MAKER (Limit)",
            "exit_type": "TAKER (Market)",
            "description": ""
        }

    def to_format_status(self) -> List[str]:
        """
        Format the status of the controller for display with compact vertical layout.
        """
        status_lines = []

        # Header line with all key info
        status_lines.append(f"=== Funding Rate Arbitrage: {self.config.token} | Size: ${self.config.position_size_quote} | Min: {self.config.min_funding_rate_profitability:.3%} | Active: {self._active_executors_count}/{self.config.max_active_positions} ===")

        # Display current funding rates in compact format
        if self.normalized_rates_data:
            # One line per exchange with horizontal layout
            rate_display = []
            for exchange, rate in self.normalized_rates_data.items():
                daily_rate = rate * 86400 * 100  # Convert per-second to per-day percentage
                exchange_short = exchange.replace("_perpetual", "").upper()
                rate_display.append(f"{exchange_short}: {daily_rate:+.3f}%/d")

            status_lines.append(f"📈 Funding Rates: {' | '.join(rate_display)}")

            # Display best opportunity in compact format
            opportunity = self._find_best_opportunity()
            if opportunity:
                long_ex = opportunity['long_exchange'].replace('_perpetual', '').upper()
                short_ex = opportunity['short_exchange'].replace('_perpetual', '').upper()
                daily_diff = opportunity['funding_rate_differential'] * 86400 * 100
                expected_pnl = opportunity['expected_funding_pnl']
                total_fees = opportunity.get('estimated_fees', Decimal('0'))
                net_pnl = opportunity['net_profitability']

                # Status indicator
                if self._active_executors_count >= self.config.max_active_positions:
                    status_icon = "⏸️"
                elif net_pnl >= self.config.min_funding_rate_profitability:
                    status_icon = "✅"
                else:
                    status_icon = "❌"

                status_lines.append(f"🎯 Best Opportunity: {status_icon} Long {long_ex} / Short {short_ex} | Diff: {daily_diff:+.3f}%/d | Expected: {expected_pnl:.3%} | Fees: {total_fees:.3%} | Net: {net_pnl:.3%}")
            else:
                status_lines.append("🔍 No profitable opportunities available")
        else:
            status_lines.append("⚠️  Waiting for funding rate data...")

        # Compact executor status table
        if self.executors_info:
            running_executors = [e for e in self.executors_info if e.status == RunnableStatus.RUNNING]
            if running_executors:
                status_lines.append("🔧 Active Executors:")
                # Table header
                status_lines.append(f"{'ID':<8} {'Type':<20} {'PnL':<10} {'Age':<8} {'Status':<12}")
                status_lines.append("-" * 65)

                for executor_info in running_executors:
                    try:
                        executor_id = executor_info.id[:8]
                        executor_type = executor_info.type[:20] if hasattr(executor_info, 'type') else "Unknown"

                        # PnL info
                        pnl_str = "N/A"
                        if hasattr(executor_info, 'net_pnl_quote') and executor_info.net_pnl_quote is not None:
                            pnl_str = f"${executor_info.net_pnl_quote:.2f}"
                        elif hasattr(executor_info, 'custom_info') and executor_info.custom_info:
                            custom_info = executor_info.custom_info
                            if 'total_pnl_quote' in custom_info:
                                pnl_str = f"${custom_info['total_pnl_quote']:.2f}"

                        # Age info
                        age_str = "N/A"
                        if hasattr(executor_info, 'custom_info') and executor_info.custom_info:
                            custom_info = executor_info.custom_info
                            if 'position_age_seconds' in custom_info:
                                age_hours = int(custom_info['position_age_seconds'] // 3600)
                                age_minutes = int((custom_info['position_age_seconds'] % 3600) // 60)
                                age_str = f"{age_hours}h{age_minutes}m"

                        status_str = executor_info.status.name
                        status_lines.append(f"{executor_id:<8} {executor_type:<20} {pnl_str:<10} {age_str:<8} {status_str:<12}")

                    except Exception:
                        status_lines.append(f"{executor_info.id[:8]:<8} {'ERROR':<20} {'N/A':<10} {'N/A':<8} {'ERROR':<12}")

        return status_lines
