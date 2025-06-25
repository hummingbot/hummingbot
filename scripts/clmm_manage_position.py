import os
import time
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CLMMPositionManagerConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("meteora/clmm", json_schema_extra={
        "prompt": "CLMM Connector (e.g. meteora/clmm, raydium/clmm)", "prompt_on_new": True})
    network: str = Field("mainnet-beta", json_schema_extra={
        "prompt": "Network (e.g. mainnet-beta, devnet)", "prompt_on_new": True})
    wallet_address: str = Field("", json_schema_extra={
        "prompt": "Wallet address (leave empty to use the default wallet for the chain)", "prompt_on_new": False})
    pool_address: str = Field("9d9mb8kooFfaD3SctgZtkxQypkshx6ezhbKio89ixyy2", json_schema_extra={
        "prompt": "Pool address (e.g. TRUMP-USDC Meteora pool)", "prompt_on_new": True})
    target_price: Decimal = Field(Decimal("10.0"), json_schema_extra={
        "prompt": "Target price to trigger position opening", "prompt_on_new": True})
    trigger_above: bool = Field(False, json_schema_extra={
        "prompt": "Trigger when price rises above target? (True for above/False for below)", "prompt_on_new": True})
    position_width_pct: Decimal = Field(Decimal("10.0"), json_schema_extra={
        "prompt": "Position width in percentage (e.g. 5.0 for ±5% around target price)", "prompt_on_new": True})
    base_token_amount: Decimal = Field(Decimal("0.1"), json_schema_extra={
        "prompt": "Base token amount to add to position (0 for quote only)", "prompt_on_new": True})
    quote_token_amount: Decimal = Field(Decimal("1.0"), json_schema_extra={
        "prompt": "Quote token amount to add to position (0 for base only)", "prompt_on_new": True})
    out_of_range_pct: Decimal = Field(Decimal("1.0"), json_schema_extra={
        "prompt": "Percentage outside range that triggers closing (e.g. 1.0 for 1%)", "prompt_on_new": True})
    out_of_range_secs: int = Field(300, json_schema_extra={
        "prompt": "Seconds price must be out of range before closing (e.g. 300 for 5 min)", "prompt_on_new": True})


class CLMMPositionManager(ScriptStrategyBase):
    """
    This strategy monitors CLMM pool prices, opens a position when a target price is reached,
    and closes the position if the price moves out of range for a specified duration.
    """

    @classmethod
    def init_markets(cls, config: CLMMPositionManagerConfig):
        # For gateway connectors, use connector_network format
        market_name = f"{config.connector}_{config.network}"
        cls.markets = {market_name: set()}  # Empty set since we're not trading pairs directly

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CLMMPositionManagerConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = f"{config.connector}_{config.network}"

        # Get the gateway LP connector from connectors
        self.gateway_lp = self.connectors.get(self.exchange)
        if not self.gateway_lp:
            self.logger().error(f"Gateway LP connector {self.exchange} not found!")
            return

        # State tracking
        self.position_opened = False
        self.position_opening = False
        self.position_closing = False
        self.position_address = None
        self.pool_info = None
        self.base_token = None
        self.quote_token = None
        self.last_price = None
        self.position_lower_price = None
        self.position_upper_price = None
        self.out_of_range_start_time = None

        # Log startup information
        self.logger().info("Starting CLMMPositionManager strategy")
        self.logger().info(f"Connector: {self.config.connector}")
        self.logger().info(f"Network: {self.config.network}")
        self.logger().info(f"Pool address: {self.config.pool_address}")
        self.logger().info(f"Target price: {self.config.target_price}")
        condition = "rises above" if self.config.trigger_above else "falls below"
        self.logger().info(f"Will open position when price {condition} target")
        self.logger().info(f"Position width: ±{self.config.position_width_pct}%")
        self.logger().info(f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds")

        # Check Gateway status
        safe_ensure_future(self.check_gateway_and_fetch_pool_info())

    async def check_gateway_and_fetch_pool_info(self):
        """Check if Gateway server is online and fetch pool information"""
        self.logger().info("Checking Gateway server status...")
        try:
            gateway = GatewayHttpClient.get_instance()
            if await gateway.ping_gateway():
                self.logger().info("Gateway server is online!")
                # Fetch pool info to get token information
                await self.fetch_pool_info()
            else:
                self.logger().error("Gateway server is offline! Make sure Gateway is running before using this strategy.")
        except Exception as e:
            self.logger().error(f"Error connecting to Gateway server: {str(e)}")

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        try:
            self.logger().info(f"Fetching information for pool {self.config.pool_address}...")
            pool_info = await GatewayHttpClient.get_instance().connector_request(
                "get",
                self.config.connector,
                "pool-info",
                {"network": self.config.network, "poolAddress": self.config.pool_address}
            )

            if not pool_info:
                self.logger().error(f"Failed to get pool information for {self.config.pool_address}")
                return

            self.pool_info = pool_info

            # Extract token information (addresses for later use)
            self.base_token_address = pool_info.get("baseTokenAddress")
            self.quote_token_address = pool_info.get("quoteTokenAddress")

            # For now, hardcode the token symbols based on the pool
            # In a real implementation, you'd get these from the pool info or token list
            # This is a SOL-USDC pool based on the pool address in the config
            self.base_token = "SOL"
            self.quote_token = "USDC"

            # Extract current price - it's at the top level of the response
            if "price" in pool_info:
                try:
                    self.last_price = Decimal(str(pool_info["price"]))
                except (ValueError, TypeError) as e:
                    self.logger().error(f"Error converting price value: {e}")
            else:
                self.logger().error("No price found in pool info response")

        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")

    async def fetch_position_info(self):
        """Fetch actual position information including price bounds"""
        if not self.position_address:
            return

        try:
            self.logger().info(f"Fetching position info for {self.position_address}...")
            position_info = await GatewayHttpClient.get_instance().connector_request(
                "get",
                self.config.connector,
                "position-info",
                {
                    "network": self.config.network,
                    "positionAddress": self.position_address,
                    "walletAddress": self.gateway_lp.address  # Use the gateway connector's address
                }
            )

            if not position_info:
                self.logger().error(f"Failed to get position information for {self.position_address}")
                return

            # Extract actual position price bounds
            if "lowerPrice" in position_info and "upperPrice" in position_info:
                self.position_lower_price = float(position_info["lowerPrice"])
                self.position_upper_price = float(position_info["upperPrice"])
                self.logger().info(f"Position actual bounds: {self.position_lower_price} to {self.position_upper_price}")
            else:
                self.logger().error("Position info missing price bounds")

        except Exception as e:
            self.logger().error(f"Error fetching position info: {str(e)}")

    def on_tick(self):
        # Check price and position status on each tick
        if not self.position_opened and not self.position_opening:
            safe_ensure_future(self.check_price_and_open_position())
        elif self.position_opened and not self.position_closing:
            safe_ensure_future(self.monitor_position())

    async def check_price_and_open_position(self):
        """Check current price and open position if target is reached"""
        if self.position_opening or self.position_opened:
            return

        self.position_opening = True

        try:
            # Fetch current pool info to get the latest price
            await self.fetch_pool_info()

            if not self.last_price:
                self.logger().warning("Unable to get current price")
                self.position_opening = False
                return

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
            else:
                self.logger().info(f"Current price: {self.last_price}, Target: {self.config.target_price}, "
                                   f"Condition not met yet.")
                self.position_opening = False

        except Exception as e:
            self.logger().error(f"Error in check_price_and_open_position: {str(e)}")
            self.position_opening = False

    async def open_position(self):
        """Open a concentrated liquidity position around the target price"""
        if self.position_opening or self.position_opened:
            return

        self.position_opening = True

        try:
            # Get the latest pool price before creating the position
            await self.fetch_pool_info()

            if not self.last_price:
                self.logger().error("Cannot open position: Failed to get current pool price")
                self.position_opening = False
                return

            # Use the gateway LP connector to open position
            # Create a trading pair from pool info
            trading_pair = f"{self.base_token}-{self.quote_token}"

            self.logger().info(f"Opening position on {trading_pair} around price {self.last_price} with width {self.config.position_width_pct}%")

            # Use the open_position method from gateway_lp
            order_id = self.gateway_lp.open_position(
                trading_pair=trading_pair,
                price=float(self.last_price),
                spread_pct=float(self.config.position_width_pct),
                base_token_amount=float(self.config.base_token_amount) if self.config.base_token_amount > 0 else None,
                quote_token_amount=float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else None,
                slippage_pct=0.5,
                pool_address=self.config.pool_address  # Pass the pool address
            )

            self.logger().info(f"Position opening order submitted: {order_id}")

            # Store order ID to track when it's filled
            self.opening_order_id = order_id

        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")
            self.position_opening = False

    async def monitor_position(self):
        """Monitor the position and price to determine if position should be closed"""
        if not self.position_address or self.position_closing:
            return

        try:
            # Fetch current pool info to get the latest price
            await self.fetch_pool_info()

            if not self.last_price:
                return

            # Check if price is outside position range by more than out_of_range_pct
            out_of_range = False
            current_time = time.time()

            lower_bound_with_buffer = self.position_lower_price * (1 - float(self.config.out_of_range_pct) / 100.0)
            upper_bound_with_buffer = self.position_upper_price * (1 + float(self.config.out_of_range_pct) / 100.0)

            if float(self.last_price) < lower_bound_with_buffer:
                out_of_range = True
                elapsed = int(current_time - self.out_of_range_start_time) if self.out_of_range_start_time else 0
                self.logger().info(f"Price {self.last_price} is below position lower bound {self.position_lower_price:.6f} by more than {self.config.out_of_range_pct}% buffer (threshold: {lower_bound_with_buffer:.6f}) - Out of range for {elapsed}/{self.config.out_of_range_secs}s")
            elif float(self.last_price) > upper_bound_with_buffer:
                out_of_range = True
                elapsed = int(current_time - self.out_of_range_start_time) if self.out_of_range_start_time else 0
                self.logger().info(f"Price {self.last_price} is above position upper bound {self.position_upper_price:.6f} by more than {self.config.out_of_range_pct}% buffer (threshold: {upper_bound_with_buffer:.6f}) - Out of range for {elapsed}/{self.config.out_of_range_secs}s")

            # Track out-of-range time
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
                buffer_info = f" with {self.config.out_of_range_pct}% buffer" if self.config.out_of_range_pct > 0 else ""
                self.logger().info(f"Price {self.last_price} is within position range [{self.position_lower_price:.6f}, {self.position_upper_price:.6f}]{buffer_info}")

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the concentrated liquidity position"""
        if not self.position_address or self.position_closing:
            return

        self.position_closing = True

        try:
            # Create a trading pair from pool info
            trading_pair = f"{self.base_token}-{self.quote_token}"

            self.logger().info(f"Closing position {self.position_address}...")

            # Use the close_position method from gateway_lp
            order_id = self.gateway_lp.close_position(
                trading_pair=trading_pair,
                position_address=self.position_address
            )

            self.logger().info(f"Position closing order submitted: {order_id}")

            # Store order ID to track when it's closed
            self.closing_order_id = order_id

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")
            self.position_closing = False

    def did_fill_order(self, event):
        """
        Called when an order is filled.
        """
        if hasattr(self, 'opening_order_id') and event.order_id == self.opening_order_id:
            self.logger().info(f"Position opened successfully! Order {event.order_id} filled.")
            self.position_opened = True
            self.position_opening = False
            # Extract position address from event if available
            if hasattr(event, 'exchange_order_id'):
                self.position_address = event.exchange_order_id
                # Fetch actual position info to get the exact price bounds
                safe_ensure_future(self.fetch_position_info())
        elif hasattr(self, 'closing_order_id') and event.order_id == self.closing_order_id:
            self.logger().info(f"Position closed successfully! Order {event.order_id} filled.")
            # Reset position state
            self.position_opened = False
            self.position_closing = False
            self.position_address = None
            self.position_lower_price = None
            self.position_upper_price = None
            self.out_of_range_start_time = None

    def did_fail_order(self, event):
        """
        Called when an order fails.
        """
        if hasattr(self, 'opening_order_id') and event.order_id == self.opening_order_id:
            self.logger().error(f"Failed to open position! Order {event.order_id} failed.")
            self.position_opening = False
        elif hasattr(self, 'closing_order_id') and event.order_id == self.closing_order_id:
            self.logger().error(f"Failed to close position! Order {event.order_id} failed.")
            self.position_closing = False

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        lines = []
        connector_network = f"{self.config.connector}_{self.config.network}"

        if self.position_opened:
            lines.append(f"Position is open on {connector_network}")
            lines.append(f"Position address: {self.position_address}")
            if self.position_lower_price and self.position_upper_price:
                lines.append(f"Position price range: {self.position_lower_price:.6f} to {self.position_upper_price:.6f}")
            lines.append(f"Current price: {self.last_price}")

            # Show buffer info
            if self.config.out_of_range_pct > 0 and self.position_lower_price and self.position_upper_price:
                lower_bound_with_buffer = self.position_lower_price * (1 - float(self.config.out_of_range_pct) / 100.0)
                upper_bound_with_buffer = self.position_upper_price * (1 + float(self.config.out_of_range_pct) / 100.0)
                lines.append(f"Buffer zone: {lower_bound_with_buffer:.6f} to {upper_bound_with_buffer:.6f} ({self.config.out_of_range_pct}%)")

            # Show position status
            if self.out_of_range_start_time:
                elapsed = time.time() - self.out_of_range_start_time
                lines.append(f"⚠️  Price out of range for {elapsed:.0f}/{self.config.out_of_range_secs} seconds")
                if elapsed >= self.config.out_of_range_secs * 0.8:  # Warning when close to closing
                    lines.append("⏰ Position will close soon!")
            else:
                # Check if price is in position range vs buffer range
                if self.position_lower_price and self.position_upper_price and self.last_price:
                    if self.position_lower_price <= float(self.last_price) <= self.position_upper_price:
                        lines.append("✅ Price is within position range")
                    else:
                        lines.append("⚠️  Price is outside position range but within buffer")
        elif self.position_opening:
            lines.append(f"Opening position on {connector_network}...")
        elif self.position_closing:
            lines.append(f"Closing position on {connector_network}...")
        else:
            lines.append(f"Monitoring pool on {connector_network}")
            lines.append(f"Pool address: {self.config.pool_address}")
            lines.append(f"Current price: {self.last_price}")
            lines.append(f"Target price: {self.config.target_price}")
            condition = "rises above" if self.config.trigger_above else "falls below"
            lines.append(f"Will open position when price {condition} target")

        return "\n".join(lines)
