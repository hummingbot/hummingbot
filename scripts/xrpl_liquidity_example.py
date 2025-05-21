import os
import time
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    AddLiquidityResponse,
    PoolInfo,
    QuoteLiquidityResponse,
    RemoveLiquidityResponse,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class XRPLTriggeredLiquidityConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    trading_pair: str = Field(
        "XRP-RLUSD", json_schema_extra={"prompt": "Trading pair (e.g. XRP-RLUSD)", "prompt_on_new": True}
    )
    target_price: Decimal = Field(
        Decimal("1.0"), json_schema_extra={"prompt": "Target price to trigger position opening", "prompt_on_new": True}
    )
    trigger_above: bool = Field(
        False,
        json_schema_extra={
            "prompt": "Trigger when price rises above target? (True for above/False for below)",
            "prompt_on_new": True,
        },
    )
    position_width_pct: Decimal = Field(
        Decimal("10.0"),
        json_schema_extra={
            "prompt": "Position width in percentage (e.g. 5.0 for ±5% around target price)",
            "prompt_on_new": True,
        },
    )
    total_amount_in_quote: Decimal = Field(
        Decimal("1.0"), json_schema_extra={"prompt": "Total amount in quote token", "prompt_on_new": True}
    )
    out_of_range_pct: Decimal = Field(
        Decimal("1.0"),
        json_schema_extra={
            "prompt": "Percentage outside range that triggers closing (e.g. 1.0 for 1%)",
            "prompt_on_new": True,
        },
    )
    out_of_range_secs: int = Field(
        300,
        json_schema_extra={
            "prompt": "Seconds price must be out of range before closing (e.g. 300 for 5 min)",
            "prompt_on_new": True,
        },
    )
    refresh_interval_secs: int = Field(
        15,
        json_schema_extra={
            "prompt": "Refresh interval in seconds",
            "prompt_on_new": True,
        },
    )


class XRPLTriggeredLiquidity(ScriptStrategyBase):
    """
    This strategy monitors XRPL DEX prices and add liquidity to AMM Pools when the price is within a certain range.
    Remove liquidity if the price is outside the range.
    It uses a connector to get the current price and manage liquidity in AMM Pools
    """

    @classmethod
    def init_markets(cls, config: XRPLTriggeredLiquidityConfig):
        cls.markets = {"xrpl": {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: XRPLTriggeredLiquidityConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = "xrpl"
        self.base, self.quote = self.config.trading_pair.split("-")

        # State tracking
        self.connector_ready = False
        self.connector_instance: XrplExchange = self.connectors[self.exchange]
        self.position_opened = False
        self.position_opening = False
        self.position_closing = False
        self.wallet_address = None
        self.pool_info = None
        self.pool_balance = None
        self.last_price = None
        self.position_lower_price = None
        self.position_upper_price = None
        self.out_of_range_start_time = None
        self.last_refresh_time = 0  # Track last refresh time

        # Log startup information
        self.logger().info("Starting XRPLTriggeredLiquidity strategy")
        self.logger().info(f"Trading pair: {self.config.trading_pair}")
        self.logger().info(f"Target price: {self.config.target_price}")
        condition = "rises above" if self.config.trigger_above else "falls below"
        self.logger().info(f"Will open position when price {condition} target")
        self.logger().info(f"Position width: ±{self.config.position_width_pct}%")
        self.logger().info(f"Total amount in quote: {self.config.total_amount_in_quote} {self.quote}")
        self.logger().info(
            f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds"
        )

        # Check connector status
        self.check_connector_status()

    def check_connector_status(self):
        """Check if the connector is ready"""
        if not self.connectors[self.exchange].ready:
            self.logger().info("Connector not ready yet, waiting...")
            self.connector_ready = False
        else:
            self.connector_ready = True
            self.wallet_address = self.connectors[self.exchange].auth.get_wallet().address

    def on_tick(self):
        """Main loop to check price and manage liquidity"""
        current_time = time.time()
        if current_time - self.last_refresh_time < self.config.refresh_interval_secs:
            return
        self.last_refresh_time = current_time

        if not self.connector_ready or not self.wallet_address:
            self.check_connector_status()
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        # Check price and position status on each tick
        if not self.position_opened and not self.position_opening:
            safe_ensure_future(self.check_price_and_open_position())
        elif self.position_opened and not self.position_closing:
            safe_ensure_future(self.monitor_position())
            safe_ensure_future(self.check_position_balance())

    async def on_stop(self):
        """Stop the strategy and close any open positions"""
        if self.position_opened:
            self.logger().info("Stopping strategy, closing position...")
            safe_ensure_future(self.close_position())
        else:
            self.logger().info("Stopping strategy, no open position to close.")
        await super().on_stop()

    async def check_price_and_open_position(self):
        """Check the current price and open a position if within range"""
        if self.position_opening or self.position_opened:
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        self.position_opening = True

        try:
            pool_info: PoolInfo = await self.connector_instance.amm_get_pool_info(trading_pair=self.config.trading_pair)
            self.pool_info = pool_info
            self.last_price = pool_info.price

            # Check if price condition is met
            condition_met = False
            if self.config.trigger_above and self.last_price > self.config.target_price:
                condition_met = True
                self.logger().info(f"Price rose above target: {self.last_price} > {self.config.target_price}")
            elif not self.config.trigger_above and self.last_price < self.config.target_price:
                condition_met = True
                self.logger().info(f"Price fell below target: {self.last_price} < {self.config.target_price}")

            if condition_met:
                self.logger().info("Price condition met! Opening position...")
                self.position_opening = False  # Reset flag so open_position can set it
                await self.open_position()
                await self.check_position_balance()
            else:
                self.logger().info(
                    f"Current price: {self.last_price}, Target: {self.config.target_price}, " f"Condition not met yet."
                )
                self.position_opening = False

        except Exception as e:
            self.logger().error(f"Error in check_price_and_open_position: {str(e)}")
            self.position_opening = False

    async def open_position(self):
        """Open a liquidity position around the target price"""
        if self.position_opening or self.position_opened:
            return

        if self.pool_info is None:
            self.logger().error("Cannot open position: Failed to get current pool info")
            self.position_opening = False
            return

        if self.wallet_address is None:
            self.logger().error("Cannot open position: Failed to get wallet address")
            self.position_opening = False
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        self.position_opening = True

        try:
            if not self.last_price:
                self.logger().error("Cannot open position: Failed to get current pool price")
                self.position_opening = False
                return

            # Calculate position price range based on CURRENT pool price instead of target
            current_price = float(self.last_price)
            width_pct = float(self.config.position_width_pct) / 100.0

            lower_price = current_price * (1 - width_pct)
            upper_price = current_price * (1 + width_pct)

            self.position_lower_price = lower_price
            self.position_upper_price = upper_price

            # Calculate base and quote token amounts from last_price and the total_amount_in_quote
            total_amount_in_quote = float(self.config.total_amount_in_quote)
            quote_amount_per_side = total_amount_in_quote / 2
            if total_amount_in_quote > 0:
                base_token_amount = quote_amount_per_side / current_price
                quote_token_amount = quote_amount_per_side
            else:
                # Log warning if total_amount_in_quote is 0 and return
                self.logger().warning("total_amount_in_quote is 0, cannot calculate base and quote token amounts.")
                self.position_opening = False
                return

            self.logger().info(
                f"Opening position around current price {current_price} with range: {lower_price} to {upper_price}"
            )

            quote: QuoteLiquidityResponse = await self.connector_instance.amm_quote_add_liquidity(
                pool_address=self.pool_info.address,
                base_token_amount=Decimal(base_token_amount),
                quote_token_amount=Decimal(quote_token_amount),
                slippage_pct=Decimal("0.01"),
            )

            add_liquidity_response: AddLiquidityResponse = await self.connector_instance.amm_add_liquidity(
                pool_address=self.pool_info.address,
                wallet_address=self.wallet_address,
                base_token_amount=quote.base_token_amount,
                quote_token_amount=quote.quote_token_amount,
                slippage_pct=Decimal("0.01"),
            )

            # Check if any amount added or not, if not then position has not been opened
            if (
                add_liquidity_response.base_token_amount_added == 0
                and add_liquidity_response.quote_token_amount_added == 0
            ):
                self.logger().error("Failed to open position: No tokens added.")
                self.position_opening = False
                return

            # Update position state
            self.position_opened = True
            self.position_opening = False
            self.logger().info(
                f"Position opened successfully! Base: {add_liquidity_response.base_token_amount_added}, "
                f"Quote: {add_liquidity_response.quote_token_amount_added}"
            )

        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")
        finally:
            # Only clear position_opening flag if position is not opened
            if not self.position_opened:
                self.position_opening = False

    async def monitor_position(self):
        """Monitor the position and price to determine if position should be closed"""
        if self.position_closing:
            return

        if self.position_lower_price is None or self.position_upper_price is None:
            self.logger().error("Cannot monitor position: Failed to get position price range")
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        try:
            # Fetch current pool info to get the latest price
            pool_info: PoolInfo = await self.connector_instance.amm_get_pool_info(trading_pair=self.config.trading_pair)
            self.pool_info = pool_info
            self.last_price = pool_info.price

            if not self.last_price:
                return

            # Check if price is outside position range by more than out_of_range_pct
            out_of_range = False

            lower_bound_with_buffer = self.position_lower_price * (1 - float(self.config.out_of_range_pct) / 100.0)
            upper_bound_with_buffer = self.position_upper_price * (1 + float(self.config.out_of_range_pct) / 100.0)

            if float(self.last_price) < lower_bound_with_buffer:
                out_of_range = True
                out_of_range_amount = (
                    (lower_bound_with_buffer - float(self.last_price)) / self.position_lower_price * 100
                )
                self.logger().info(
                    f"Price {self.last_price} is below position lower bound with buffer {lower_bound_with_buffer} by {out_of_range_amount:.2f}%"
                )
            elif float(self.last_price) > upper_bound_with_buffer:
                out_of_range = True
                out_of_range_amount = (
                    (float(self.last_price) - upper_bound_with_buffer) / self.position_upper_price * 100
                )
                self.logger().info(
                    f"Price {self.last_price} is above position upper bound with buffer {upper_bound_with_buffer} by {out_of_range_amount:.2f}%"
                )

            # Track out-of-range time
            current_time = time.time()
            if out_of_range:
                if self.out_of_range_start_time is None:
                    self.out_of_range_start_time = current_time
                    self.logger().info("Price moved out of range (with buffer). Starting timer...")

                # Check if price has been out of range for sufficient time
                elapsed_seconds = current_time - self.out_of_range_start_time
                if elapsed_seconds >= self.config.out_of_range_secs:
                    self.logger().info(
                        f"Price has been out of range for {elapsed_seconds:.0f} seconds (threshold: {self.config.out_of_range_secs} seconds)"
                    )
                    self.logger().info("Closing position...")
                    await self.close_position()
                else:
                    self.logger().info(
                        f"Price out of range for {elapsed_seconds:.0f} seconds, waiting until {self.config.out_of_range_secs} seconds..."
                    )
            else:
                # Reset timer if price moves back into range
                if self.out_of_range_start_time is not None:
                    self.logger().info("Price moved back into range (with buffer). Resetting timer.")
                    self.out_of_range_start_time = None

                # Add log statement when price is in range
                self.logger().info(
                    f"Price {self.last_price} is within range: {lower_bound_with_buffer:.6f} to {upper_bound_with_buffer:.6f}"
                )

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the concentrated liquidity position"""
        if self.position_closing:
            return

        if self.wallet_address is None:
            self.logger().error("Cannot close position: Failed to get wallet address")
            self.position_closing = False
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        self.position_closing = True
        position_closed = False

        try:
            if not self.pool_info:
                self.logger().error("Cannot close position: Failed to get current pool info")
                self.position_closing = False
                return

            # Remove liquidity from the pool
            remove_response: RemoveLiquidityResponse = await self.connector_instance.amm_remove_liquidity(
                pool_address=self.pool_info.address,
                wallet_address=self.wallet_address,
                percentage_to_remove=Decimal("100"),
            )

            # Check if any amount removed or not, if not then position has not been closed
            if remove_response.base_token_amount_removed == 0 and remove_response.quote_token_amount_removed == 0:
                self.logger().error("Failed to close position: No tokens removed.")
                self.position_closing = False
                return

            position_closed = True
            self.logger().info(
                f"Position closed successfully! {self.base}: {remove_response.base_token_amount_removed:.6f}, "
                f"{self.quote}: {remove_response.quote_token_amount_removed:.6f}, "
            )

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")

        finally:
            if position_closed:
                self.position_closing = False
                self.position_opened = False
            else:
                self.position_closing = False

    async def check_position_balance(self):
        """Check the balance of the position"""
        if not self.pool_info:
            self.logger().error("Cannot check position balance: Failed to get current pool info")
            return

        if self.wallet_address is None:
            self.logger().error("Cannot check position balance: Failed to get wallet address")
            return

        if self.connector_instance is None:
            self.logger().error("Connector instance is not available.")
            return

        try:
            pool_balance = await self.connector_instance.amm_get_balance(
                pool_address=self.pool_info.address,
                wallet_address=self.wallet_address,
            )
            self.pool_balance = pool_balance

        except Exception as e:
            self.logger().error(f"Error checking position balance: {str(e)}")

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if not self.connector_ready:
            return "Connector is not available. Please check your connection."

        if not self.wallet_address:
            return "No wallet found yet."

        if self.pool_info is None:
            return "No pool info found yet."

        lines = []

        if self.position_opened:
            lines.append(f"Position is open on XRPL: {self.config.trading_pair} pool {self.pool_info.address}")
            lines.append(f"Position price range: {self.position_lower_price:.6f} to {self.position_upper_price:.6f}")
            lines.append(f"Current price: {self.last_price}")

            if self.out_of_range_start_time:
                elapsed = time.time() - self.out_of_range_start_time
                lines.append(f"Price out of range for {elapsed:.0f}/{self.config.out_of_range_secs} seconds")

            if self.pool_balance:
                lines.append("Pool balance:")
                lines.append(f"  {self.pool_balance['base_token_lp_amount']:.5f} {self.base}")
                lines.append(f"  {self.pool_balance['quote_token_lp_amount']:.5f} {self.quote}")
                lines.append(f"  {self.pool_balance['lp_token_amount']:.5f} LP tokens")
                lines.append(f"  {self.pool_balance['lp_token_amount_pct']:.5f} LP token percentage")
        elif self.position_opening:
            lines.append(f"Opening position on {self.config.trading_pair} pool {self.pool_info.address} ...")
        elif self.position_closing:
            lines.append(f"Closing position on {self.config.trading_pair} pool {self.pool_info.address} ...")
        else:
            lines.append(f"Monitoring {self.config.trading_pair} pool {self.pool_info.address}")
            lines.append(f"Current price: {self.last_price}")
            lines.append(f"Target price: {self.config.target_price}")
            condition = "rises above" if self.config.trigger_above else "falls below"
            lines.append(f"Will open position when price {condition} target")

        return "\n".join(lines)
