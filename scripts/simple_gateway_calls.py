from decimal import Decimal

from hummingbot.connector.gateway.core.gateway_connector import GatewayConnector
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleGatewayCalls(ScriptStrategyBase):
    """
    This example shows how to execute gateway utility operations (wrap/unwrap/approve) directly.
    It demonstrates using the GatewayConnector for non-trading operations.
    """
    operations_executed = 0
    operations_to_execute = 1  # Number of operations to execute

    # Configuration - only need to specify chain and amount
    chain = "ethereum"  # Chain to use (ethereum, bsc, avalanche, etc.)
    wrap_amount = Decimal("0.01")  # Amount to wrap/unwrap

    # Markets - required by script base but not used for utility operations
    markets = {}

    # Instance variables initialized at class level
    _connector = None
    _operation_in_progress = False

    def on_tick(self):
        if self.operations_executed < self.operations_to_execute and not self._operation_in_progress:
            self._operation_in_progress = True

            # Execute the async wrap operation
            safe_ensure_future(self._execute_wrap_operation())

    async def _execute_wrap_operation(self):
        """Execute a wrap operation using the gateway API"""
        try:
            # Create a utility connector instance if not exists
            if self._connector is None:
                # Create a temporary connector to get chain info
                # Use a real connector that exists in the gateway
                self._connector = GatewayConnector(
                    connector_name="uniswap/router",
                    network="mainnet",  # Temporary network, will be updated
                    trading_required=False
                )
                await self._connector._initialize()

            # Get the gateway client from connector
            client = self._connector.client

            # Get the default network for this chain
            network = await client.get_default_network_for_chain(self.chain)
            if not network:
                self.logger().error(f"No default network found for {self.chain}")
                self._operation_in_progress = False
                return

            self.logger().info(f"Using default network: {network}")

            # Get default wallet
            wallet_address = await client.get_default_wallet_for_chain(self.chain)
            if not wallet_address:
                self.logger().error(f"No default wallet found for {self.chain}")
                self._operation_in_progress = False
                return

            # Get native token symbol using the gateway client method
            native_token = await client.get_native_currency_symbol(self.chain, network)
            if not native_token:
                self.logger().error(f"Could not determine native token for {self.chain} {network}")
                self._operation_in_progress = False
                return

            wrapped_token = f"W{native_token}"

            # Call the wrap endpoint directly
            self.logger().info(f"Wrapping {self.wrap_amount} {native_token} to {wrapped_token}...")
            self.logger().info(f"Using wallet: {wallet_address}")

            # Make the wrap API call
            wrap_response = await client.api_request(
                method="post",
                path=f"chains/{self.chain}/wrap",
                params={
                    "network": network,
                    "address": wallet_address,
                    "amount": str(self.wrap_amount)
                }
            )

            # Extract transaction details
            tx_hash = wrap_response.get("signature")
            fee = wrap_response.get("fee", "0")
            wrapped_address = wrap_response.get("wrappedAddress")

            if not tx_hash:
                self.logger().error("No transaction hash received")
                self._operation_in_progress = False
                return

            self.logger().info(f"Transaction submitted: {tx_hash}")
            self.logger().info(f"Wrapped token contract: {wrapped_address}")
            self.logger().info(f"Estimated fee: {fee} {native_token}")

            # Track the transaction using the connector's transaction monitoring
            order_id = await self._connector.execute_transaction(
                tx_type="wrap",
                chain=self.chain,
                network=network,
                tx_hash=tx_hash,
                amount=self.wrap_amount,
                token=native_token,
                native_token=native_token,
                wrapped_token=wrapped_token
            )

            self.logger().info(f"Tracking transaction with order ID: {order_id}")

            # The transaction will be monitored automatically by the connector
            # You can check the status using: self._connector.get_order(order_id)

            self.operations_executed += 1

            if self.operations_executed >= self.operations_to_execute:
                self.logger().info("All operations completed!")
                self.stop()

        except Exception as e:
            self.logger().error(f"Error executing wrap operation: {str(e)}")
        finally:
            self._operation_in_progress = False

    def did_fill_order(self, event):
        """Called when a transaction is confirmed"""
        # Check if this is a wrap transaction by looking for native-wrapped token pairs
        if "-W" in event.trading_pair:
            self.logger().info(f"Wrap operation completed: {event.client_order_id}")

    def on_stop(self):
        """Clean up"""
        self.logger().info("Script stopped")
