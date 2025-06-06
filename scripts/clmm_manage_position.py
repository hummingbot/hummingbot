import asyncio
import os
import time
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CLMMPositionManagerConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("meteora/clmm", json_schema_extra={
        "prompt": "CLMM Connector (e.g. meteora/clmm, raydium/clmm)", "prompt_on_new": True})
    chain: str = Field("solana", json_schema_extra={
        "prompt": "Chain (e.g. solana)", "prompt_on_new": False})
    network: str = Field("mainnet-beta", json_schema_extra={
        "prompt": "Network (e.g. mainnet-beta)", "prompt_on_new": False})
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
        # Nothing to initialize for CLMM as it uses Gateway API directly
        cls.markets = {}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CLMMPositionManagerConfig):
        super().__init__(connectors)
        self.config = config

        # State tracking
        self.gateway_ready = False
        self.position_opened = False
        self.position_opening = False
        self.position_closing = False
        self.position_address = None
        self.wallet_address = None
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
        self.logger().info(f"Chain: {self.config.chain}")
        self.logger().info(f"Network: {self.config.network}")
        self.logger().info(f"Pool address: {self.config.pool_address}")
        self.logger().info(f"Target price: {self.config.target_price}")
        condition = "rises above" if self.config.trigger_above else "falls below"
        self.logger().info(f"Will open position when price {condition} target")
        self.logger().info(f"Position width: ±{self.config.position_width_pct}%")
        self.logger().info(f"Will close position if price is outside range by {self.config.out_of_range_pct}% for {self.config.out_of_range_secs} seconds")

        # Check Gateway status
        safe_ensure_future(self.check_gateway_status())

    async def check_gateway_status(self):
        """Check if Gateway server is online and verify wallet connection"""
        self.logger().info("Checking Gateway server status...")
        try:
            gateway_http_client = GatewayHttpClient.get_instance()
            if await gateway_http_client.ping_gateway():
                self.gateway_ready = True
                self.logger().info("Gateway server is online!")

                # Verify wallet connections
                connector = self.config.connector
                chain = self.config.chain
                network = self.config.network
                gateway_connections_conf = GatewayConnectionSetting.load()

                if len(gateway_connections_conf) < 1:
                    self.logger().error("No wallet connections found. Please connect a wallet using 'gateway connect'.")
                else:
                    wallet = [w for w in gateway_connections_conf
                              if w["chain"] == chain and w["connector"] == connector and w["network"] == network]

                    if not wallet:
                        self.logger().error(f"No wallet found for {chain}/{connector}/{network}. "
                                            f"Please connect using 'gateway connect'.")
                    else:
                        self.wallet_address = wallet[0]["wallet_address"]
                        self.logger().info(f"Found wallet connection: {self.wallet_address}")

                        # Get pool info to get token information
                        await self.fetch_pool_info()
            else:
                self.gateway_ready = False
                self.logger().error("Gateway server is offline! Make sure Gateway is running before using this strategy.")
        except Exception as e:
            self.gateway_ready = False
            self.logger().error(f"Error connecting to Gateway server: {str(e)}")

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        try:
            self.logger().info(f"Fetching information for pool {self.config.pool_address}...")
            pool_info = await GatewayHttpClient.get_instance().pool_info(
                self.config.connector,
                self.config.network,
                self.config.pool_address
            )

            if not pool_info:
                self.logger().error(f"Failed to get pool information for {self.config.pool_address}")
                return

            self.pool_info = pool_info

            # Extract token information
            self.base_token = pool_info.get("baseTokenAddress")
            self.quote_token = pool_info.get("quoteTokenAddress")

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
        if not self.position_address or not self.wallet_address:
            return

        try:
            self.logger().info(f"Fetching position info for {self.position_address}...")
            position_info = await GatewayHttpClient.get_instance().clmm_position_info(
                connector=self.config.connector,
                network=self.config.network,
                position_address=self.position_address,
                wallet_address=self.wallet_address
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
        # Don't proceed if Gateway is not ready
        if not self.gateway_ready or not self.wallet_address:
            return

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

            # Calculate position price range based on CURRENT pool price
            current_price = float(self.last_price)
            width_pct = float(self.config.position_width_pct) / 100.0

            lower_price = current_price * (1 - width_pct)
            upper_price = current_price * (1 + width_pct)

            self.logger().info(f"Opening position around current price {current_price} with requested range: {lower_price} to {upper_price}")

            # Open position - only send one transaction
            response = await GatewayHttpClient.get_instance().clmm_open_position(
                connector=self.config.connector,
                network=self.config.network,
                wallet_address=self.wallet_address,
                pool_address=self.config.pool_address,
                lower_price=lower_price,
                upper_price=upper_price,
                base_token_amount=float(self.config.base_token_amount) if self.config.base_token_amount > 0 else None,
                quote_token_amount=float(self.config.quote_token_amount) if self.config.quote_token_amount > 0 else None,
                slippage_pct=0.5  # Default slippage
            )

            self.logger().info(f"Position opening response received: {response}")

            # Check for signature
            if "signature" in response:
                signature = response["signature"]
                self.logger().info(f"Position opening transaction submitted: {signature}")

                # Store position address from response
                if "positionAddress" in response:
                    potential_position_address = response["positionAddress"]
                    self.logger().info(f"Position address from transaction (pending confirmation): {potential_position_address}")
                    # Store it temporarily in case we need it
                    self.position_address = potential_position_address

                # Poll for transaction result - this is async and will wait
                tx_success = await self.poll_transaction(signature)

                if tx_success:
                    # Transaction confirmed successfully
                    self.position_opened = True
                    self.logger().info(f"Position opened successfully! Position address: {self.position_address}")

                    # Fetch actual position info to get the exact price bounds
                    await self.fetch_position_info()
                else:
                    # Transaction failed or still pending after max attempts
                    self.logger().warning("Transaction did not confirm successfully within polling period.")
                    self.logger().warning("Position may still confirm later. Check your wallet for status.")
                    # Clear the position address since we're not sure of its status
                    self.position_address = None
            else:
                # No transaction hash in response
                self.logger().error(f"Failed to open position. No signature in response: {response}")
        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")
        finally:
            # Only clear position_opening flag if position is not opened
            if not self.position_opened:
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
        max_retries = 3
        retry_count = 0
        position_closed = False

        try:
            # Close position with retry logic
            while retry_count < max_retries and not position_closed:
                if retry_count > 0:
                    self.logger().info(f"Retrying position closing (attempt {retry_count + 1}/{max_retries})...")

                # Close position
                self.logger().info(f"Closing position {self.position_address}...")
                response = await GatewayHttpClient.get_instance().clmm_close_position(
                    connector=self.config.connector,
                    network=self.config.network,
                    wallet_address=self.wallet_address,
                    position_address=self.position_address
                )

                # Check response
                if "signature" in response:
                    signature = response["signature"]
                    self.logger().info(f"Position closing transaction submitted: {signature}")

                    # Poll for transaction result
                    tx_success = await self.poll_transaction(signature)

                    if tx_success:
                        self.logger().info("Position closed successfully!")
                        position_closed = True

                        # Reset position state
                        self.position_opened = False
                        self.position_address = None
                        self.position_lower_price = None
                        self.position_upper_price = None
                        self.out_of_range_start_time = None
                        break  # Exit retry loop on success
                    else:
                        # Transaction failed, increment retry counter
                        retry_count += 1
                        self.logger().info(f"Transaction failed, will retry. {max_retries - retry_count} attempts remaining.")
                        await asyncio.sleep(2)  # Short delay before retry
                else:
                    self.logger().error(f"Failed to close position. No signature in response: {response}")
                    retry_count += 1

            if not position_closed and retry_count >= max_retries:
                self.logger().error(f"Failed to close position after {max_retries} attempts. Giving up.")

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")

        finally:
            if position_closed:
                self.position_closing = False
                self.position_opened = False
            else:
                self.position_closing = False

    async def poll_transaction(self, signature):
        """Continuously polls for transaction status until completion or max attempts reached"""
        if not signature:
            return False

        self.logger().info(f"Polling for transaction status: {signature}")

        # Transaction status codes
        # -1 = FAILED
        # 0 = UNCONFIRMED
        # 1 = CONFIRMED

        max_poll_attempts = 60  # Increased from 30 to allow more time for confirmation
        poll_attempts = 0

        while poll_attempts < max_poll_attempts:
            poll_attempts += 1
            try:
                # Use the get_transaction_status method to check transaction status
                poll_data = await GatewayHttpClient.get_instance().get_transaction_status(
                    chain=self.config.chain,
                    network=self.config.network,
                    transaction_hash=signature,
                )

                transaction_status = poll_data.get("txStatus")

                if transaction_status == 1:  # CONFIRMED
                    self.logger().info(f"Transaction {signature} confirmed successfully!")
                    return True
                elif transaction_status == -1:  # FAILED
                    self.logger().error(f"Transaction {signature} failed!")
                    self.logger().error(f"Details: {poll_data}")
                    return False
                elif transaction_status == 0:  # UNCONFIRMED
                    self.logger().info(f"Transaction {signature} still pending... (attempt {poll_attempts}/{max_poll_attempts})")
                    # Continue polling for unconfirmed transactions
                    await asyncio.sleep(5)  # Wait before polling again
                else:
                    self.logger().warning(f"Unknown txStatus: {transaction_status}")
                    self.logger().info(f"{poll_data}")
                    # Continue polling for unknown status
                    await asyncio.sleep(5)

            except Exception as e:
                self.logger().error(f"Error polling transaction: {str(e)}")
                await asyncio.sleep(5)  # Add delay to avoid rapid retries on error

        # If we reach here, we've exceeded maximum polling attempts
        self.logger().warning(f"Transaction {signature} still unconfirmed after {max_poll_attempts} polling attempts")
        # Return false but don't mark as definitely failed
        return False

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if not self.gateway_ready:
            return "Gateway server is not available. Please start Gateway and restart the strategy."

        if not self.wallet_address:
            return "No wallet connected. Please connect a wallet using 'gateway connect'."

        lines = []
        connector_chain_network = f"{self.config.connector}_{self.config.chain}_{self.config.network}"

        if self.position_opened:
            lines.append(f"Position is open on {connector_chain_network}")
            lines.append(f"Position address: {self.position_address}")
            lines.append(f"Position price range: {self.position_lower_price:.6f} to {self.position_upper_price:.6f}")
            lines.append(f"Current price: {self.last_price}")

            # Show buffer info
            if self.config.out_of_range_pct > 0:
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
                if self.position_lower_price and self.position_upper_price:
                    if self.last_price and self.position_lower_price <= float(self.last_price) <= self.position_upper_price:
                        lines.append("✅ Price is within position range")
                    else:
                        lines.append("⚠️  Price is outside position range but within buffer")
        elif self.position_opening:
            lines.append(f"Opening position on {connector_chain_network}...")
        elif self.position_closing:
            lines.append(f"Closing position on {connector_chain_network}...")
        else:
            lines.append(f"Monitoring {self.base_token}-{self.quote_token} pool on {connector_chain_network}")
            lines.append(f"Pool address: {self.config.pool_address}")
            lines.append(f"Current price: {self.last_price}")
            lines.append(f"Target price: {self.config.target_price}")
            condition = "rises above" if self.config.trigger_above else "falls below"
            lines.append(f"Will open position when price {condition} target")

        return "\n".join(lines)
