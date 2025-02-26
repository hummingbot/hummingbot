import asyncio
import os
import time
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CLMMPositionManagerConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("meteora", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "CLMM Connector (e.g. meteora, raydium-clmm)"))
    chain: str = Field("solana", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Chain (e.g. solana)"))
    network: str = Field("mainnet-beta", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Network (e.g. mainnet-beta)"))
    pool_address: str = Field("9d9mb8kooFfaD3SctgZtkxQypkshx6ezhbKio89ixyy2", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Pool address"))
    target_price: Decimal = Field(Decimal("13.0"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Target price to trigger position opening"))
    trigger_above: bool = Field(False, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trigger when price rises above target? (True for above/False for below)"))
    position_width_pct: Decimal = Field(Decimal("10.0"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position width in percentage (e.g. 5.0 for ±5% around target price)"))
    base_token_amount: Decimal = Field(Decimal("0.2"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Base token amount to add to position (0 for quote only)"))
    quote_token_amount: Decimal = Field(Decimal("3.0"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Quote token amount to add to position (0 for base only)"))
    out_of_range_pct: Decimal = Field(Decimal("1.0"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Percentage outside range that triggers closing (e.g. 1.0 for 1%)"))
    out_of_range_secs: int = Field(300, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Seconds price must be out of range before closing (e.g. 300 for 5 min)"))


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
            pool_info = await GatewayHttpClient.get_instance().clmm_pool_info(
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
                    self.logger().info(f"Current price: {self.last_price}")
                except (ValueError, TypeError) as e:
                    self.logger().error(f"Error converting price value: {e}")
            else:
                self.logger().error("No price found in pool info response")

            self.logger().info("Pool information retrieved:")
            self.logger().info(f"Base token address: {self.base_token}")
            self.logger().info(f"Quote token address: {self.quote_token}")

            # Additional pool details that might be useful
            if "binStep" in pool_info:
                self.logger().info(f"Bin step: {pool_info['binStep']}")
            if "feePct" in pool_info:
                self.logger().info(f"Fee percentage: {pool_info['feePct']}%")

        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")

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
            # Calculate position price range
            target_price = float(self.config.target_price)
            width_pct = float(self.config.position_width_pct) / 100.0

            lower_price = target_price * (1 - width_pct)
            upper_price = target_price * (1 + width_pct)

            self.position_lower_price = lower_price
            self.position_upper_price = upper_price

            self.logger().info(f"Opening position with price range: {lower_price} to {upper_price}")

            # Get initial balances
            await self.get_balances()

            # Open position
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

            # Check response
            if "txHash" in response:
                tx_hash = response["txHash"]
                self.logger().info(f"Position opening transaction submitted: {tx_hash}")

                # Poll for transaction result
                await self.poll_transaction(tx_hash)

                # Get position address - check position info after transaction is confirmed
                if "positionAddress" in response:
                    self.position_address = response["positionAddress"]
                    self.position_opened = True
                    self.logger().info(f"Position opened successfully! Position address: {self.position_address}")

                    # Get updated balances
                    await self.get_balances()
                else:
                    self.logger().error("Transaction completed but no position address found in response")
            else:
                self.logger().error(f"Failed to open position: {response}")

        except Exception as e:
            self.logger().error(f"Error opening position: {str(e)}")

        finally:
            # Make sure to update state flags properly
            if not self.position_opened:
                self.position_opening = False
            else:
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
            out_of_range_amount = 0

            lower_bound_with_buffer = self.position_lower_price * (1 - float(self.config.out_of_range_pct) / 100.0)
            upper_bound_with_buffer = self.position_upper_price * (1 + float(self.config.out_of_range_pct) / 100.0)

            if float(self.last_price) < lower_bound_with_buffer:
                out_of_range = True
                out_of_range_amount = (lower_bound_with_buffer - float(self.last_price)) / self.position_lower_price * 100
                self.logger().info(f"Price {self.last_price} is below position lower bound with buffer {lower_bound_with_buffer} by {out_of_range_amount:.2f}%")
            elif float(self.last_price) > upper_bound_with_buffer:
                out_of_range = True
                out_of_range_amount = (float(self.last_price) - upper_bound_with_buffer) / self.position_upper_price * 100
                self.logger().info(f"Price {self.last_price} is above position upper bound with buffer {upper_bound_with_buffer} by {out_of_range_amount:.2f}%")

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

        except Exception as e:
            self.logger().error(f"Error monitoring position: {str(e)}")

    async def close_position(self):
        """Close the concentrated liquidity position"""
        if not self.position_address or self.position_closing:
            return

        self.position_closing = True

        try:
            # Get initial balances
            await self.get_balances()

            # Close position
            self.logger().info(f"Closing position {self.position_address}...")
            response = await GatewayHttpClient.get_instance().clmm_close_position(
                connector=self.config.connector,
                network=self.config.network,
                wallet_address=self.wallet_address,
                position_address=self.position_address
            )

            # Check response
            if "txHash" in response:
                tx_hash = response["txHash"]
                self.logger().info(f"Position closing transaction submitted: {tx_hash}")

                # Poll for transaction result
                await self.poll_transaction(tx_hash)

                self.logger().info("Position closed successfully!")

                # Reset position state
                self.position_opened = False
                self.position_address = None
                self.position_lower_price = None
                self.position_upper_price = None
                self.out_of_range_start_time = None

                # Get updated balances
                await self.get_balances()
            else:
                self.logger().error(f"Failed to close position: {response}")

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")

        finally:
            self.position_closing = False

    async def get_balances(self):
        """Fetch and log balances of base and quote tokens"""
        if not self.base_token or not self.quote_token:
            return

        try:
            balance_data = await GatewayHttpClient.get_instance().get_balances(
                self.config.chain,
                self.config.network,
                self.wallet_address,
                [self.base_token, self.quote_token]
            )

            if balance_data and "balances" in balance_data:
                self.logger().info(f"Current balances: {balance_data['balances']}")

        except Exception as e:
            self.logger().error(f"Failed to get balances: {str(e)}")

    async def poll_transaction(self, tx_hash):
        """Continuously polls for transaction status until completion"""
        if not tx_hash:
            return

        self.logger().info(f"Polling for transaction status: {tx_hash}")

        # Transaction status codes
        # -1 = FAILED
        # 0 = UNCONFIRMED
        # 1 = CONFIRMED

        pending = True
        while pending:
            try:
                # Use the get_transaction_status method to check transaction status
                poll_data = await GatewayHttpClient.get_instance().get_transaction_status(
                    chain=self.config.chain,
                    network=self.config.network,
                    transaction_hash=tx_hash,
                    connector=self.config.connector
                )

                transaction_status = poll_data.get("txStatus")

                if transaction_status == 1:  # CONFIRMED
                    self.logger().info(f"Transaction {tx_hash} confirmed successfully!")
                    pending = False
                elif transaction_status == -1:  # FAILED
                    self.logger().error(f"Transaction {tx_hash} failed!")
                    self.logger().error(f"Details: {poll_data}")
                    pending = False
                elif transaction_status == 0:  # UNCONFIRMED
                    self.logger().info(f"Transaction {tx_hash} still pending...")
                    await asyncio.sleep(2)
                else:
                    self.logger().info(f"Unknown txStatus: {transaction_status}")
                    self.logger().info(f"{poll_data}")
                    pending = False

            except Exception as e:
                self.logger().error(f"Error polling transaction: {str(e)}")
                await asyncio.sleep(5)  # Add delay to avoid rapid retries on error

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

            if self.out_of_range_start_time:
                elapsed = time.time() - self.out_of_range_start_time
                lines.append(f"Price out of range for {elapsed:.0f}/{self.config.out_of_range_secs} seconds")
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
