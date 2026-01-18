import asyncio
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Union

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_lp import AMMPoolInfo, AMMPositionInfo, CLMMPoolInfo, CLMMPositionInfo
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LpPositionManagerConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    connector: str = Field("raydium/clmm", json_schema_extra={
        "prompt": "AMM or CLMM connector in format 'name/type' (e.g. raydium/clmm, uniswap/amm)", "prompt_on_new": True})
    trading_pair: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "Trading pair (e.g. SOL-USDC)", "prompt_on_new": True})
    pool_address: str = Field("", json_schema_extra={
        "prompt": "Pool address (optional - will fetch automatically if not provided)", "prompt_on_new": False})
    target_price: Decimal = Field(150.0, json_schema_extra={
        "prompt": "Target price to trigger position opening", "prompt_on_new": True})
    trigger_above: bool = Field(True, json_schema_extra={
        "prompt": "Trigger when price rises above target? (True for above/False for below)", "prompt_on_new": True})
    upper_range_width_pct: Decimal = Field(10.0, json_schema_extra={
        "prompt": "Upper range width in percentage from center price (e.g. 10.0 for +10%)", "prompt_on_new": True})
    lower_range_width_pct: Decimal = Field(10.0, json_schema_extra={
        "prompt": "Lower range width in percentage from center price (e.g. 10.0 for -10%)", "prompt_on_new": True})
    base_token_amount: Decimal = Field(0.01, json_schema_extra={
        "prompt": "Base token amount to add to position (0 for quote only)", "prompt_on_new": True})
    quote_token_amount: Decimal = Field(2.0, json_schema_extra={
        "prompt": "Quote token amount to add to position (0 for base only)", "prompt_on_new": True})
    out_of_range_secs: int = Field(60, json_schema_extra={
        "prompt": "Seconds price must be out of range before closing (e.g. 60 for 1 min)", "prompt_on_new": True})
    check_interval: int = Field(10, json_schema_extra={
        "prompt": "How often to check price in seconds (default: 10)", "prompt_on_new": False})


class LpPositionManager(ScriptStrategyBase):
    """
    This strategy shows how to use the Gateway LP connector to manage a AMM or CLMM position.
    It monitors pool prices, opens a position when a target price is reached,
    and closes the position if the price moves out of range for a specified duration.
    """

    @classmethod
    def init_markets(cls, config: LpPositionManagerConfig):
        cls.markets = {config.connector: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: LpPositionManagerConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = config.connector  # Now uses connector directly (e.g., "raydium/clmm")
        self.connector_type = get_connector_type(config.connector)
        self.base_token, self.quote_token = self.config.trading_pair.split("-")

        # State tracking
        self.position_opened = False
        self.position_opening = False  # Track if position is being opened
        self.pool_info: Union[AMMPoolInfo, CLMMPoolInfo] = None
        self.position_info: Union[CLMMPositionInfo, AMMPositionInfo, None] = None
        self.out_of_range_start_time = None
        self.position_closing = False
        self.position_closed = False  # Track if position has been closed
        self.amm_position_open_price = None  # Track AMM position open price for monitoring

        # Order tracking
        self.open_position_order_id = None
        self.close_position_order_id = None

        # Price checking timing
        self.last_price = None
        self.last_price_update = None
        self.last_check_time = None

        # Log startup information
        condition = "rises above" if self.config.trigger_above else "falls below"
        if self.connector_type == ConnectorType.CLMM:
            self.log_with_clock(logging.INFO,
                                f"Will open CLMM position when price {condition} target price: {self.config.target_price}\n"
                                f"Position range: -{self.config.lower_range_width_pct}% to +{self.config.upper_range_width_pct}% from center price\n"
                                f"Will close position if price is outside range for {self.config.out_of_range_secs} seconds")
        else:
            self.log_with_clock(logging.INFO,
                                f"Will open AMM position when price {condition} target price: {self.config.target_price}\n"
                                f"Token amounts: {self.config.base_token_amount} {self.base_token} / {self.config.quote_token_amount} {self.quote_token}\n"
                                f"Will close position if price moves -{self.config.lower_range_width_pct}% or +{self.config.upper_range_width_pct}% from open price\n"
                                f"Will close position if price is outside range for {self.config.out_of_range_secs} seconds")

        self.log_with_clock(logging.INFO, f"Price will be checked every {self.config.check_interval} seconds")

        # Check for existing positions on startup (delayed to allow connector initialization)
        safe_ensure_future(self.check_and_use_existing_position())

    async def check_and_use_existing_position(self):
        """Check for existing positions on startup"""
        await asyncio.sleep(3)  # Wait for connector to initialize

        # Fetch pool info first
        await self.fetch_pool_info()

        if await self.check_existing_positions():
            self.position_opened = True
            # For AMM positions, store current price as reference for monitoring
            if self.connector_type == ConnectorType.AMM and self.pool_info:
                self.amm_position_open_price = float(self.pool_info.price)
            self.logger().info("Using existing position for monitoring")

    def on_tick(self):
        # Check price and position status on each tick
        if self.position_closed:
            # Position has been closed, do nothing more
            return
        elif self.position_opening:
            # Position is being opened, wait for confirmation
            return
        elif self.position_closing:
            # Position is being closed, wait for confirmation
            return
        elif not self.position_opened:
            # Check if enough time has passed since last check
            current_time = datetime.now()
            if self.last_check_time is None or (current_time - self.last_check_time).total_seconds() >= self.config.check_interval:
                self.last_check_time = current_time
                # If no position is open, check price conditions (which includes fetching pool info)
                safe_ensure_future(self.check_price_and_open_position())
        else:
            # If position is open, monitor it
            safe_ensure_future(self.update_position_info())
            safe_ensure_future(self.monitor_position())

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        if self.config.pool_address:
            self.logger().info(f"Fetching pool info for pool {self.config.pool_address} on {self.config.connector}")
        else:
            self.logger().info(f"Fetching pool info for {self.config.trading_pair} on {self.config.connector}")
        try:
            # If pool address is provided, we can fetch pool info directly
            # Otherwise, get_pool_info will fetch the pool address internally
            self.pool_info = await self.connectors[self.exchange].get_pool_info(
                trading_pair=self.config.trading_pair
            )
            return self.pool_info
        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")
            return None

    async def get_pool_address(self):
        """Get pool address from config or fetch from connector"""
        if self.config.pool_address:
            return self.config.pool_address
        else:
            connector = self.connectors[self.exchange]
            return await connector.get_pool_address(self.config.trading_pair)

    async def check_existing_positions(self):
        """Check if user has existing positions in this pool"""
        try:
            connector = self.connectors[self.exchange]
            pool_address = await self.get_pool_address()

            if self.connector_type == ConnectorType.CLMM:
                # For CLMM, fetch all user positions for this pool
                positions = await connector.get_user_positions(pool_address=pool_address)
                if positions and len(positions) > 0:
                    # Use the first position found (could be enhanced to let user choose)
                    self.position_info = positions[0]
                    self.logger().info(f"Found existing CLMM position: {self.position_info.address}")
                    return True
            else:
                # For AMM, check if user has position in this pool
                if pool_address:
                    position_info = await connector.get_position_info(
                        trading_pair=self.config.trading_pair,
                        position_address=pool_address
                    )
                    if position_info and position_info.lp_token_amount > 0:
                        self.position_info = position_info
                        self.logger().info(f"Found existing AMM position in pool {pool_address}")
                        return True

            return False
        except Exception as e:
            self.logger().debug(f"No existing positions found or error checking: {str(e)}")
            return False

    async def update_position_info(self):
        """Fetch the latest position information if we have an open position"""
        if not self.position_opened or not self.position_info:
            return

        try:
            if isinstance(self.position_info, CLMMPositionInfo):
                # For CLMM, use the position address
                self.position_info = await self.connectors[self.exchange].get_position_info(
                    trading_pair=self.config.trading_pair,
                    position_address=self.position_info.address
                )
            else:  # AMM position
                # For AMM, get the pool address
                pool_address = await self.get_pool_address()
                if pool_address:
                    self.position_info = await self.connectors[self.exchange].get_position_info(
                        trading_pair=self.config.trading_pair,
                        position_address=pool_address
                    )
            self.logger().debug(f"Updated position info: {self.position_info}")
        except Exception as e:
            self.logger().error(f"Error updating position info: {str(e)}")

    async def check_price_and_open_position(self):
        """Check current price and open position if target is reached"""
        if self.position_opened:
            return

        try:
            # Fetch current pool info to get the latest price
            await self.fetch_pool_info()

            if not self.pool_info:
                self.logger().warning("Unable to get current price")
                return

            current_price = Decimal(str(self.pool_info.price))

            # Update last price tracking
            self.last_price = current_price
            self.last_price_update = datetime.now()

            # Log current price vs target
            price_diff = current_price - self.config.target_price
            percentage_diff = (price_diff / self.config.target_price) * 100

            if self.config.trigger_above:
                status = "waiting for price to rise" if current_price < self.config.target_price else "ABOVE TARGET"
                self.logger().info(f"Current price: {current_price:.6f} | Target: {self.config.target_price:.6f} | "
                                   f"Difference: {price_diff:.6f} ({percentage_diff:+.2f}%) | Status: {status}")
            else:
                status = "waiting for price to fall" if current_price > self.config.target_price else "BELOW TARGET"
                self.logger().info(f"Current price: {current_price:.6f} | Target: {self.config.target_price:.6f} | "
                                   f"Difference: {price_diff:.6f} ({percentage_diff:+.2f}%) | Status: {status}")

            # Check for existing positions in this pool
            if not self.position_info:
                await self.check_existing_positions()
                if self.position_info:
                    self.logger().info("Found existing position in pool, will monitor it instead of creating new one")
                    self.position_opened = True
                    # For AMM positions, store current price as reference for monitoring
                    if self.connector_type == ConnectorType.AMM:
                        self.amm_position_open_price = float(current_price)
                    return

            # Check if price condition is met
            condition_met = False
            if self.config.trigger_above and current_price > self.config.target_price:
                condition_met = True
                self.logger().info(f"Price rose above target: {current_price} > {self.config.target_price}")
            elif not self.config.trigger_above and current_price < self.config.target_price:
                condition_met = True
                self.logger().info(f"Price fell below target: {current_price} < {self.config.target_price}")

            if condition_met:
                self.logger().info("Price condition met! Opening position...")
                await self.open_position()

        except Exception as e:
            self.logger().error(f"Error in check_price_and_open_position: {str(e)}")

    async def open_position(self):
        """Open a liquidity position around the target price"""
        # Prevent multiple open attempts
        if self.position_opening or self.position_opened:
            return

        self.position_opening = True

        try:
            # Calculate position price range based on CURRENT pool price
            current_price = float(self.pool_info.price)

            # Log different messages based on connector type
            if self.connector_type == ConnectorType.CLMM:
                self.logger().info(f"Submitting CLMM position order around current price {current_price} with range -{self.config.lower_range_width_pct}% to +{self.config.upper_range_width_pct}%")
            else:  # AMM
                self.logger().info(f"Submitting AMM position order at current price {current_price}")

            # Use the connector's add_liquidity method
            if self.connector_type == ConnectorType.CLMM:
                # CLMM uses upper_width_pct and lower_width_pct parameters
                order_id = self.connectors[self.exchange].add_liquidity(
                    trading_pair=self.config.trading_pair,
                    price=current_price,
                    upper_width_pct=float(self.config.upper_range_width_pct),
                    lower_width_pct=float(self.config.lower_range_width_pct),
                    base_token_amount=float(self.config.base_token_amount),
                    quote_token_amount=float(self.config.quote_token_amount),
                )
            else:  # AMM
                # AMM doesn't use spread_pct, just token amounts
                order_id = self.connectors[self.exchange].add_liquidity(
                    trading_pair=self.config.trading_pair,
                    price=current_price,
                    base_token_amount=float(self.config.base_token_amount),
                    quote_token_amount=float(self.config.quote_token_amount),
                )

            self.open_position_order_id = order_id
            self.logger().info(f"Position opening order submitted with ID: {order_id} (awaiting confirmation)")

            # For AMM positions, store the price for later use
            if self.connector_type == ConnectorType.AMM:
                self.amm_position_open_price = current_price

        except Exception as e:
            self.logger().error(f"Error submitting position open order: {str(e)}")
            self.position_opening = False

    async def monitor_position(self):
        """Monitor the position and price to determine if position should be closed"""
        if not self.position_info:
            return

        # Don't monitor if we're already closing
        if self.position_closing:
            return

        try:
            # Fetch current pool info to get the latest price
            await self.fetch_pool_info()

            if not self.pool_info or not self.position_info:
                return

            current_price = Decimal(str(self.pool_info.price))

            # Initialize variables that will be used later
            out_of_range = False

            # Handle different types of position info based on connector type
            if isinstance(self.position_info, CLMMPositionInfo):
                # For CLMM positions, check if price is outside range
                lower_price = Decimal(str(self.position_info.lower_price))
                upper_price = Decimal(str(self.position_info.upper_price))

                # Check if price is outside position range
                if float(current_price) < float(lower_price):
                    out_of_range = True
                    out_of_range_amount = (float(lower_price) - float(current_price)) / float(lower_price) * 100
                    self.logger().info(f"Price {current_price} is below position lower bound {lower_price} by {out_of_range_amount:.2f}%")
                elif float(current_price) > float(upper_price):
                    out_of_range = True
                    out_of_range_amount = (float(current_price) - float(upper_price)) / float(upper_price) * 100
                    self.logger().info(f"Price {current_price} is above position upper bound {upper_price} by {out_of_range_amount:.2f}%")

            elif isinstance(self.position_info, AMMPositionInfo):
                # For AMM positions, track deviation from the price when position was opened
                if not hasattr(self, 'amm_position_open_price') or self.amm_position_open_price is None:
                    self.logger().error("AMM position open price not set! Cannot monitor position properly.")
                    return

                reference_price = self.amm_position_open_price

                # Calculate acceptable range based on separate upper and lower width percentages
                lower_width_pct = float(self.config.lower_range_width_pct) / 100.0
                upper_width_pct = float(self.config.upper_range_width_pct) / 100.0
                lower_bound = reference_price * (1 - lower_width_pct)
                upper_bound = reference_price * (1 + upper_width_pct)

                if float(current_price) < lower_bound:
                    out_of_range = True
                    out_of_range_amount = (lower_bound - float(current_price)) / lower_bound * 100
                    self.logger().info(f"Price {current_price} is below lower bound {lower_bound:.6f} by {out_of_range_amount:.2f}%")
                elif float(current_price) > upper_bound:
                    out_of_range = True
                    out_of_range_amount = (float(current_price) - upper_bound) / upper_bound * 100
                    self.logger().info(f"Price {current_price} is above upper bound {upper_bound:.6f} by {out_of_range_amount:.2f}%")
            else:
                self.logger().warning("Unknown position info type")
                return

            # Track out-of-range time
            current_time = time.time()
            if out_of_range:
                if self.out_of_range_start_time is None:
                    self.out_of_range_start_time = current_time
                    self.logger().info("Price moved out of range. Starting timer...")

                # Check if price has been out of range for sufficient time
                elapsed_seconds = current_time - self.out_of_range_start_time
                if elapsed_seconds >= self.config.out_of_range_secs:
                    self.logger().info(f"Price has been out of range for {elapsed_seconds:.0f} seconds (threshold: {self.config.out_of_range_secs} seconds)")
                    self.logger().info("Closing position...")
                    await self.close_position()
                else:
                    self.logger().info(f"Price out of range for {elapsed_seconds:.0f} seconds, waiting until {self.config.out_of_range_secs} seconds...")
            else:
                # Reset timer if price moves back into range
                if self.out_of_range_start_time is not None:
                    self.logger().info("Price moved back into range. Resetting timer.")
                    self.out_of_range_start_time = None

                # Add log statement when price is in range
                if isinstance(self.position_info, AMMPositionInfo):
                    self.logger().info(f"Price {current_price} is within monitoring range: {lower_bound:.6f} to {upper_bound:.6f}")
                else:
                    self.logger().info(f"Price {current_price} is within range: {lower_price:.6f} to {upper_price:.6f}")

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the liquidity position"""
        if not self.position_info:
            return

        # Prevent multiple close attempts
        if self.position_closing or self.position_closed:
            self.logger().info("Position close already in progress or completed, skipping...")
            return

        self.position_closing = True

        try:
            # Use the connector's remove_liquidity method
            if isinstance(self.position_info, CLMMPositionInfo):
                self.logger().info(f"Submitting order to close CLMM position {self.position_info.address}...")
                order_id = self.connectors[self.exchange].remove_liquidity(
                    trading_pair=self.config.trading_pair,
                    position_address=self.position_info.address
                )
            else:  # AMM position
                self.logger().info(f"Submitting order to close AMM position for {self.config.trading_pair}...")
                order_id = self.connectors[self.exchange].remove_liquidity(
                    trading_pair=self.config.trading_pair
                )

            self.close_position_order_id = order_id
            self.logger().info(f"Position closing order submitted with ID: {order_id} (awaiting confirmation)")

        except Exception as e:
            self.logger().error(f"Error submitting position close order: {str(e)}")
            self.position_closing = False

    def _get_price_range_visualization(self, current_price: Decimal, lower_price: Decimal, upper_price: Decimal, width: int = 20) -> str:
        """Generate ASCII visualization of price range"""
        if not self.pool_info:
            return ""

        # Calculate the price range for visualization
        price_range = float(upper_price) - float(lower_price)
        if price_range == 0:
            return ""

        # Calculate the position of current price in the range
        position = (float(current_price) - float(lower_price)) / price_range
        position = max(0, min(1, position))  # Clamp between 0 and 1

        # Generate the visualization
        bar = [' '] * width
        bar[int(position * (width - 1))] = '|'  # Current price marker
        bar[0] = '['  # Lower bound
        bar[-1] = ']'  # Upper bound

        return f"{lower_price:.2f} {''.join(bar)} {upper_price:.2f}"

    async def fetch_position_info_after_fill(self):
        """Fetch position info after LP order is filled"""
        try:
            # Wait a bit for the position to be fully created on-chain
            await asyncio.sleep(2)

            connector = self.connectors[self.exchange]
            pool_address = await self.get_pool_address()

            if self.connector_type == ConnectorType.CLMM:
                # For CLMM, fetch all user positions for this pool and get the latest one
                positions = await connector.get_user_positions(pool_address=pool_address)
                if positions:
                    # Get the most recent position (last in the list)
                    self.position_info = positions[-1]
                    self.logger().info(f"CLMM position fetched: {self.position_info.address}")
            else:
                # For AMM, use the pool address to get position info
                if pool_address:
                    self.position_info = await connector.get_position_info(
                        trading_pair=self.config.trading_pair,
                        position_address=pool_address
                    )
                    self.logger().info(f"AMM position info fetched for pool {pool_address}")
        except Exception as e:
            self.logger().error(f"Error fetching position info after fill: {str(e)}")

    def did_fill_order(self, event):
        """
        Called when an order is filled. We use this to confirm position opening/closing.
        """
        # Check if this is our position opening order
        if hasattr(event, 'order_id') and event.order_id == self.open_position_order_id:
            self.logger().info(f"Position opening order {event.order_id} confirmed!")
            self.position_opened = True
            self.position_opening = False

            # Log fill details if available
            if hasattr(event, 'amount'):
                actual_base = float(event.amount)
                actual_quote = actual_base * float(event.price) if hasattr(event, 'price') else 0
                self.logger().info(f"Position opened with amounts: {actual_base:.6f} {self.base_token} + {actual_quote:.6f} {self.quote_token}")

            # Fetch position info after the order is filled
            safe_ensure_future(self.fetch_position_info_after_fill())

            # Notify user
            msg = f"LP position opened successfully on {self.exchange}"
            self.notify_hb_app_with_timestamp(msg)

        # Check if this is our position closing order
        elif hasattr(event, 'order_id') and event.order_id == self.close_position_order_id:
            self.logger().info(f"Position closing order {event.order_id} confirmed!")

            # Mark position as closed
            self.position_closed = True
            self.position_opened = False
            self.position_info = None
            self.pool_info = None
            self.out_of_range_start_time = None
            self.position_closing = False
            if hasattr(self, 'amm_position_open_price'):
                self.amm_position_open_price = None

            # Log that the strategy has completed
            self.logger().info("Position closed successfully. Strategy completed.")

            # Notify user
            msg = f"LP position closed successfully on {self.exchange}"
            self.notify_hb_app_with_timestamp(msg)

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        lines = []

        if self.position_closed:
            lines.append("Position has been closed. Strategy completed.")
        elif self.position_closing:
            lines.append(f"⏳ Position closing order submitted (ID: {self.close_position_order_id})")
            lines.append("Awaiting transaction confirmation...")
        elif self.position_opening:
            lines.append(f"⏳ Position opening order submitted (ID: {self.open_position_order_id})")
            lines.append("Awaiting transaction confirmation...")
        elif self.position_opened and self.position_info:
            if isinstance(self.position_info, CLMMPositionInfo):
                lines.append(f"Position: {self.position_info.address} ({self.config.trading_pair}) on {self.exchange}")
            else:  # AMM position
                lines.append(f"Position: {self.config.trading_pair} on {self.exchange}")

            # Common position info for both CLMM and AMM
            base_amount = Decimal(str(self.position_info.base_token_amount))
            quote_amount = Decimal(str(self.position_info.quote_token_amount))
            total_quote_value = base_amount * Decimal(str(self.pool_info.price)) + quote_amount

            lines.append(f"Tokens: {base_amount:.6f} {self.base_token} / {quote_amount:.6f} {self.quote_token}")
            lines.append(f"Total Value: {total_quote_value:.2f} {self.quote_token}")

            # Get price range visualization
            if isinstance(self.position_info, CLMMPositionInfo):
                lower_price = Decimal(str(self.position_info.lower_price))
                upper_price = Decimal(str(self.position_info.upper_price))
                lines.append(f"Position Range: {lower_price:.6f} - {upper_price:.6f}")
            else:  # AMMPositionInfo
                # For AMM, show the monitoring range based on open price
                open_price = Decimal(str(self.amm_position_open_price))
                lower_width_pct = Decimal(str(self.config.lower_range_width_pct)) / Decimal("100")
                upper_width_pct = Decimal(str(self.config.upper_range_width_pct)) / Decimal("100")
                lower_price = open_price * (1 - lower_width_pct)
                upper_price = open_price * (1 + upper_width_pct)
                lines.append(f"Position Opened At: {open_price:.6f}")
                lines.append(f"Monitoring Range: {lower_price:.6f} - {upper_price:.6f} (-{self.config.lower_range_width_pct}% to +{self.config.upper_range_width_pct}% from open price)")
            if self.pool_info:
                current_price = Decimal(str(self.pool_info.price))
                price_visualization = self._get_price_range_visualization(current_price, lower_price, upper_price)
                if price_visualization:
                    lines.append(price_visualization)
                lines.append(f"Current Price: {current_price}")

            # Position-specific info
            if isinstance(self.position_info, CLMMPositionInfo):
                if self.position_info.base_fee_amount > 0 or self.position_info.quote_fee_amount > 0:
                    lines.append(f"Fees: {self.position_info.base_fee_amount} {self.base_token} / {self.position_info.quote_fee_amount} {self.quote_token}")

            if self.out_of_range_start_time:
                elapsed = time.time() - self.out_of_range_start_time
                lines.append(f"Price out of range for {elapsed:.0f}/{self.config.out_of_range_secs} seconds")
        else:
            lines.append(f"Monitoring {self.base_token}-{self.quote_token} pool on {self.exchange}")
            lines.append(f"Target Price: {self.config.target_price}")
            condition = "rises above" if self.config.trigger_above else "falls below"
            lines.append(f"Will open position when price {condition} target")
            lines.append(f"Check Interval: Every {self.config.check_interval} seconds")

            if self.last_price is not None:
                # Calculate price difference
                price_diff = self.last_price - self.config.target_price
                percentage_diff = (price_diff / self.config.target_price) * 100

                # Determine status
                if self.config.trigger_above:
                    if self.last_price < self.config.target_price:
                        status_emoji = "⏳"
                        status_text = f"Waiting (need {self.config.target_price - self.last_price:.6f} more)"
                    else:
                        status_emoji = "✅"
                        status_text = "READY TO OPEN POSITION"
                else:
                    if self.last_price > self.config.target_price:
                        status_emoji = "⏳"
                        status_text = f"Waiting (need {self.last_price - self.config.target_price:.6f} drop)"
                    else:
                        status_emoji = "✅"
                        status_text = "READY TO OPEN POSITION"

                lines.append(f"\nCurrent Price: {self.last_price:.6f}")
                lines.append(f"Target Price:  {self.config.target_price:.6f}")
                lines.append(f"Difference:    {price_diff:.6f} ({percentage_diff:+.2f}%)")
                lines.append(f"Status:        {status_emoji} {status_text}")

                if self.last_price_update:
                    seconds_ago = (datetime.now() - self.last_price_update).total_seconds()
                    lines.append(f"\nLast update: {int(seconds_ago)}s ago")

                # Show next check time
                if self.last_check_time:
                    next_check_in = self.config.check_interval - int((datetime.now() - self.last_check_time).total_seconds())
                    if next_check_in > 0:
                        lines.append(f"Next check in: {next_check_in}s")
            else:
                lines.append("\nStatus: ⏳ Waiting for first price update...")

        return "\n".join(lines)
