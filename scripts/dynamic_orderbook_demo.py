import asyncio
import os
from decimal import Decimal
from typing import Dict, List, Optional, Set

from pydantic import Field, field_validator

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class DynamicOrderbookDemoConfig(StrategyV2ConfigBase):
    """
    Configuration for the Dynamic Orderbook Demo  strategy.

    This strategy demonstrates dynamic order book initialization and removal.
    It uses one connector for the strategy (markets) but can display
    order books from a different exchange (order_book_exchange).
    """
    script_file_name: str = Field(default=os.path.basename(__file__))

    # Required by StrategyV2ConfigBase - provide defaults
    markets: Dict[str, Set[str]] = Field(default={"binance_paper_trade": {"BTC-USDT"}})
    candles_config: List[CandlesConfig] = Field(default=[])
    controllers_config: List[str] = Field(default=[])

    # Exchange to use for order book data (can be different from trading exchange)
    order_book_exchange: str = Field(
        default="binance_perpetual",
        json_schema_extra={
            "prompt": lambda mi: "Enter exchange for order book data (e.g., binance_perpetual, bybit_perpetual): ",
            "prompt_on_new": True
        }
    )

    # Trading pairs to add dynamically (comma-separated string that gets parsed to Set)
    add_trading_pairs: Set[str] = Field(
        default="SOL-USDT,ETH-USDT",
        json_schema_extra={
            "prompt": lambda mi: "Enter trading pairs to add dynamically (comma-separated, e.g., SOL-USDT,ETH-USDT): ",
            "prompt_on_new": True
        }
    )

    # Trading pairs to remove dynamically (must be subset of add_trading_pairs)
    remove_trading_pairs: Set[str] = Field(
        default="SOL-USDT,ETH-USDT",
        json_schema_extra={
            "prompt": lambda mi: "Enter trading pairs to remove dynamically (comma-separated, e.g., SOL-USDT,ETH-USDT): ",
            "prompt_on_new": True
        }
    )

    # Timing configuration (in seconds)
    add_pairs_delay: float = Field(
        default=10.0,
        gt=0,
        json_schema_extra={
            "prompt": lambda mi: "Enter seconds before adding pairs (e.g., 10): ",
            "prompt_on_new": True
        }
    )
    remove_pairs_delay: float = Field(
        default=25.0,
        gt=0,
        json_schema_extra={
            "prompt": lambda mi: "Enter seconds before removing pairs (e.g., 25): ",
            "prompt_on_new": True
        }
    )

    # Display configuration
    order_book_depth: int = Field(default=5, gt=0, description="Number of order book levels to display")
    histogram_range_bps: int = Field(default=50, gt=0, description="Basis points range for depth chart (±bps from mid)")
    chart_height: int = Field(default=12, gt=0, description="Height of depth chart in rows")

    @field_validator('add_trading_pairs', 'remove_trading_pairs', mode="before")
    @classmethod
    def parse_trading_pairs(cls, v) -> Set[str]:
        """Parse comma-separated string into a set of trading pairs."""
        if isinstance(v, str):
            if not v.strip():
                return set()
            return {pair.strip() for pair in v.split(',') if pair.strip()}
        elif isinstance(v, (set, list)):
            return set(v)
        return v


class DynamicOrderbookDemo(StrategyV2Base):
    """
    V2 Demo strategy showing dynamic order book initialization and removal.

    The strategy uses one connector for trading (markets) but can display
    order books from a different exchange (order_book_exchange).

    Timeline:
    - Starts with initial markets configuration
    - Adds pairs from add_trading_pairs after add_pairs_delay seconds
    - Removes pairs from remove_trading_pairs after remove_pairs_delay seconds

    Order book data is displayed in format_status() (use `status` command to view).

    For perpetual connectors, the strategy also:
    - Displays funding info (mark price, index price, funding rate) for each pair
    - Validates that funding info is properly initialized when pairs are added
    - Validates that funding info is properly cleaned up when pairs are removed
    """

    # Default markets when running without a config file
    markets: Dict[str, Set[str]] = {"binance_paper_trade": {"BTC-USDT"}}

    @classmethod
    def init_markets(cls, config: DynamicOrderbookDemoConfig):
        """Initialize the markets for the strategy."""
        cls.markets = dict(config.markets)

    def __init__(self, connectors: Dict[str, ConnectorBase], config: Optional[DynamicOrderbookDemoConfig] = None):
        # Create default config if none provided (when running without --conf flag)
        if config is None:
            config = DynamicOrderbookDemoConfig()
        super().__init__(connectors, config)
        self.config: DynamicOrderbookDemoConfig = config
        self._start_timestamp: Optional[float] = None
        self._pairs_added: Set[str] = set()
        self._pairs_removed: Set[str] = set()

    def start(self, clock: Clock, timestamp: float) -> None:
        """Start the strategy."""
        super().start(clock, timestamp)
        self._start_timestamp = timestamp
        self.logger().info(
            f"DynamicOrderbookDemo started. "
            f"Order book exchange: {self.config.order_book_exchange}, "
            f"Add pairs: {self.config.add_trading_pairs}, "
            f"Remove pairs: {self.config.remove_trading_pairs}"
        )

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """This demo doesn't create any executors."""
        return []

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """This demo doesn't stop any executors."""
        return []

    def on_tick(self):
        """Handle tick events - manage dynamic pair addition/removal."""
        super().on_tick()

        if self._start_timestamp is None:
            self._start_timestamp = self.current_timestamp

        elapsed = self.current_timestamp - self._start_timestamp

        # Add trading pairs after add_pairs_delay
        if elapsed >= self.config.add_pairs_delay:
            for pair in self.config.add_trading_pairs:
                if pair not in self._pairs_added:
                    self._pairs_added.add(pair)
                    self.logger().info(f">>> ADDING {pair} ORDER BOOK <<<")
                    asyncio.create_task(self._add_trading_pair(pair))

        # Remove trading pairs after remove_pairs_delay
        if elapsed >= self.config.remove_pairs_delay:
            for pair in self.config.remove_trading_pairs:
                if pair not in self._pairs_removed and pair in self._pairs_added:
                    self._pairs_removed.add(pair)
                    self.logger().info(f">>> REMOVING {pair} ORDER BOOK <<<")
                    asyncio.create_task(self._remove_trading_pair(pair))

    def format_status(self) -> str:
        """Display order book information for all tracked trading pairs."""
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        elapsed = self.current_timestamp - self._start_timestamp if self._start_timestamp else 0

        lines.append("\n" + "=" * 80)
        lines.append(f"  DYNAMIC ORDER BOOK DEMO | Exchange: {self.config.order_book_exchange} | Elapsed: {elapsed:.1f}s")
        lines.append("=" * 80)

        # Timeline status
        lines.append("\n  Timeline:")
        add_pairs_str = ", ".join(self.config.add_trading_pairs) if self.config.add_trading_pairs else "None"
        remove_pairs_str = ", ".join(self.config.remove_trading_pairs) if self.config.remove_trading_pairs else "None"
        all_added = self.config.add_trading_pairs <= self._pairs_added
        all_removed = self.config.remove_trading_pairs <= self._pairs_removed

        lines.append(
            f"    [{'✓' if all_added else '○'}] {self.config.add_pairs_delay:.0f}s - Add {add_pairs_str}"
            + (" (added)" if all_added else "")
        )
        lines.append(
            f"    [{'✓' if all_removed else '○'}] {self.config.remove_pairs_delay:.0f}s - Remove {remove_pairs_str}"
            + (" (removed)" if all_removed else "")
        )

        # Check if the non-trading connector has been started
        connector = self.market_data_provider.get_connector_with_fallback(self.config.order_book_exchange)
        is_started = self.market_data_provider._non_trading_connectors_started.get(
            self.config.order_book_exchange, False
        ) if self.config.order_book_exchange not in self.market_data_provider.connectors else True

        if not is_started:
            lines.append("\n  Waiting for first trading pair to be added...")
            lines.append(f"  (Order book connector will start at {self.config.add_pairs_delay:.0f}s)")
            lines.append("\n" + "=" * 80)
            return "\n".join(lines)

        # Get tracked pairs from order book tracker
        tracker = connector.order_book_tracker
        tracked_pairs = list(tracker.order_books.keys())
        lines.append(f"\n  Tracked Pairs: {tracked_pairs}")

        if not tracked_pairs:
            lines.append("\n  No order books currently tracked.")
            lines.append("\n" + "=" * 80)
            return "\n".join(lines)

        # Display order book for each pair
        for pair in tracked_pairs:
            lines.append("\n" + "-" * 80)
            lines.extend(self._format_order_book(connector, pair))

        # Display funding info for perpetual connectors
        if self._is_perpetual_connector(connector):
            lines.append("\n" + "-" * 80)
            lines.append("  FUNDING INFO (Perpetual Connector)")
            lines.append("-" * 80)
            lines.extend(self._format_funding_info(connector, tracked_pairs))

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)

    def _format_order_book(self, connector, trading_pair: str) -> List[str]:
        """Format order book data for a single trading pair with horizontal depth chart."""
        lines = []

        try:
            ob = connector.order_book_tracker.order_books.get(trading_pair)
            if ob is None:
                lines.append(f"  {trading_pair}: Order book not yet initialized...")
                return lines

            bids_df, asks_df = ob.snapshot

            if len(bids_df) == 0 or len(asks_df) == 0:
                lines.append(f"  {trading_pair}: Order book empty or initializing...")
                return lines

            # Calculate market metrics
            best_bid = float(bids_df.iloc[0].price)
            best_ask = float(asks_df.iloc[0].price)
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            mid_price = (best_bid + best_ask) / 2

            # Header with market info
            lines.append(f"  {trading_pair}")
            lines.append(f"  Mid: {mid_price:.4f} | Spread: {spread:.4f} ({spread_pct:.4f}%)")
            lines.append("")

            # Prepare order book display
            depth = min(self.config.order_book_depth, len(bids_df), len(asks_df))

            # Order book table
            lines.append(f"  {'Bid Size':>12} {'Bid Price':>14} │ {'Ask Price':<14} {'Ask Size':<12}")
            lines.append(f"  {'-' * 12} {'-' * 14} │ {'-' * 14} {'-' * 12}")

            for i in range(depth):
                bid_price = float(bids_df.iloc[i].price)
                bid_size = float(bids_df.iloc[i].amount)
                ask_price = float(asks_df.iloc[i].price)
                ask_size = float(asks_df.iloc[i].amount)
                lines.append(f"  {bid_size:>12.4f} {bid_price:>14.4f} │ {ask_price:<14.4f} {ask_size:<12.4f}")

            # Total volume at displayed levels
            total_bid_vol = float(bids_df.iloc[:depth]['amount'].sum())
            total_ask_vol = float(asks_df.iloc[:depth]['amount'].sum())
            lines.append(f"  {'-' * 12} {'-' * 14} │ {'-' * 14} {'-' * 12}")
            lines.append(f"  {'Total:':>12} {total_bid_vol:>14.4f} │ {total_ask_vol:<14.4f}")

            # Add horizontal depth chart below
            lines.extend(self._build_horizontal_depth_chart(bids_df, asks_df, mid_price))

        except Exception as e:
            lines.append(f"  {trading_pair}: Error - {e}")

        return lines

    def _build_horizontal_depth_chart(self, bids_df, asks_df, mid_price: float) -> List[str]:
        """
        Build ASCII depth chart with bps on X-axis and volume on Y-axis.
        1 bar per bps, bids on left, asks on right.
        """
        lines = []
        num_buckets = self.config.histogram_range_bps  # 1 bucket per bps
        range_decimal = self.config.histogram_range_bps / 10000
        bucket_size_decimal = range_decimal / num_buckets

        # Aggregate bid volume into buckets (1 per bps, from mid going down)
        bid_buckets = []
        for i in range(num_buckets):
            bucket_upper = mid_price * (1 - i * bucket_size_decimal)
            bucket_lower = mid_price * (1 - (i + 1) * bucket_size_decimal)
            mask = (bids_df['price'] <= bucket_upper) & (bids_df['price'] > bucket_lower)
            vol = float(bids_df[mask]['amount'].sum()) if mask.any() else 0
            bid_buckets.append(vol)

        # Aggregate ask volume into buckets (1 per bps, from mid going up)
        ask_buckets = []
        for i in range(num_buckets):
            bucket_lower = mid_price * (1 + i * bucket_size_decimal)
            bucket_upper = mid_price * (1 + (i + 1) * bucket_size_decimal)
            mask = (asks_df['price'] >= bucket_lower) & (asks_df['price'] < bucket_upper)
            vol = float(asks_df[mask]['amount'].sum()) if mask.any() else 0
            ask_buckets.append(vol)

        # Find max volume for scaling
        all_vols = bid_buckets + ask_buckets
        max_vol = max(all_vols) if all_vols and max(all_vols) > 0 else 1

        # Calculate totals and imbalance
        total_bid_vol = sum(bid_buckets)
        total_ask_vol = sum(ask_buckets)
        total_vol = total_bid_vol + total_ask_vol
        imbalance_pct = ((total_bid_vol - total_ask_vol) / total_vol * 100) if total_vol > 0 else 0
        imbalance_str = f"+{imbalance_pct:.1f}%" if imbalance_pct >= 0 else f"{imbalance_pct:.1f}%"

        # Calculate bar heights
        chart_height = self.config.chart_height
        bid_heights = [int((v / max_vol) * chart_height) for v in bid_buckets]
        ask_heights = [int((v / max_vol) * chart_height) for v in ask_buckets]

        # Reverse bids so furthest from mid is on left
        bid_heights_display = list(reversed(bid_heights))

        # Header with summary
        lines.append("")
        lines.append(f"  Depth Chart (±{self.config.histogram_range_bps} bps)")
        lines.append(f"  Bids: {total_bid_vol:,.2f}  |  Asks: {total_ask_vol:,.2f}  |  Imbalance: {imbalance_str}")
        lines.append("")

        # Build chart row by row from top to bottom
        for row in range(chart_height, 0, -1):
            row_chars = []

            # Bid bars (left side)
            for h in bid_heights_display:
                if h >= row:
                    row_chars.append("█")
                else:
                    row_chars.append(" ")

            # Center divider
            row_chars.append("│")

            # Ask bars (right side)
            for h in ask_heights:
                if h >= row:
                    row_chars.append("█")
                else:
                    row_chars.append(" ")

            lines.append("  " + "".join(row_chars))

        # X-axis line
        lines.append("  " + "─" * num_buckets + "┴" + "─" * num_buckets)

        # X-axis labels (sparse - every 10 bps)
        label_interval = 10
        # Build label line with proper spacing
        bid_label_line = [" "] * num_buckets
        ask_label_line = [" "] * num_buckets

        # Place bid labels (negative values, from left to right: -50, -40, -30, -20, -10)
        for bps in range(self.config.histogram_range_bps, 0, -label_interval):
            pos = self.config.histogram_range_bps - bps  # Position from left
            label = f"-{bps}"
            # Center the label at this position
            start = max(0, pos - len(label) // 2)
            for j, ch in enumerate(label):
                if start + j < num_buckets:
                    bid_label_line[start + j] = ch

        # Place ask labels (positive values, from left to right: 10, 20, 30, 40, 50)
        for bps in range(label_interval, self.config.histogram_range_bps + 1, label_interval):
            pos = bps - 1  # Position from left (0-indexed)
            label = f"+{bps}"
            start = max(0, pos - len(label) // 2)
            for j, ch in enumerate(label):
                if start + j < num_buckets:
                    ask_label_line[start + j] = ch

        lines.append("  " + "".join(bid_label_line) + "0" + "".join(ask_label_line) + "  (bps)")

        return lines

    def _is_perpetual_connector(self, connector: ConnectorBase) -> bool:
        """Check if the connector is a perpetual/derivative connector."""
        return isinstance(connector, PerpetualDerivativePyBase)

    def _format_funding_info(self, connector: ConnectorBase, trading_pairs: List[str]) -> List[str]:
        """Format funding info for perpetual connectors."""
        lines = []

        if not self._is_perpetual_connector(connector):
            lines.append("  Not a perpetual connector - funding info N/A")
            return lines

        # Get the perpetual trading instance
        perpetual_trading = connector._perpetual_trading
        funding_info_dict = perpetual_trading.funding_info

        lines.append("")
        lines.append(f"  {'Trading Pair':<16} {'Mark Price':>14} {'Index Price':>14} {'Funding Rate':>14} {'Status':<12}")
        lines.append(f"  {'-' * 16} {'-' * 14} {'-' * 14} {'-' * 14} {'-' * 12}")

        for pair in trading_pairs:
            try:
                funding_info: Optional[FundingInfo] = funding_info_dict.get(pair)
                if funding_info is None:
                    lines.append(f"  {pair:<16} {'N/A':>14} {'N/A':>14} {'N/A':>14} {'NOT INIT':^12}")
                else:
                    mark_price = funding_info.mark_price
                    index_price = funding_info.index_price
                    rate = funding_info.rate
                    # Format rate as percentage (e.g., 0.0001 -> 0.01%)
                    rate_pct = rate * Decimal("100")
                    lines.append(
                        f"  {pair:<16} {mark_price:>14.4f} {index_price:>14.4f} {rate_pct:>13.4f}% {'✓ READY':^12}"
                    )
            except Exception as e:
                lines.append(f"  {pair:<16} Error: {str(e)[:40]}")

        # Summary
        initialized_count = sum(1 for p in trading_pairs if p in funding_info_dict)
        total_count = len(trading_pairs)
        lines.append("")
        lines.append(f"  Funding Info Status: {initialized_count}/{total_count} pairs initialized")

        if initialized_count < total_count:
            missing = [p for p in trading_pairs if p not in funding_info_dict]
            lines.append(f"  Missing: {', '.join(missing)}")

        return lines

    async def _add_trading_pair(self, trading_pair: str):
        """Add a trading pair to the order book tracker."""
        try:
            success = await self.market_data_provider.initialize_order_book(
                self.config.order_book_exchange, trading_pair
            )
            if not success:
                self.logger().error(f"Failed to add {trading_pair} to order book tracker")
                return

            self.logger().info(f"Successfully added {trading_pair}!")

            # Validate funding info for perpetual connectors
            connector = self.market_data_provider.get_connector_with_fallback(self.config.order_book_exchange)
            if self._is_perpetual_connector(connector):
                await self._validate_funding_info(connector, trading_pair)

        except Exception as e:
            self.logger().exception(f"Error adding {trading_pair}: {e}")

    async def _remove_trading_pair(self, trading_pair: str):
        """Remove a trading pair from the order book tracker."""
        try:
            success = await self.market_data_provider.remove_order_book(
                self.config.order_book_exchange, trading_pair
            )
            if not success:
                self.logger().error(f"Failed to remove {trading_pair} from order book tracker")
                return

            self.logger().info(f"Successfully removed {trading_pair}!")

            # Validate funding info cleanup for perpetual connectors
            connector = self.market_data_provider.get_connector_with_fallback(self.config.order_book_exchange)
            if self._is_perpetual_connector(connector):
                perpetual_trading = connector._perpetual_trading
                if trading_pair in perpetual_trading.funding_info:
                    self.logger().warning(f"Funding info for {trading_pair} was NOT cleaned up!")
                else:
                    self.logger().info(f"Funding info for {trading_pair} properly cleaned up")

        except Exception as e:
            self.logger().exception(f"Error removing {trading_pair}: {e}")

    async def _validate_funding_info(self, connector: ConnectorBase, trading_pair: str):
        """Validate that funding info is properly initialized for a trading pair."""
        try:
            perpetual_trading = connector._perpetual_trading
            funding_info_dict = perpetual_trading.funding_info

            if trading_pair not in funding_info_dict:
                self.logger().error(
                    f"FUNDING INFO NOT INITIALIZED for {trading_pair}! "
                    "This indicates the dynamic pair addition didn't properly initialize funding info."
                )
                return

            funding_info = funding_info_dict[trading_pair]
            self.logger().info(
                f"Funding info VALIDATED for {trading_pair}: "
                f"mark_price={funding_info.mark_price:.4f}, "
                f"index_price={funding_info.index_price:.4f}, "
                f"rate={funding_info.rate:.6f}"
            )

            # Also check that the trading pair is in the perpetual trading's trading pairs list
            if trading_pair not in perpetual_trading._trading_pairs:
                self.logger().warning(
                    f"Trading pair {trading_pair} not in perpetual_trading._trading_pairs list"
                )
            else:
                self.logger().info(f"Trading pair {trading_pair} properly added to perpetual trading pairs list")

        except Exception as e:
            self.logger().exception(f"Error validating funding info for {trading_pair}: {e}")
