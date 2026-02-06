import json
import os
import random
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent, SellOrderCompletedEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WeexVolumeGeneratorConfig(BaseClientModel):
    """
    Configuration for WEEX Volume Generation Strategy

    This strategy ensures minimum daily volume by actively trading,
    alternating between buy and sell to maintain neutral inventory.
    """
    script_file_name: str = os.path.basename(__file__)

    # Exchange Configuration
    exchange: str = Field(default="weex", description="Exchange name")
    trading_pair: str = Field(default="VCC-USDT", description="Trading pair")

    # Volume Targets
    daily_volume_target_usdt: Decimal = Field(
        default=Decimal("10000"),
        description="Minimum daily volume target in USDT"
    )
    trade_interval_seconds: int = Field(
        default=300,  # 5 minutes
        description="Seconds between trades (288 trades per day at 300s)"
    )

    # Order Configuration
    order_size_usdt: Decimal = Field(
        default=Decimal("35"),  # 10000 / 288 ≈ 35
        description="Target order size in USDT per trade (before randomization)"
    )
    order_size_variance: Decimal = Field(
        default=Decimal("0.3"),  # 30%
        description="Random variance in order size (0.3 = ±30% from target)"
    )
    order_type: str = Field(
        default="market",
        description="Order type: 'market' (recommended) or 'limit_cross_spread'"
    )

    # Interval Randomization
    trade_interval_jitter: Decimal = Field(
        default=Decimal("0.4"),  # 40%
        description="Random jitter on trade interval (0.4 = ±40% variation)"
    )

    # Spread Crossing Configuration (for limit orders that ensure fill)
    cross_spread_buffer: Decimal = Field(
        default=Decimal("0.002"),  # 0.2%
        description="How far beyond best bid/ask to place limit orders (0.002 = 0.2%)"
    )

    # Inventory Management
    max_inventory_deviation: Decimal = Field(
        default=Decimal("250000"),  # ~$37.5 at $0.00015
        description="Maximum deviation from starting inventory in base asset"
    )
    rebalance_threshold: Decimal = Field(
        default=Decimal("150000"),  # ~$22.5 at $0.00015
        description="Inventory deviation that triggers rebalancing"
    )

    # Safety
    max_price_deviation: Decimal = Field(
        default=Decimal("0.05"),  # 5%
        description="Max allowed price deviation from reference price"
    )


class WeexVolumeGenerator(ScriptStrategyBase):
    """
    WEEX Volume Generation Strategy

    Ensures minimum daily trading volume by:
    1. Placing regular trades at fixed intervals
    2. Alternating buy/sell to maintain neutral inventory
    3. Crossing the spread to guarantee fills
    4. Tracking daily volume progress

    This is designed for volume requirements, not profit generation.
    """

    price_source = PriceType.MidPrice

    @classmethod
    def init_markets(cls, config: WeexVolumeGeneratorConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: WeexVolumeGeneratorConfig):
        super().__init__(connectors)
        self.config = config
        # Initialize timestamps as instance variables to avoid class-level sharing
        self.create_timestamp = 0.0
        self.last_reset_date = datetime.now().date()

        # Volume tracking (instance variables)
        self.daily_volume_usdt = Decimal("0")
        self.total_volume_usdt = Decimal("0")
        self.trades_today = 0
        self._filled_order_ids = set()
        self._order_meta = {}

        # Inventory tracking (instance variables)
        self.starting_base_balance = None
        self.current_inventory_deviation = Decimal("0")

        # Trade alternation (instance variable)
        self.next_trade_is_buy = True

        # Monitor health file path
        self.monitor_health_file = "/home/hummingbot/health/weex_vol_health.json"
        self.last_health_check = 0.0
        self.health_check_interval = 5.0  # Check health every 5 seconds
        # Create health file on startup if monitor isn't running
        self._initialize_health_file()

        # Stochastic behavior tracking
        self._last_scheduled_interval = self.config.trade_interval_seconds

    def on_tick(self):
        """
        Called every tick. Places trades at configured intervals to meet volume targets.
        """
        # Check monitor health status
        if not self._check_monitor_health():
            return  # Skip this tick if monitor signals pause

        # Reset daily counters at midnight
        self._check_daily_reset()

        # Check if it's time to trade
        if self.create_timestamp <= self.current_timestamp:
            # Initialize starting balance if needed
            if self.starting_base_balance is None:
                self._initialize_starting_balance()

            # Calculate current inventory deviation
            self._update_inventory_deviation()

            # Determine trade direction (buy/sell)
            trade_side = self._determine_trade_direction()

            # Create and place order
            if self.ready_to_trade:
                order = self._create_volume_order(trade_side)
                if order:
                    if trade_side == TradeType.BUY:
                        order_id = self.buy(
                            connector_name=self.config.exchange,
                            trading_pair=self.config.trading_pair,
                            amount=order.amount,
                            order_type=order.order_type,
                            price=order.price
                        )
                    else:
                        order_id = self.sell(
                            connector_name=self.config.exchange,
                            trading_pair=self.config.trading_pair,
                            amount=order.amount,
                            order_type=order.order_type,
                            price=order.price
                        )
                    if order_id:
                        self._order_meta[order_id] = {
                            "amount": order.amount,
                            "price": order.price,
                        }
                    self.trades_today += 1
                    self.logger().info(
                        f"Placed volume generation order #{self.trades_today}: "
                        f"{'BUY' if trade_side == TradeType.BUY else 'SELL'} "
                        f"${float(self.config.order_size_usdt):.2f}"
                    )

            # Schedule next trade with stochastic jitter
            self.create_timestamp = self.current_timestamp + self._get_randomized_interval()

    def _check_daily_reset(self):
        """Reset volume counters at midnight"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.logger().info(
                f"Daily volume completed: ${float(self.daily_volume_usdt):.2f} USDT "
                f"({self.trades_today} trades)"
            )
            self.daily_volume_usdt = Decimal("0")
            self.trades_today = 0
            self.last_reset_date = current_date
            self.starting_base_balance = None  # Reset for new day

    def _initialize_starting_balance(self):
        """Set the starting base balance for inventory tracking"""
        connector = self.connectors[self.config.exchange]
        base_asset = self.config.trading_pair.split("-")[0]
        self.starting_base_balance = connector.get_available_balance(base_asset)
        self.logger().info(f"Starting base balance: {float(self.starting_base_balance):.2f} {base_asset}")

    def _update_inventory_deviation(self):
        """Calculate how far current inventory is from starting balance"""
        connector = self.connectors[self.config.exchange]
        base_asset = self.config.trading_pair.split("-")[0]
        current_balance = connector.get_available_balance(base_asset)
        self.current_inventory_deviation = current_balance - self.starting_base_balance

    def _determine_trade_direction(self) -> TradeType:
        """
        Determine whether to buy or sell based on:
        1. Inventory deviation (prioritize rebalancing)
        2. Probabilistic alternation with stochastic bias (default behavior)
        """
        # If inventory deviation is large, prioritize rebalancing
        if abs(self.current_inventory_deviation) > self.config.rebalance_threshold:
            if self.current_inventory_deviation > 0:
                # Too much base asset, need to sell
                return TradeType.SELL
            else:
                # Too little base asset, need to buy
                return TradeType.BUY

        # Otherwise, use probabilistic alternation to avoid obvious patterns
        # Slight bias toward next_trade_is_buy, but sometimes break the pattern
        if random.random() < 0.85:  # 85% of the time follow pattern, 15% time break it for randomness
            if self.next_trade_is_buy:
                self.next_trade_is_buy = False
                return TradeType.BUY
            else:
                self.next_trade_is_buy = True
                return TradeType.SELL
        else:
            # Break the pattern occasionally for more natural behavior
            trade = TradeType.SELL if self.next_trade_is_buy else TradeType.BUY
            return trade

    def _create_volume_order(self, trade_side: TradeType) -> OrderCandidate:
        """
        Create a market order that hits the MM orders on the other side.
        Uses randomized amounts and market execution for natural trading patterns.
        """
        connector = self.connectors[self.config.exchange]

        # Get current market price
        mid_price = connector.get_price_by_type(self.config.trading_pair, PriceType.MidPrice)

        # Safety check: verify price is reasonable
        if not self._is_price_reasonable(mid_price):
            self.logger().warning(f"Price {mid_price} seems abnormal, skipping this trade")
            return None

        # Calculate randomized order amount to avoid obvious patterns
        # Keep amounts comparable to MM order sizes (typically 200k-250k VCC)
        randomized_size_usdt = self._get_randomized_order_size()
        order_amount = randomized_size_usdt / mid_price
        order_amount = connector.quantize_order_amount(self.config.trading_pair, order_amount)

        # Check if we have sufficient balance
        if not self._check_sufficient_balance(trade_side, order_amount, mid_price):
            self.logger().warning(f"Insufficient balance for {'buy' if trade_side == TradeType.BUY else 'sell'} order")
            return None

        # Use market orders to hit the MM orders naturally
        # This is more realistic trading behavior vs. crossing the spread
        order_type = OrderType.MARKET if self.config.order_type == "market" else OrderType.LIMIT

        if order_type == OrderType.MARKET:
            # Market orders: use mid price for reference
            price = mid_price
        else:
            # Limit orders: cross spread for guaranteed fill
            if trade_side == TradeType.BUY:
                best_ask = connector.get_price_by_type(self.config.trading_pair, PriceType.BestAsk)
                price = best_ask * (Decimal("1") + self.config.cross_spread_buffer)
            else:
                best_bid = connector.get_price_by_type(self.config.trading_pair, PriceType.BestBid)
                price = best_bid * (Decimal("1") - self.config.cross_spread_buffer)
            price = connector.quantize_order_price(self.config.trading_pair, price)

        return OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=False,
            order_type=order_type,
            order_side=trade_side,
            amount=order_amount,
            price=price
        )

    def _is_price_reasonable(self, current_price: Decimal) -> bool:
        """Safety check to avoid trading at abnormal prices"""
        # TODO: Could store a reference price and check deviation
        # For now, just check if price is positive and not zero
        return current_price > 0

    def _get_randomized_order_size(self) -> Decimal:
        """
        Return randomized order size to avoid obvious alternating pattern.
        Keeps amounts comparable to MM order sizes.
        """
        variance_factor = Decimal(str(random.uniform(
            float(1 - self.config.order_size_variance),
            float(1 + self.config.order_size_variance)
        )))
        randomized_size = self.config.order_size_usdt * variance_factor
        return randomized_size

    def _get_randomized_interval(self) -> int:
        """
        Return randomized trade interval with stochastic jitter.
        Adds variation to make trades less predictable.
        """
        jitter_factor = random.uniform(
            float(1 - self.config.trade_interval_jitter),
            float(1 + self.config.trade_interval_jitter)
        )
        randomized_interval = int(self.config.trade_interval_seconds * jitter_factor)
        # Ensure minimum 10 second interval to avoid too-frequent trades
        return max(10, randomized_interval)

    def _initialize_health_file(self):
        """Create health file directory and initialize health file if it doesn't exist."""
        try:
            health_dir = os.path.dirname(self.monitor_health_file)
            if not os.path.exists(health_dir):
                os.makedirs(health_dir, exist_ok=True)

            # Create initial health file if monitor hasn't created it
            if not os.path.exists(self.monitor_health_file):
                initial_health = {
                    "healthy": True,
                    "pause_requested": False,
                    "issues": [],
                    "last_update": int(time.time())
                }
                with open(self.monitor_health_file, 'w') as f:
                    json.dump(initial_health, f)
        except Exception as e:
            self.logger().warning(f"Could not initialize health file: {e}")

    def _check_monitor_health(self) -> bool:
        """
        Check if the external monitor is signaling to pause trading.
        Returns True if trading should continue, False if it should pause.
        """
        # Only check periodically to avoid excessive file reads
        if self.current_timestamp - self.last_health_check < self.health_check_interval:
            return True  # Assume healthy if recently checked

        self.last_health_check = self.current_timestamp

        try:
            if os.path.exists(self.monitor_health_file):
                with open(self.monitor_health_file, 'r') as f:
                    health_data = json.load(f)

                if health_data.get("status") == "paused":
                    self.logger().warning("[MONITOR] Trading paused by external monitor")
                    return False

                if health_data.get("status") == "error":
                    self.logger().error(f"[MONITOR] Error state: {health_data.get('message', 'Unknown error')}")
                    return False
        except Exception as e:
            self.logger().debug(f"Could not read monitor health file: {e}")

        return True  # Continue trading by default

    def _check_sufficient_balance(self, trade_side: TradeType, amount: Decimal, price: Decimal) -> bool:
        """Check if we have enough balance for the trade"""
        connector = self.connectors[self.config.exchange]
        base_asset = self.config.trading_pair.split("-")[0]
        quote_asset = self.config.trading_pair.split("-")[1]

        if trade_side == TradeType.BUY:
            # Need quote asset (USDT)
            required = amount * price
            available = connector.get_available_balance(quote_asset)
            return available >= required
        else:
            # Need base asset
            available = connector.get_available_balance(base_asset)
            return available >= amount

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """Track volume when buy orders complete"""
        if event.order_id in self._filled_order_ids:
            return
        volume_usdt = event.quote_asset_amount
        if volume_usdt <= 0:
            meta = self._order_meta.pop(event.order_id, None)
            if meta is not None and meta["price"] is not None:
                volume_usdt = meta["amount"] * meta["price"]
        if volume_usdt > 0:
            self.daily_volume_usdt += volume_usdt
            self.total_volume_usdt += volume_usdt

            progress = (self.daily_volume_usdt / self.config.daily_volume_target_usdt) * 100
            self.logger().info(
                f"Buy completed: ${float(volume_usdt):.2f} | "
                f"Daily: ${float(self.daily_volume_usdt):.2f} / ${float(self.config.daily_volume_target_usdt):.2f} "
                f"({float(progress):.1f}%)"
            )

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """Track volume when sell orders complete"""
        if event.order_id in self._filled_order_ids:
            return
        volume_usdt = event.quote_asset_amount
        if volume_usdt <= 0:
            meta = self._order_meta.pop(event.order_id, None)
            if meta is not None and meta["price"] is not None:
                volume_usdt = meta["amount"] * meta["price"]
        if volume_usdt > 0:
            self.daily_volume_usdt += volume_usdt
            self.total_volume_usdt += volume_usdt

            progress = (self.daily_volume_usdt / self.config.daily_volume_target_usdt) * 100
            self.logger().info(
                f"Sell completed: ${float(volume_usdt):.2f} | "
                f"Daily: ${float(self.daily_volume_usdt):.2f} / ${float(self.config.daily_volume_target_usdt):.2f} "
                f"({float(progress):.1f}%)"
            )

    def did_fill_order(self, event: OrderFilledEvent):
        """Track volume from fills (more reliable than completed events on WEEX)."""
        volume_usdt = event.amount * event.price
        self.daily_volume_usdt += volume_usdt
        self.total_volume_usdt += volume_usdt
        self._filled_order_ids.add(event.order_id)
        self._order_meta.pop(event.order_id, None)

        progress = (self.daily_volume_usdt / self.config.daily_volume_target_usdt) * 100
        self.logger().info(
            f"{'Buy' if event.trade_type == TradeType.BUY else 'Sell'} fill: ${float(volume_usdt):.2f} | "
            f"Daily: ${float(self.daily_volume_usdt):.2f} / ${float(self.config.daily_volume_target_usdt):.2f} "
            f"({float(progress):.1f}%)"
        )

    def format_status(self) -> str:
        """Display strategy status"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        lines.append("\n  WEEX Volume Generation Status")
        lines.append("  " + "=" * 50)

        # Market info
        mid_price = self.connectors[self.config.exchange].get_price_by_type(
            self.config.trading_pair,
            PriceType.MidPrice
        )
        lines.append(f"  Market: {self.config.trading_pair}")
        lines.append(f"  Price: ${float(mid_price):.8f}")

        # Volume progress
        progress = (self.daily_volume_usdt / self.config.daily_volume_target_usdt) * 100
        lines.append(f"\n  Volume Target: ${float(self.config.daily_volume_target_usdt):.2f} USDT/day")
        lines.append(f"  Today's Volume: ${float(self.daily_volume_usdt):.2f} ({float(progress):.1f}%)")
        lines.append(f"  Trades Today: {self.trades_today}")

        remaining_volume = self.config.daily_volume_target_usdt - self.daily_volume_usdt
        if remaining_volume > 0:
            trades_remaining = int(remaining_volume / self.config.order_size_usdt) + 1
            time_remaining = trades_remaining * self.config.trade_interval_seconds / 3600
            lines.append(f"  Remaining: ${float(remaining_volume):.2f} (~{trades_remaining} trades, ~{time_remaining:.1f}h)")
        else:
            lines.append("  ✓ Daily target achieved!")

        # Inventory status
        if self.starting_base_balance is not None:
            base_asset = self.config.trading_pair.split("-")[0]
            deviation_usdt = self.current_inventory_deviation * mid_price
            lines.append(f"\n  Inventory Deviation: {float(self.current_inventory_deviation):.2f} {base_asset} (${float(deviation_usdt):.2f})")

            if abs(self.current_inventory_deviation) > self.config.rebalance_threshold:
                lines.append(f"  ⚠ Rebalancing mode: will {'SELL' if self.current_inventory_deviation > 0 else 'BUY'}")

        # Next trade info
        next_trade_in = max(0, int(self.create_timestamp - self.current_timestamp))
        lines.append(f"\n  Next Trade: {'BUY' if self.next_trade_is_buy else 'SELL'} in {next_trade_in}s")
        lines.append(f"  Order Size: ${float(self.config.order_size_usdt):.2f} USDT")
        lines.append(f"  Interval: {self.config.trade_interval_seconds}s ({288 if self.config.trade_interval_seconds == 300 else int(86400 / self.config.trade_interval_seconds)} trades/day)")

        # Balances
        base_asset = self.config.trading_pair.split("-")[0]
        quote_asset = self.config.trading_pair.split("-")[1]
        base_balance = self.connectors[self.config.exchange].get_available_balance(base_asset)
        quote_balance = self.connectors[self.config.exchange].get_available_balance(quote_asset)
        lines.append("\n  Balances:")
        lines.append(f"    {base_asset}: {float(base_balance):.2f}")
        lines.append(f"    {quote_asset}: ${float(quote_balance):.2f}")

        return "\n".join(lines)


# Create singleton config instance
CREATE_COMMAND_EXAMPLE = """
To use this strategy:
1. import weex_volume_generator
2. Adjust config if needed (default: $10k/day target, 5min intervals)
3. start
"""
