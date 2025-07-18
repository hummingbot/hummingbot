#!/usr/bin/env python
"""
Example script showing how to use gateway operations (approve, wrap, swap) from a script.
This demonstrates programmatic access to gateway functionality.
"""
import asyncio
from decimal import Decimal
from typing import Optional

from hummingbot.connector.gateway.core.gateway_connector import GatewayConnector
from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class GatewayOperationsExample(ScriptStrategyBase):
    """
    Example script that demonstrates gateway operations:
    1. Wrapping native tokens (ETH -> WETH)
    2. Approving tokens for trading
    3. Executing swaps
    """

    # Configuration
    chain = "ethereum"
    network = "mainnet"
    connector_name = "uniswap/router"  # Can be any gateway connector

    # Example operation parameters
    wrap_amount = Decimal("0.01")  # Amount of ETH to wrap
    swap_amount = Decimal("100")   # Amount of tokens to swap
    trading_pair = "WETH-USDC"    # Trading pair for swap

    def __init__(self):
        super().__init__()
        self.gateway_connector: Optional[GatewayConnector] = None
        self.operations_complete = False

    async def on_tick(self):
        """Main strategy tick - execute operations once"""
        if self.operations_complete:
            return

        try:
            # Initialize gateway connector if not already done
            if not self.gateway_connector:
                await self.initialize_gateway_connector()

            # Example 1: Wrap native tokens
            await self.example_wrap_tokens()

            # Example 2: Approve tokens
            await self.example_approve_tokens()

            # Example 3: Execute a swap
            await self.example_swap()

            self.operations_complete = True
            self.logger().info("All gateway operations completed successfully!")

        except Exception as e:
            self.logger().error(f"Error in gateway operations: {str(e)}")

    async def initialize_gateway_connector(self):
        """Initialize the gateway connector"""
        self.logger().info(f"Initializing gateway connector: {self.connector_name}")

        # Get wallet address from gateway
        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()
        gateway_instance = app._gateway_monitor._gateway_instance

        wallet_address = await gateway_instance.get_default_wallet_for_chain(self.chain)
        if not wallet_address:
            raise ValueError(f"No wallet found for {self.chain}")

        # Create gateway connector
        self.gateway_connector = GatewayConnector(
            connector_name=self.connector_name,
            network=self.network,
            wallet_address=wallet_address,
            trading_required=True
        )

        # Wait for initialization
        await self.gateway_connector.start_network()
        await asyncio.sleep(2)  # Give it time to initialize

        self.logger().info(f"Gateway connector initialized with wallet: {wallet_address}")

    async def example_wrap_tokens(self):
        """Example: Wrap native tokens to wrapped tokens"""
        self.logger().info(f"Wrapping {self.wrap_amount} ETH to WETH...")

        # Direct approach using gateway API
        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()
        gateway_instance = app._gateway_monitor._gateway_instance

        wallet_address = await gateway_instance.get_default_wallet_for_chain(self.chain)

        # Call wrap endpoint
        wrap_response = await gateway_instance.api_request(
            method="post",
            path=f"chains/{self.chain}/wrap",
            params={
                "network": self.network,
                "address": wallet_address,
                "amount": str(self.wrap_amount)
            }
        )

        tx_hash = wrap_response.get("signature")
        if tx_hash:
            self.logger().info(f"Wrap transaction submitted: {tx_hash}")

            # Track transaction using gateway connector
            order_id = await self.gateway_connector.execute_transaction(
                tx_type="wrap",
                chain=self.chain,
                network=self.network,
                tx_hash=tx_hash,
                amount=self.wrap_amount,
                token="ETH",
                native_token="ETH",
                wrapped_token="WETH"
            )

            # Wait for confirmation
            await self.wait_for_transaction_confirmation(order_id)
        else:
            self.logger().error("Failed to get transaction hash from wrap response")

    async def example_approve_tokens(self):
        """Example: Approve tokens for trading"""
        tokens_to_approve = ["WETH", "USDC"]

        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()
        gateway_instance = app._gateway_monitor._gateway_instance

        wallet_address = await gateway_instance.get_default_wallet_for_chain(self.chain)

        for token in tokens_to_approve:
            self.logger().info(f"Approving {token} for {self.connector_name}...")

            # Check current allowance
            allowance_resp = await gateway_instance.get_allowances(
                chain=self.chain,
                network=self.network,
                address=wallet_address,
                token_symbols=[token],
                spender=self.connector_name
            )

            allowances = allowance_resp.get("approvals", {})
            current_allowance = Decimal(allowances.get(token, "0"))

            if current_allowance > 0:
                self.logger().info(f"{token} already approved with allowance: {current_allowance}")
                continue

            # Approve token
            approve_resp = await gateway_instance.approve_token(
                chain=self.chain,
                network=self.network,
                address=wallet_address,
                token=token,
                spender=self.connector_name
            )

            tx_hash = approve_resp.get("approval", {}).get("hash") or approve_resp.get("signature")
            if tx_hash:
                self.logger().info(f"Approve transaction submitted for {token}: {tx_hash}")

                # Track transaction
                order_id = await self.gateway_connector.execute_transaction(
                    tx_type="approve",
                    chain=self.chain,
                    network=self.network,
                    tx_hash=tx_hash,
                    amount=Decimal("0"),
                    token=token,
                    spender=self.connector_name
                )

                await self.wait_for_transaction_confirmation(order_id)

    async def example_swap(self):
        """Example: Execute a swap using gateway connector"""
        self.logger().info(f"Executing swap: BUY {self.swap_amount} {self.trading_pair}")

        # Use the gateway connector's buy method
        order_id = self.gateway_connector.buy(
            trading_pair=self.trading_pair,
            amount=self.swap_amount,
            order_type=OrderType.MARKET,
            price=None  # Market order
        )

        self.logger().info(f"Swap order created: {order_id}")

        # Wait for order completion
        await self.wait_for_order_completion(order_id)

    async def wait_for_transaction_confirmation(self, order_id: str, timeout: float = 30.0):
        """Wait for a transaction to be confirmed"""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            order = self.gateway_connector.get_order(order_id)
            if order:
                if order.is_filled:
                    self.logger().info(f"Transaction {order_id} confirmed!")
                    return True
                elif order.is_failure:
                    self.logger().error(f"Transaction {order_id} failed!")
                    return False

            await asyncio.sleep(1)

        self.logger().warning(f"Transaction {order_id} timed out after {timeout}s")
        return False

    async def wait_for_order_completion(self, order_id: str, timeout: float = 30.0):
        """Wait for an order to complete"""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            order = self.gateway_connector.get_order(order_id)
            if order:
                if order.is_filled:
                    self.logger().info(f"Order {order_id} filled successfully!")
                    # Log trade details
                    for trade in order.executed_amount_base:
                        self.logger().info(f"Trade executed at price: {trade.price}")
                    return True
                elif order.is_failure:
                    self.logger().error(f"Order {order_id} failed!")
                    return False

            await asyncio.sleep(1)

        self.logger().warning(f"Order {order_id} timed out after {timeout}s")
        return False

    def on_stop(self):
        """Clean up when script stops"""
        self.logger().info("Gateway operations example script stopped")
