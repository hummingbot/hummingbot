"""
lp_manage_position_simple.py

Simplified CLMM LP position manager that automatically rebalances positions.

This is a simpler version of lp_manage_position.py that:
- Monitors existing positions or creates new ones with user-specified token amounts
- Automatically rebalances when price moves out of position bounds
- Switches to single-sided liquidity after first rebalance for capital efficiency

BEHAVIOR
--------
- If an existing position exists in the pool, monitors it (does NOT auto-create a new one)
- Monitors price vs. active position's price bounds
- When price is out-of-bounds for >= rebalance_seconds, fully closes the position and re-enters
- First position can be double-sided (if both base_amount and quote_amount provided)
- After first rebalance, all subsequent positions are SINGLE-SIDED (more capital efficient)
- Single-sided positions provide only the token needed based on where price moved

PARAMETERS
----------
- connector: CLMM connector in format 'name/type' (e.g. raydium/clmm, meteora/clmm)
- trading_pair: Trading pair (e.g. SOL-USDC)
- pool_address: Optional pool address (will fetch automatically if not provided)
- base_amount: Initial base token amount (0 for quote-only position)
- quote_amount: Initial quote token amount (0 for base-only position)
  * If both are 0 and no existing position: monitoring only
  * If both provided: creates double-sided initial position
  * After rebalance: only one token provided based on price direction
- position_width_pct: TOTAL position width as percentage of mid price (e.g. 2.0 = ±1%)
- rebalance_seconds: Seconds price must stay out-of-bounds before rebalancing

NOTES
-----
- Simpler alternative to lp_manage_position.py without target price triggers
- All tick rounding and amount calculations delegated to Gateway
- After first rebalance, automatically switches to single-sided positions
"""

import asyncio
import logging
import os
import time
from decimal import Decimal
from typing import Dict, Optional

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_lp import CLMMPoolInfo, CLMMPositionInfo
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LpSimplePositionManagerConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    connector: str = Field("raydium/clmm", json_schema_extra={
        "prompt": "CLMM connector in format 'name/type' (e.g. raydium/clmm, meteora/clmm)", "prompt_on_new": True})
    trading_pair: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "Trading pair (e.g. SOL-USDC)", "prompt_on_new": True})
    pool_address: str = Field("", json_schema_extra={
        "prompt": "Pool address (optional - will fetch automatically if not provided)", "prompt_on_new": False})
    base_amount: Decimal = Field(Decimal("0"), json_schema_extra={
        "prompt": "Initial base token amount (0 for quote-only initial position)", "prompt_on_new": True})
    quote_amount: Decimal = Field(Decimal("0"), json_schema_extra={
        "prompt": "Initial quote token amount (0 for base-only initial position)", "prompt_on_new": True})
    position_width_pct: Decimal = Field(Decimal("2.0"), json_schema_extra={
        "prompt": "TOTAL position width as percentage (e.g. 2.0 for ±1% around mid price)", "prompt_on_new": True})
    rebalance_seconds: int = Field(60, json_schema_extra={
        "prompt": "Seconds price must stay out-of-bounds before rebalancing", "prompt_on_new": True})


class LpSimplePositionManager(ScriptStrategyBase):
    """
    Simplified CLMM LP position manager that automatically rebalances when price moves out of bounds.
    """

    @classmethod
    def init_markets(cls, config: LpSimplePositionManagerConfig):
        cls.markets = {config.connector: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: LpSimplePositionManagerConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = config.connector
        self.connector_type = get_connector_type(config.connector)
        self.base_token, self.quote_token = self.config.trading_pair.split("-")

        # Verify this is a CLMM connector
        if self.connector_type != ConnectorType.CLMM:
            raise ValueError(f"This script only supports CLMM connectors. Got: {config.connector}")

        # State tracking
        self.pool_info: Optional[CLMMPoolInfo] = None
        self.position_info: Optional[CLMMPositionInfo] = None
        self.current_position_id: Optional[str] = None
        self.out_of_bounds_since: Optional[float] = None
        self.has_rebalanced_once: bool = False  # Track if we've done first rebalance

        # Order tracking
        self.pending_open_order_id: Optional[str] = None
        self.pending_close_order_id: Optional[str] = None
        self.pending_operation: Optional[str] = None  # "opening", "closing"

        # Log startup information
        self.log_with_clock(logging.INFO,
                            f"Simple LP Position Manager initialized for {self.config.trading_pair} on {self.exchange}\n"
                            f"Position width: ±{float(self.config.position_width_pct) / 2:.2f}% around mid price\n"
                            f"Rebalance threshold: {self.config.rebalance_seconds} seconds out-of-bounds")

        if self.config.base_amount > 0 or self.config.quote_amount > 0:
            self.log_with_clock(logging.INFO,
                                f"Initial amounts: {self.config.base_amount} {self.base_token} / "
                                f"{self.config.quote_amount} {self.quote_token}")
        else:
            self.log_with_clock(logging.INFO, "No initial amounts - will only monitor existing positions")

        # Check for existing positions on startup
        safe_ensure_future(self.initialize_position())

    async def initialize_position(self):
        """Check for existing positions or create initial position on startup"""
        await asyncio.sleep(3)  # Wait for connector to initialize

        # Fetch pool info first
        await self.fetch_pool_info()

        # Check if user has existing position in this pool
        if await self.check_existing_positions():
            self.logger().info(f"Found existing position {self.current_position_id}, will monitor it")
            return

        # No existing position - create one if user provided amounts
        if self.config.base_amount > 0 or self.config.quote_amount > 0:
            self.logger().info("No existing position found, creating initial position...")
            await self.create_initial_position()
        else:
            self.logger().info("No existing position and no initial amounts provided - monitoring only")

    def on_tick(self):
        """Called on each strategy tick"""
        if self.pending_operation:
            # Operation in progress, wait for confirmation
            return

        if self.current_position_id:
            # Monitor existing position
            safe_ensure_future(self.monitor_and_rebalance())
        else:
            # No position yet, just update pool info
            safe_ensure_future(self.fetch_pool_info())

    async def fetch_pool_info(self):
        """Fetch pool information to get current price"""
        try:
            self.pool_info = await self.connectors[self.exchange].get_pool_info(
                trading_pair=self.config.trading_pair
            )
            return self.pool_info
        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")
            return None

    async def get_pool_address(self) -> Optional[str]:
        """Get pool address from config or fetch from connector"""
        if self.config.pool_address:
            return self.config.pool_address
        else:
            connector = self.connectors[self.exchange]
            return await connector.get_pool_address(self.config.trading_pair)

    async def check_existing_positions(self) -> bool:
        """Check if user has existing positions in this pool"""
        try:
            connector = self.connectors[self.exchange]
            pool_address = await self.get_pool_address()

            if not pool_address:
                return False

            positions = await connector.get_user_positions(pool_address=pool_address)

            if positions and len(positions) > 0:
                # Use the first position found (could be enhanced to let user choose)
                self.position_info = positions[0]
                self.current_position_id = self.position_info.address
                self.logger().info(f"Found existing position: {self.current_position_id}")
                return True

            return False
        except Exception as e:
            self.logger().debug(f"No existing positions found or error checking: {str(e)}")
            return False

    async def update_position_info(self):
        """Fetch the latest position information"""
        if not self.current_position_id:
            return

        try:
            self.position_info = await self.connectors[self.exchange].get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=self.current_position_id
            )

            # Log position details
            if self.position_info:
                self.logger().info(
                    f"{self.exchange} {self.config.trading_pair} position: {self.current_position_id[:8]}... "
                    f"(price: {self.position_info.price:.2f}, "
                    f"range: {self.position_info.lower_price:.2f}-{self.position_info.upper_price:.2f})"
                )

            self.logger().debug(f"Updated position info: {self.position_info}")
        except Exception as e:
            self.logger().error(f"Error updating position info: {str(e)}")

    async def create_initial_position(self):
        """Create initial position (can be double-sided or single-sided)"""
        if self.pending_operation:
            return

        try:
            if not self.pool_info:
                await self.fetch_pool_info()

            if not self.pool_info:
                self.logger().error("Cannot create position without pool info")
                return

            current_price = float(self.pool_info.price)
            lower_pct, upper_pct = self._compute_width_percentages()

            base_amt = float(self.config.base_amount)
            quote_amt = float(self.config.quote_amount)

            if base_amt > 0 and quote_amt > 0:
                self.logger().info(f"Creating double-sided position at price {current_price:.6f} "
                                   f"with range -{lower_pct}% to +{upper_pct}%")
            elif base_amt > 0:
                self.logger().info(f"Creating base-only position at price {current_price:.6f} "
                                   f"with {base_amt} {self.base_token}")
            elif quote_amt > 0:
                self.logger().info(f"Creating quote-only position at price {current_price:.6f} "
                                   f"with {quote_amt} {self.quote_token}")
            else:
                return

            order_id = self.connectors[self.exchange].add_liquidity(
                trading_pair=self.config.trading_pair,
                price=current_price,
                upper_width_pct=upper_pct,
                lower_width_pct=lower_pct,
                base_token_amount=base_amt,
                quote_token_amount=quote_amt,
            )

            self.pending_open_order_id = order_id
            self.pending_operation = "opening"
            self.logger().info(f"Initial position order submitted with ID: {order_id}")

        except Exception as e:
            self.logger().error(f"Error creating initial position: {str(e)}")
            self.pending_operation = None

    async def monitor_and_rebalance(self):
        """Monitor position and rebalance if needed"""
        if not self.current_position_id:
            return

        try:
            # Update position and pool info
            await self.update_position_info()
            await self.fetch_pool_info()

            if not self.pool_info or not self.position_info:
                return

            current_price = Decimal(str(self.pool_info.price))
            lower_price = Decimal(str(self.position_info.lower_price))
            upper_price = Decimal(str(self.position_info.upper_price))

            # Check if price is in bounds
            in_bounds = self._price_in_bounds(current_price, lower_price, upper_price)

            if in_bounds:
                # Price is in bounds
                if self.out_of_bounds_since is not None:
                    self.logger().info("Price moved back into position bounds, resetting timer")
                    self.out_of_bounds_since = None
            else:
                # Price is out of bounds
                current_time = time.time()

                if self.out_of_bounds_since is None:
                    self.out_of_bounds_since = current_time
                    if float(current_price) < float(lower_price):
                        deviation = (float(lower_price) - float(current_price)) / float(lower_price) * 100
                        self.logger().info(f"Price {current_price:.6f} moved below lower bound {lower_price:.6f} by {deviation:.2f}%")
                    else:
                        deviation = (float(current_price) - float(upper_price)) / float(upper_price) * 100
                        self.logger().info(f"Price {current_price:.6f} moved above upper bound {upper_price:.6f} by {deviation:.2f}%")

                elapsed_seconds = current_time - self.out_of_bounds_since

                if elapsed_seconds >= self.config.rebalance_seconds:
                    self.logger().info(f"Price out of bounds for {elapsed_seconds:.0f} seconds (threshold: {self.config.rebalance_seconds})")
                    await self.rebalance_position(current_price, lower_price, upper_price)
                else:
                    self.logger().info(f"Price out of bounds for {elapsed_seconds:.0f}/{self.config.rebalance_seconds} seconds")

        except Exception as e:
            self.logger().error(f"Error in monitor_and_rebalance: {str(e)}")

    async def rebalance_position(self, current_price: Decimal, old_lower: Decimal, old_upper: Decimal):
        """Close current position and open new single-sided position"""
        if self.pending_operation:
            return

        try:
            self.logger().info("Starting rebalance: closing current position...")

            # First, close the current position
            order_id = self.connectors[self.exchange].remove_liquidity(
                trading_pair=self.config.trading_pair,
                position_address=self.current_position_id
            )

            self.pending_close_order_id = order_id
            self.pending_operation = "closing"
            self.logger().info(f"Position close order submitted with ID: {order_id}")

            # Store rebalance info for when close completes
            self._rebalance_info = {
                "current_price": current_price,
                "old_lower": old_lower,
                "old_upper": old_upper,
            }

        except Exception as e:
            self.logger().error(f"Error starting rebalance: {str(e)}")
            self.pending_operation = None

    async def open_rebalanced_position(self):
        """Open new single-sided position after closing old one"""
        try:
            if not hasattr(self, '_rebalance_info'):
                self.logger().error("No rebalance info available")
                return

            info = self._rebalance_info
            current_price = info["current_price"]
            old_lower = info["old_lower"]
            old_upper = info["old_upper"]

            # Determine which side to enter based on where price is relative to old range
            side = self._determine_side(current_price, old_lower, old_upper)

            # Get current pool info for latest price
            await self.fetch_pool_info()
            if not self.pool_info:
                self.logger().error("Cannot open rebalanced position without pool info")
                return

            new_mid_price = float(self.pool_info.price)
            lower_pct, upper_pct = self._compute_width_percentages()

            # For single-sided position, provide amount for only one side
            if side == "base":
                # Price is below range, provide base token only
                # Use all available base tokens (would need to check balance in real implementation)
                base_amt = float(self.config.base_amount)
                quote_amt = 0.0
                self.logger().info(f"Opening base-only position at {new_mid_price:.6f} (price below previous bounds)")
            else:  # quote side
                # Price is above bounds, provide quote token only
                base_amt = 0.0
                quote_amt = float(self.config.quote_amount)
                self.logger().info(f"Opening quote-only position at {new_mid_price:.6f} (price above previous bounds)")

            order_id = self.connectors[self.exchange].add_liquidity(
                trading_pair=self.config.trading_pair,
                price=new_mid_price,
                upper_width_pct=upper_pct,
                lower_width_pct=lower_pct,
                base_token_amount=base_amt,
                quote_token_amount=quote_amt,
            )

            self.pending_open_order_id = order_id
            self.pending_operation = "opening"
            self.has_rebalanced_once = True
            self.logger().info(f"Rebalanced {side}-only position order submitted with ID: {order_id}")

            # Clean up rebalance info
            delattr(self, '_rebalance_info')

        except Exception as e:
            self.logger().error(f"Error opening rebalanced position: {str(e)}")
            self.pending_operation = None

    def _compute_width_percentages(self):
        """Compute upper and lower width percentages from total position width"""
        # position_width_pct is TOTAL width, so each side gets half
        half_width = float(self.config.position_width_pct) / 2.0
        return half_width, half_width

    @staticmethod
    def _price_in_bounds(price: Decimal, lower: Decimal, upper: Decimal) -> bool:
        """Check if price is within position bounds"""
        return lower <= price <= upper

    @staticmethod
    def _determine_side(price: Decimal, lower: Decimal, upper: Decimal) -> str:
        """Determine which side to provide liquidity based on price position"""
        if price < lower:
            return "base"
        elif price > upper:
            return "quote"
        else:
            # Should not happen when rebalancing, but default to base
            return "base"

    async def fetch_position_info_after_fill(self):
        """Fetch position info after position is created"""
        try:
            await asyncio.sleep(2)  # Wait for position to be created on-chain

            connector = self.connectors[self.exchange]
            pool_address = await self.get_pool_address()

            if pool_address:
                positions = await connector.get_user_positions(pool_address=pool_address)
                if positions:
                    # Get the most recent position
                    self.position_info = positions[-1]
                    self.current_position_id = self.position_info.address
                    self.logger().info(f"Position info fetched: {self.current_position_id}")
        except Exception as e:
            self.logger().error(f"Error fetching position info after fill: {str(e)}")

    def did_fill_order(self, event):
        """Called when an order is filled"""
        # Check if this is our position opening order
        if hasattr(event, 'order_id') and event.order_id == self.pending_open_order_id:
            self.logger().info(f"Position opening order {event.order_id} confirmed!")

            # Fetch the new position info
            safe_ensure_future(self.fetch_position_info_after_fill())

            # Clear pending state
            self.pending_open_order_id = None
            self.pending_operation = None
            self.out_of_bounds_since = None  # Reset out-of-bounds timer

            msg = f"LP position opened on {self.exchange}"
            self.notify_hb_app_with_timestamp(msg)

        # Check if this is our position closing order
        elif hasattr(event, 'order_id') and event.order_id == self.pending_close_order_id:
            self.logger().info(f"Position closing order {event.order_id} confirmed!")

            # Clear current position
            self.current_position_id = None
            self.position_info = None
            self.pending_close_order_id = None
            self.pending_operation = None
            self.out_of_bounds_since = None

            msg = f"LP position closed on {self.exchange}"
            self.notify_hb_app_with_timestamp(msg)

            # If this was a rebalance, open the new position
            if hasattr(self, '_rebalance_info'):
                self.logger().info("Position closed, opening rebalanced position...")
                safe_ensure_future(self.open_rebalanced_position())

    def _create_price_range_visualization(self, lower_price: Decimal, current_price: Decimal,
                                          upper_price: Decimal) -> str:
        """Create visual representation of price range with current price marker"""
        # Calculate position in range (0 to 1)
        price_range = upper_price - lower_price
        current_position = (current_price - lower_price) / price_range

        # Create 50-character wide bar
        bar_width = 50
        current_pos = int(current_position * bar_width)

        # Build price range bar
        range_bar = ['─'] * bar_width
        range_bar[0] = '├'
        range_bar[-1] = '┤'

        # Place marker inside or outside range
        if current_pos < 0:
            # Price below range
            marker_line = '● ' + ''.join(range_bar)
        elif current_pos >= bar_width:
            # Price above range
            marker_line = ''.join(range_bar) + ' ●'
        else:
            # Price within range
            range_bar[current_pos] = '●'
            marker_line = ''.join(range_bar)

        viz_lines = []
        viz_lines.append(marker_line)
        viz_lines.append(f'{float(lower_price):.2f}' + ' ' * (bar_width - len(f'{float(lower_price):.2f}') - len(f'{float(upper_price):.2f}')) + f'{float(upper_price):.2f}')
        viz_lines.append(f'Price: {float(current_price):.6f}')

        return '\n'.join(viz_lines)

    def _calculate_token_distribution(self, base_amount: Decimal, quote_amount: Decimal) -> str:
        """Calculate token distribution percentages"""
        total_value = base_amount + quote_amount
        if total_value > 0:
            base_pct = float(base_amount / total_value * 100)
            quote_pct = float(quote_amount / total_value * 100)
        else:
            base_pct = quote_pct = 50.0

        return f"Token Distribution: {base_pct:.1f}% {self.base_token} / {quote_pct:.1f}% {self.quote_token}"

    def format_status(self) -> str:
        """Format status message for display"""
        lines = []

        if self.pending_operation == "opening":
            lines.append(f"⏳ Opening position (order ID: {self.pending_open_order_id})")
            lines.append("Awaiting transaction confirmation...")
        elif self.pending_operation == "closing":
            lines.append(f"⏳ Closing position (order ID: {self.pending_close_order_id})")
            lines.append("Awaiting transaction confirmation...")
        elif self.current_position_id and self.position_info:
            # Active position
            lines.append(f"Position: {self.current_position_id}")

            # Pool info with address
            pool_address = self.position_info.pool_address if hasattr(self.position_info, 'pool_address') else self.config.pool_address
            if pool_address:
                lines.append(f"Pool: {self.config.trading_pair} ({pool_address})")
            else:
                lines.append(f"Pool: {self.config.trading_pair}")

            lines.append(f"Connector: {self.exchange}")

            # Tokens and value section
            base_amount = Decimal(str(self.position_info.base_token_amount))
            quote_amount = Decimal(str(self.position_info.quote_token_amount))
            base_fee = Decimal(str(self.position_info.base_fee_amount))
            quote_fee = Decimal(str(self.position_info.quote_fee_amount))

            if self.pool_info:
                current_price = Decimal(str(self.pool_info.price))

                # Calculate token value
                token_value = base_amount * current_price + quote_amount

                # Calculate fee value
                fee_value = base_fee * current_price + quote_fee

                # Calculate total value (tokens + fees)
                total_value = token_value + fee_value

                lines.append(f"Total Value: {total_value:.6f} {self.quote_token}")

                # Calculate percentages
                if total_value > 0:
                    token_pct = float(token_value / total_value * 100)
                    fee_pct = float(fee_value / total_value * 100)
                else:
                    token_pct = fee_pct = 0.0

                lines.append(f"Tokens: {base_amount:.6f} {self.base_token} / {quote_amount:.6f} {self.quote_token} ({token_pct:.2f}%)")

                if base_fee > 0 or quote_fee > 0:
                    lines.append(f"Fees: {base_fee:.6f} {self.base_token} / {quote_fee:.6f} {self.quote_token} ({fee_pct:.2f}%)")
            else:
                lines.append(f"Tokens: {base_amount:.6f} {self.base_token} / {quote_amount:.6f} {self.quote_token}")

                if base_fee > 0 or quote_fee > 0:
                    lines.append(f"Fees: {base_fee:.6f} {self.base_token} / {quote_fee:.6f} {self.quote_token}")

            lines.append("")  # Spacer

            # Position range and width info
            lower_price = Decimal(str(self.position_info.lower_price))
            upper_price = Decimal(str(self.position_info.upper_price))

            if self.pool_info:
                current_price = Decimal(str(self.pool_info.price))

                # Price range visualization
                lines.append(self._create_price_range_visualization(lower_price, current_price, upper_price))

                if self._price_in_bounds(current_price, lower_price, upper_price):
                    lines.append("Status: ✅ In Bounds")
                else:
                    lines.append("Status: ⚠️ Out of Bounds")
            else:
                lines.append(f"Position Range: {lower_price:.6f} - {upper_price:.6f}")

            if self.out_of_bounds_since:
                elapsed = time.time() - self.out_of_bounds_since
                lines.append(f"Out of bounds for: {elapsed:.0f}/{self.config.rebalance_seconds} seconds")

        else:
            lines.append(f"Monitoring {self.config.trading_pair} on {self.exchange}")
            lines.append("Status: ⏳ No active position")

            if self.config.base_amount > 0 or self.config.quote_amount > 0:
                lines.append(f"Will create position with: {self.config.base_amount} {self.base_token} / "
                             f"{self.config.quote_amount} {self.quote_token}")

            if self.pool_info:
                lines.append(f"Current Price: {self.pool_info.price:.6f}")

        return "\n".join(lines)
