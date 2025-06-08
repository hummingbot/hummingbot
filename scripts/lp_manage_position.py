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
    connector: str = Field("raydium/clmm")
    chain: str = Field("solana")
    network: str = Field("mainnet-beta")
    trading_pair: str = Field("SOL-USDC")
    target_price: Decimal = Field(130.0)
    trigger_above: bool = Field(True)
    position_width_pct: Decimal = Field(10.0)
    base_token_amount: Decimal = Field(0.1)
    quote_token_amount: Decimal = Field(1.0)
    out_of_range_pct: Decimal = Field(1.0)
    out_of_range_secs: int = Field(300)


class LpPositionManager(ScriptStrategyBase):
    """
    This strategy monitors pool prices, opens a position when a target price is reached,
    and closes the position if the price moves out of range for a specified duration.
    Works with both AMM and CLMM pools.
    """

    @classmethod
    def init_markets(cls, config: LpPositionManagerConfig):
        connector_chain_network = f"{config.connector}_{config.chain}_{config.network}"
        cls.markets = {connector_chain_network: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: LpPositionManagerConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = f"{config.connector}_{config.chain}_{config.network}"
        self.connector_type = get_connector_type(config.connector)
        self.base_token, self.quote_token = self.config.trading_pair.split("-")

        # State tracking
        self.position_opened = False
        self.pool_info: Union[AMMPoolInfo, CLMMPoolInfo] = None
        self.position_info: Union[CLMMPositionInfo, AMMPositionInfo, None] = None
        self.out_of_range_start_time = None

        # Log startup information
        condition = "rises above" if self.config.trigger_above else "falls below"
        self.log_with_clock(logging.INFO,
                            f"Will open position when price {condition} target price: {self.config.target_price}\n"
                            f"Position width: ±{self.config.position_width_pct}%\n"
                            f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds")

    def on_tick(self):
        # Check price and position status on each tick
        if not self.position_opened:
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
            self.position_info = await self.connectors[self.exchange].get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=self.position_info.address
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
            width_pct = float(self.config.position_width_pct) / 100.0

            # Log different messages based on connector type
            if self.connector_type == ConnectorType.CLMM:
                self.logger().info(f"Opening CLMM position around current price {current_price} with width: ±{self.config.position_width_pct}%")
            else:  # AMM
                target_price = float(self.config.target_price)
                lower_bound = target_price * (1 - width_pct)
                upper_bound = target_price * (1 + width_pct)
                self.logger().info(f"Opening AMM position with target price {target_price}")
                self.logger().info(f"Position will be closed if price moves outside range: {lower_bound:.6f} to {upper_bound:.6f}")

            # Use the connector's open_position method
            order_id = self.connectors[self.exchange].open_position(
                trading_pair=self.config.trading_pair,
                price=current_price,
                spread_pct=float(self.config.position_width_pct),
                base_token_amount=float(self.config.base_token_amount) if self.config.base_token_amount > 0 else None,
                quote_token_amount=float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else None,
            )

            self.logger().info(f"Position opening order submitted with ID: {order_id}")

            # The position details will be updated via order update events
            self.position_opened = True

        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")

    async def monitor_position(self):
        """Monitor the position and price to determine if position should be closed"""
        if not self.position_info:
            return

        try:
            # Fetch current pool info to get the latest price
            await self.fetch_pool_info()

            if not self.pool_info or not self.position_info:
                return

            current_price = Decimal(str(self.pool_info.price))

            # Handle different types of position info based on connector type
            if isinstance(self.position_info, CLMMPositionInfo):
                # For CLMM positions, check if price is outside range
                lower_price = Decimal(str(self.position_info.lowerPrice))
                upper_price = Decimal(str(self.position_info.upperPrice))

                # Check if price is outside position range by more than out_of_range_pct
                out_of_range = False
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
                # For AMM positions, use target_price and position_width_pct to determine acceptable range
                target_price = float(self.config.target_price)
                width_pct = float(self.config.position_width_pct)

                # Calculate price range based on target price and position width
                lower_bound = target_price * (1 - width_pct / 100.0)
                upper_bound = target_price * (1 + width_pct / 100.0)

                # Add out_of_range buffer
                out_of_range_buffer = float(self.config.out_of_range_pct)
                lower_bound_with_buffer = lower_bound * (1 - out_of_range_buffer / 100.0)
                upper_bound_with_buffer = upper_bound * (1 + out_of_range_buffer / 100.0)

                out_of_range = False

                if float(current_price) < lower_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (lower_bound_with_buffer - float(current_price)) / lower_bound * 100
                    self.logger().info(f"Price {current_price} is below lower bound with buffer {lower_bound_with_buffer} by {out_of_range_amount:.2f}%")
                elif float(current_price) > upper_bound_with_buffer:
                    out_of_range = True
                    out_of_range_amount = (float(current_price) - upper_bound_with_buffer) / upper_bound * 100
                    self.logger().info(f"Price {current_price} is above upper bound with buffer {upper_bound_with_buffer} by {out_of_range_amount:.2f}%")
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
                self.logger().info(f"Price {current_price} is within range: {lower_bound_with_buffer:.6f} to {upper_bound_with_buffer:.6f}")

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the liquidity position"""
        if not self.position_info:
            return

        try:
            # Use the connector's close_position method
            self.logger().info(f"Closing position {self.position_info.address}...")
            order_id = self.connectors[self.exchange].close_position(
                trading_pair=self.config.trading_pair,
                position_address=self.position_info.address
            )

            self.logger().info(f"Position closing order submitted with ID: {order_id}")

            # Reset all position state
            self.position_opened = False
            self.position_info = None
            self.pool_info = None
            self.out_of_range_start_time = None

            # Log that we're ready to seek a new position
            self.logger().info("Position closed. Ready to seek new position when price conditions are met.")

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")

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

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        lines = []

        if self.position_opened and self.position_info:
            lines.append(f"Position: {self.position_info.address} ({self.config.trading_pair}) on {self.exchange}")

            # Common position info for both CLMM and AMM
            base_amount = Decimal(str(self.position_info.baseTokenAmount))
            quote_amount = Decimal(str(self.position_info.quoteTokenAmount))
            total_quote_value = base_amount * Decimal(str(self.pool_info.price)) + quote_amount

            lines.append(f"Tokens: {base_amount:.6f} {self.base_token} / {quote_amount:.6f} {self.quote_token}")
            lines.append(f"Total Value: {total_quote_value:.2f} {self.quote_token}")

            # Get price range visualization
            if isinstance(self.position_info, CLMMPositionInfo):
                lower_price = Decimal(str(self.position_info.lowerPrice))
                upper_price = Decimal(str(self.position_info.upperPrice))
            else:  # AMMPositionInfo
                target_price = Decimal(str(self.config.target_price))
                width_pct = Decimal(str(self.config.position_width_pct)) / Decimal("100")
                lower_price = target_price * (1 - width_pct)
                upper_price = target_price * (1 + width_pct)

            lines.append(f"Target Price: {self.config.target_price}")
            lines.append(f"Upper Price: {upper_price}")
            lines.append(f"Lower Price: {lower_price}")
            if self.pool_info:
                current_price = Decimal(str(self.pool_info.price))
                price_visualization = self._get_price_range_visualization(current_price, lower_price, upper_price)
                if price_visualization:
                    lines.append(price_visualization)
                lines.append(f"Current Price: {current_price}")

            # Position-specific info
            if isinstance(self.position_info, CLMMPositionInfo):
                if self.position_info.baseFeeAmount > 0 or self.position_info.quoteFeeAmount > 0:
                    lines.append(f"Fees: {self.position_info.baseFeeAmount} {self.base_token} / {self.position_info.quoteFeeAmount} {self.quote_token}")

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
