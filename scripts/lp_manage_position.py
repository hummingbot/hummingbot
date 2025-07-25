import asyncio
import logging
import os
import time
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
        "prompt": "DEX connector in format 'name/type' (e.g., raydium/clmm, uniswap/amm)", "prompt_on_new": True})
    trading_pair: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "Trading pair (e.g. SOL-USDC)", "prompt_on_new": True})
    target_price: Decimal = Field(150.0, json_schema_extra={
        "prompt": "Target price to trigger position opening", "prompt_on_new": True})
    trigger_above: bool = Field(True, json_schema_extra={
        "prompt": "Trigger when price rises above target? (True for above/False for below)", "prompt_on_new": True})
    position_width_pct: Decimal = Field(10.0, json_schema_extra={
        "prompt": "Position width per side in percentage (e.g. 10.0 for ±10% from center price, 20% total width)", "prompt_on_new": True})
    base_token_amount: Decimal = Field(0.01, json_schema_extra={
        "prompt": "Base token amount to add to position (0 for quote only)", "prompt_on_new": True})
    quote_token_amount: Decimal = Field(2.0, json_schema_extra={
        "prompt": "Quote token amount to add to position (0 for base only)", "prompt_on_new": True})
    out_of_range_pct: Decimal = Field(1.0, json_schema_extra={
        "prompt": "Percentage outside range that triggers closing (e.g. 1.0 for 1%)", "prompt_on_new": True})
    out_of_range_secs: int = Field(60, json_schema_extra={
        "prompt": "Seconds price must be out of range before closing (e.g. 60 for 1 min)", "prompt_on_new": True})


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
        self.pool_info: Union[AMMPoolInfo, CLMMPoolInfo] = None
        self.position_info: Union[CLMMPositionInfo, AMMPositionInfo, None] = None
        self.out_of_range_start_time = None
        self.position_closing = False
        self.closing_order_id = None
        self.position_closed = False  # Track if position has been closed
        self.initial_base_balance = None  # Track wallet balance before position
        self.initial_quote_balance = None  # Track wallet balance before position
        self.position_base_amount = None  # Track base token amount in position
        self.position_quote_amount = None  # Track quote token amount in position
        self.open_price = None  # Track the price when position was opened
        self.close_price = None  # Track the price when position was closed
        self.final_base_balance = None  # Track wallet balance after position
        self.final_quote_balance = None  # Track wallet balance after position

        # Log startup information
        condition = "rises above" if self.config.trigger_above else "falls below"
        if self.connector_type == ConnectorType.CLMM:
            self.log_with_clock(logging.INFO,
                                f"Will open CLMM position when price {condition} target price: {self.config.target_price}\n"
                                f"Position width: ±{self.config.position_width_pct}% from center price\n"
                                f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds")
        else:
            self.log_with_clock(logging.INFO,
                                f"Will open AMM position when price {condition} target price: {self.config.target_price}\n"
                                f"Token amounts: {self.config.base_token_amount} {self.base_token} / {self.config.quote_token_amount} {self.quote_token}\n"
                                f"Will close position if price moves ±{self.config.position_width_pct}% from open price\n"
                                f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds")

    def on_tick(self):
        # Check price and position status on each tick
        if self.position_closed:
            # Position has been closed, do nothing more
            return
        elif not self.position_opened:
            # If no position is open, fetch pool info and check price conditions
            safe_ensure_future(self.fetch_pool_info())
            safe_ensure_future(self.check_price_and_open_position())
        else:
            # If position is open, monitor it
            safe_ensure_future(self.update_position_info())
            safe_ensure_future(self.monitor_position())

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        self.logger().info(f"Fetching pool info for {self.config.trading_pair} on {self.config.connector}")
        try:
            self.pool_info = await self.connectors[self.exchange].get_pool_info(
                trading_pair=self.config.trading_pair
            )
            return self.pool_info
        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")
            return None

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
                pool_address = await self.connectors[self.exchange].get_pool_address(
                    trading_pair=self.config.trading_pair
                )
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
            else:
                self.logger().info(f"Current price: {current_price}, Target: {self.config.target_price}, "
                                   f"Condition not met yet.")

        except Exception as e:
            self.logger().error(f"Error in check_price_and_open_position: {str(e)}")

    async def open_position(self):
        """Open a liquidity position around the target price"""
        try:
            # Calculate position price range based on CURRENT pool price
            current_price = float(self.pool_info.price)

            # Log different messages based on connector type
            if self.connector_type == ConnectorType.CLMM:
                self.logger().info(f"Opening CLMM position around current price {current_price} with ±{self.config.position_width_pct}% width")
            else:  # AMM
                self.logger().info(f"Opening AMM position at current price {current_price}")

            # Use the connector's add_liquidity method
            if self.connector_type == ConnectorType.CLMM:
                # CLMM uses spread_pct parameter
                order_id = self.connectors[self.exchange].add_liquidity(
                    trading_pair=self.config.trading_pair,
                    price=current_price,
                    spread_pct=float(self.config.position_width_pct),
                    base_token_amount=float(self.config.base_token_amount) if self.config.base_token_amount > 0 else None,
                    quote_token_amount=float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else None,
                )
            else:  # AMM
                # AMM doesn't use spread_pct, just token amounts
                order_id = self.connectors[self.exchange].add_liquidity(
                    trading_pair=self.config.trading_pair,
                    price=current_price,
                    base_token_amount=float(self.config.base_token_amount) if self.config.base_token_amount > 0 else None,
                    quote_token_amount=float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else None,
                )

            self.logger().info(f"Position opening order submitted with ID: {order_id}")

            # The position details will be updated via order update events
            self.position_opened = True

            # Store the open price
            self.open_price = current_price

            # Get current wallet balances before opening position
            try:
                connector = self.connectors[self.exchange]
                balances = connector.get_all_balances()
                self.initial_base_balance = float(balances.get(self.base_token, 0))
                self.initial_quote_balance = float(balances.get(self.quote_token, 0))
                self.logger().info(f"Wallet balances before position: {self.initial_base_balance:.6f} {self.base_token}, {self.initial_quote_balance:.6f} {self.quote_token}")
            except Exception as e:
                self.logger().error(f"Error getting initial balances: {str(e)}")

            # Store the requested position amounts
            self.position_base_amount = float(self.config.base_token_amount) if self.config.base_token_amount > 0 else 0
            self.position_quote_amount = float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else 0

            self.logger().info(f"Opening position with target amounts: {self.position_base_amount} {self.base_token} + {self.position_quote_amount} {self.quote_token}")
            self.logger().info(f"Open price: {self.open_price}")

            # For AMM positions, we need to fetch the position info after opening
            # since there's no position address returned like in CLMM
            if self.connector_type == ConnectorType.AMM:
                # Store the price at which the position was opened
                self.amm_position_open_price = current_price
                self.logger().info(f"AMM position opened at price: {self.amm_position_open_price}")

                await asyncio.sleep(2)  # Give time for position to be created
                try:
                    # Get pool address first
                    pool_address = await self.connectors[self.exchange].get_pool_address(
                        trading_pair=self.config.trading_pair
                    )
                    if pool_address:
                        # Fetch position info using pool address
                        self.position_info = await self.connectors[self.exchange].get_position_info(
                            trading_pair=self.config.trading_pair,
                            position_address=pool_address  # For AMM, this is the pool address
                        )
                        if self.position_info:
                            self.logger().info("AMM position opened successfully!")
                        else:
                            self.logger().warning("Position opened but unable to fetch position info")
                    else:
                        self.logger().warning("Unable to get pool address for position info")
                except Exception as e:
                    self.logger().error(f"Error fetching position info after opening: {e}")

        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")

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
            lower_bound_with_buffer = 0
            upper_bound_with_buffer = 0

            # Handle different types of position info based on connector type
            if isinstance(self.position_info, CLMMPositionInfo):
                # For CLMM positions, check if price is outside range
                lower_price = Decimal(str(self.position_info.lower_price))
                upper_price = Decimal(str(self.position_info.upper_price))

                # Check if price is outside position range by more than out_of_range_pct
                out_of_range_amount = 0

                lower_bound_with_buffer = lower_price * (1 - float(self.config.out_of_range_pct) / 100.0)
                upper_bound_with_buffer = upper_price * (1 + float(self.config.out_of_range_pct) / 100.0)

                if float(current_price) < lower_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (lower_bound_with_buffer - float(current_price)) / float(lower_price) * 100
                    self.logger().info(f"Price {current_price} is below position lower bound with buffer {lower_bound_with_buffer} by {out_of_range_amount:.2f}%")
                elif float(current_price) > upper_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (float(current_price) - upper_bound_with_buffer) / float(upper_price) * 100
                    self.logger().info(f"Price {current_price} is above position upper bound with buffer {upper_bound_with_buffer} by {out_of_range_amount:.2f}%")

            elif isinstance(self.position_info, AMMPositionInfo):
                # For AMM positions, track deviation from the price when position was opened
                if not hasattr(self, 'amm_position_open_price') or self.amm_position_open_price is None:
                    self.logger().error("AMM position open price not set! Cannot monitor position properly.")
                    return

                reference_price = self.amm_position_open_price

                # Calculate acceptable range based on position_width_pct
                width_pct = float(self.config.position_width_pct) / 100.0
                lower_bound = reference_price * (1 - width_pct)
                upper_bound = reference_price * (1 + width_pct)

                # Add out_of_range buffer
                out_of_range_buffer = float(self.config.out_of_range_pct) / 100.0
                lower_bound_with_buffer = lower_bound * (1 - out_of_range_buffer)
                upper_bound_with_buffer = upper_bound * (1 + out_of_range_buffer)

                if float(current_price) < lower_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (lower_bound_with_buffer - float(current_price)) / lower_bound * 100
                    self.logger().info(f"Price {current_price} is below lower bound with buffer {lower_bound_with_buffer:.6f} by {out_of_range_amount:.2f}%")
                elif float(current_price) > upper_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (float(current_price) - upper_bound_with_buffer) / upper_bound * 100
                    self.logger().info(f"Price {current_price} is above upper bound with buffer {upper_bound_with_buffer:.6f} by {out_of_range_amount:.2f}%")
            else:
                self.logger().warning("Unknown position info type")
                return

            # Track out-of-range time
            current_time = time.time()
            if out_of_range:
                if self.out_of_range_start_time is None:
                    self.out_of_range_start_time = current_time
                    self.logger().info("Price moved out of range (with buffer). Starting timer...")

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
                    self.logger().info("Price moved back into range (with buffer). Resetting timer.")
                    self.out_of_range_start_time = None

                # Add log statement when price is in range
                if isinstance(self.position_info, AMMPositionInfo):
                    self.logger().info(f"Price {current_price} is within monitoring range: {lower_bound:.6f} to {upper_bound:.6f} (buffer extends to {lower_bound_with_buffer:.6f} - {upper_bound_with_buffer:.6f})")
                else:
                    self.logger().info(f"Price {current_price} is within range: {lower_bound_with_buffer:.6f} to {upper_bound_with_buffer:.6f}")

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the liquidity position"""
        if not self.position_info:
            return

        # Prevent multiple close attempts
        if hasattr(self, 'position_closing') and self.position_closing:
            self.logger().info("Position close already in progress, skipping...")
            return

        self.position_closing = True

        try:
            # Use the connector's remove_liquidity method
            if isinstance(self.position_info, CLMMPositionInfo):
                self.logger().info(f"Closing CLMM position {self.position_info.address}...")
                order_id = self.connectors[self.exchange].remove_liquidity(
                    trading_pair=self.config.trading_pair,
                    position_address=self.position_info.address
                )
            else:  # AMM position
                self.logger().info(f"Closing AMM position for {self.config.trading_pair}...")
                order_id = self.connectors[self.exchange].remove_liquidity(
                    trading_pair=self.config.trading_pair
                )

            self.logger().info(f"Position closing order submitted with ID: {order_id}")

            # Store the closing order ID to track it
            self.closing_order_id = order_id

            # Wait for the order to be confirmed
            max_wait_time = 30  # seconds
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                # Check if order is completed
                in_flight_orders = self.connectors[self.exchange].in_flight_orders
                if order_id not in in_flight_orders:
                    # Order completed (either filled or failed)
                    self.logger().info("Position close order completed")
                    break

                # Wait a bit before checking again
                await asyncio.sleep(1)
            else:
                # Timeout reached
                self.logger().warning(f"Position close order {order_id} did not complete within {max_wait_time} seconds")
                self.logger().warning("Position may still be open. Please check manually.")
                # Don't reset state if order didn't complete
                self.position_closing = False
                return

            # Get current pool info to get the close price
            await self.fetch_pool_info()
            if self.pool_info:
                self.close_price = float(self.pool_info.price)

            # Wait a bit for final balances to settle
            await asyncio.sleep(2)

            # Get wallet balances to calculate final amounts
            try:
                connector = self.connectors[self.exchange]
                balances = connector.get_all_balances()

                # Get the final wallet balances
                self.final_base_balance = float(balances.get(self.base_token, 0))
                self.final_quote_balance = float(balances.get(self.quote_token, 0))

                # Calculate the differences in wallet balances
                base_diff = self.final_base_balance - self.initial_base_balance
                quote_diff = self.final_quote_balance - self.initial_quote_balance

                # Calculate price change
                price_change_pct = ((self.close_price - self.open_price) / self.open_price * 100) if self.open_price else 0

                # Create the final report
                report_lines = []
                report_lines.append("\n" + "=" * 50)
                report_lines.append("POSITION CLOSED - FINAL REPORT")
                report_lines.append("=" * 50)
                report_lines.append(f"Open price: {self.open_price:.6f}")
                report_lines.append(f"Close price: {self.close_price:.6f}")
                report_lines.append(f"Price change: {price_change_pct:+.2f}%")
                report_lines.append("-" * 50)
                report_lines.append(f"Position size: {self.position_base_amount:.6f} {self.base_token} + {self.position_quote_amount:.6f} {self.quote_token}")
                report_lines.append("-" * 50)
                report_lines.append(f"Wallet balance before: {self.initial_base_balance:.6f} {self.base_token}, {self.initial_quote_balance:.6f} {self.quote_token}")
                report_lines.append(f"Wallet balance after: {self.final_base_balance:.6f} {self.base_token}, {self.final_quote_balance:.6f} {self.quote_token}")
                report_lines.append("-" * 50)
                report_lines.append("Net changes:")
                base_pct = (base_diff / self.initial_base_balance * 100) if self.initial_base_balance > 0 else 0
                quote_pct = (quote_diff / self.initial_quote_balance * 100) if self.initial_quote_balance > 0 else 0
                report_lines.append(f"  {self.base_token}: {base_diff:+.6f} ({base_pct:+.2f}%)")
                report_lines.append(f"  {self.quote_token}: {quote_diff:+.6f} ({quote_pct:+.2f}%)")

                # Calculate total portfolio value change in quote token
                initial_portfolio_value = self.initial_base_balance * self.open_price + self.initial_quote_balance
                final_portfolio_value = self.final_base_balance * self.close_price + self.final_quote_balance
                portfolio_change = final_portfolio_value - initial_portfolio_value
                portfolio_change_pct = (portfolio_change / initial_portfolio_value * 100) if initial_portfolio_value > 0 else 0

                report_lines.append("-" * 50)
                report_lines.append(f"Total portfolio value (in {self.quote_token}):")
                report_lines.append(f"  Before: {initial_portfolio_value:.2f}")
                report_lines.append(f"  After: {final_portfolio_value:.2f}")
                report_lines.append(f"  Change: {portfolio_change:+.2f} ({portfolio_change_pct:+.2f}%)")
                report_lines.append("=" * 50 + "\n")

                # Log the report
                for line in report_lines:
                    self.logger().info(line)

                # Also display in the main UI using notify
                self.notify("\n".join(report_lines))

            except Exception as e:
                self.logger().error(f"Error calculating final amounts: {str(e)}")

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
            self.logger().info("Strategy completed. Position has been closed and will not reopen.")

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")
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

    def did_fill_order(self, event):
        """
        Called when an order is filled. We use this to track the actual amounts deposited.
        """
        if hasattr(event, 'trade_type') and str(event.trade_type) == 'TradeType.RANGE':
            # This is a liquidity provision order
            if self.position_opened and not self.position_closed:
                # Update the initial amounts with the actual filled amounts
                if hasattr(event, 'amount'):
                    # For LP orders, the amount is typically the base token amount
                    actual_base = float(event.amount)
                    # Calculate the actual quote amount based on price
                    actual_quote = actual_base * float(event.price) if hasattr(event, 'price') else self.initial_quote_amount

                    self.logger().info(f"Position filled with actual amounts: {actual_base:.6f} {self.base_token} + {actual_quote:.6f} {self.quote_token}")

                    # Update our tracking with actual amounts
                    self.position_base_amount = actual_base
                    self.position_quote_amount = actual_quote

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        lines = []

        if self.position_closed:
            lines.append("Position has been closed. Strategy completed.")
            if self.initial_base_balance is not None and self.final_base_balance is not None:
                lines.append(f"Wallet before: {self.initial_base_balance:.6f} {self.base_token}, {self.initial_quote_balance:.6f} {self.quote_token}")
                lines.append(f"Wallet after: {self.final_base_balance:.6f} {self.base_token}, {self.final_quote_balance:.6f} {self.quote_token}")
                base_diff = self.final_base_balance - self.initial_base_balance
                quote_diff = self.final_quote_balance - self.initial_quote_balance
                lines.append(f"Net change: {base_diff:+.6f} {self.base_token}, {quote_diff:+.6f} {self.quote_token}")
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
                width_pct = Decimal(str(self.config.position_width_pct)) / Decimal("100")
                lower_price = open_price * (1 - width_pct)
                upper_price = open_price * (1 + width_pct)
                lines.append(f"Position Opened At: {open_price:.6f}")
                lines.append(f"Monitoring Range: {lower_price:.6f} - {upper_price:.6f} (±{self.config.position_width_pct}% from open price)")
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
            if self.pool_info:
                lines.append(f"Current Price: {self.pool_info.price}")
            lines.append(f"Target Price: {self.config.target_price}")
            condition = "rises above" if self.config.trigger_above else "falls below"
            lines.append(f"Will open position when price {condition} target")

        return "\n".join(lines)
