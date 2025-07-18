#!/usr/bin/env python
"""
Example showing how a trading strategy can integrate gateway operations.
This demonstrates a strategy that ensures tokens are wrapped and approved before trading.
"""
from decimal import Decimal
from typing import Optional

from hummingbot.connector.gateway.core.gateway_connector import GatewayConnector
from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class GatewayStrategyIntegration(ScriptStrategyBase):
    """
    Example strategy that:
    1. Checks if tokens are approved
    2. Wraps native tokens if needed
    3. Executes trades using gateway
    """

    # Strategy configuration
    connector_name = "uniswap/router"
    trading_pair = "WETH-USDC"
    order_amount = Decimal("0.1")  # 0.1 WETH

    # Price thresholds for simple strategy logic
    buy_price_threshold = Decimal("2000")   # Buy if WETH < $2000
    sell_price_threshold = Decimal("2500")  # Sell if WETH > $2500

    def __init__(self):
        super().__init__()
        self.gateway_connector: Optional[GatewayConnector] = None
        self.tokens_approved = False
        self.last_order_id = None

    async def on_tick(self):
        """Main strategy logic"""
        try:
            # Initialize gateway connector if needed
            if not self.gateway_connector:
                await self.setup_gateway_connector()

            # Ensure tokens are approved
            if not self.tokens_approved:
                await self.ensure_tokens_approved()
                self.tokens_approved = True

            # Check if we have a pending order
            if self.last_order_id:
                order = self.gateway_connector.get_order(self.last_order_id)
                if order and not order.is_done:
                    return  # Wait for order to complete

            # Get current price
            price = await self.get_market_price()
            if not price:
                return

            # Simple trading logic
            if price < self.buy_price_threshold:
                self.logger().info(f"Price {price} < {self.buy_price_threshold}, buying {self.order_amount} WETH")
                self.last_order_id = self.gateway_connector.buy(
                    trading_pair=self.trading_pair,
                    amount=self.order_amount,
                    order_type=OrderType.MARKET
                )
            elif price > self.sell_price_threshold:
                self.logger().info(f"Price {price} > {self.sell_price_threshold}, selling {self.order_amount} WETH")
                self.last_order_id = self.gateway_connector.sell(
                    trading_pair=self.trading_pair,
                    amount=self.order_amount,
                    order_type=OrderType.MARKET
                )

        except Exception as e:
            self.logger().error(f"Strategy error: {str(e)}")

    async def setup_gateway_connector(self):
        """Initialize gateway connector"""
        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()

        # Determine chain and network from connector
        if "uniswap" in self.connector_name:
            chain = "ethereum"
            network = "mainnet"
        elif "pancakeswap" in self.connector_name:
            chain = "binance-smart-chain"
            network = "mainnet"
        else:
            chain = "ethereum"  # Default
            network = "mainnet"

        # Get wallet
        gateway_instance = app._gateway_monitor._gateway_instance
        wallet_address = await gateway_instance.get_default_wallet_for_chain(chain)

        if not wallet_address:
            raise ValueError(f"No wallet configured for {chain}")

        # Create connector
        self.gateway_connector = GatewayConnector(
            connector_name=self.connector_name,
            network=network,
            wallet_address=wallet_address,
            trading_required=True
        )

        await self.gateway_connector.start_network()
        self.logger().info(f"Gateway connector initialized: {self.connector_name}")

    async def ensure_tokens_approved(self):
        """Ensure trading tokens are approved"""
        base, quote = self.trading_pair.split("-")
        tokens_to_check = [base, quote]

        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()
        gateway_instance = app._gateway_monitor._gateway_instance

        chain = self.gateway_connector.chain
        network = self.gateway_connector.network
        wallet = self.gateway_connector.wallet_address

        for token in tokens_to_check:
            # Check allowance
            allowance_resp = await gateway_instance.get_allowances(
                chain=chain,
                network=network,
                address=wallet,
                token_symbols=[token],
                spender=self.connector_name
            )

            allowances = allowance_resp.get("approvals", {})
            current_allowance = Decimal(allowances.get(token, "0"))

            if current_allowance == 0:
                self.logger().info(f"Approving {token} for {self.connector_name}...")

                # Approve token
                approve_resp = await gateway_instance.approve_token(
                    chain=chain,
                    network=network,
                    address=wallet,
                    token=token,
                    spender=self.connector_name
                )

                tx_hash = approve_resp.get("approval", {}).get("hash") or approve_resp.get("signature")
                if tx_hash:
                    # Track approval
                    order_id = await self.gateway_connector.execute_transaction(
                        tx_type="approve",
                        chain=chain,
                        network=network,
                        tx_hash=tx_hash,
                        amount=Decimal("0"),
                        token=token,
                        spender=self.connector_name
                    )

                    # Wait for confirmation
                    await self.wait_for_confirmation(order_id)
            else:
                self.logger().info(f"{token} already approved")

    async def get_market_price(self) -> Optional[Decimal]:
        """Get current market price for the trading pair"""
        try:
            # Get price quote for 1 unit
            price = await self.gateway_connector.get_order_price(
                trading_pair=self.trading_pair,
                is_buy=True,
                amount=Decimal("1")
            )
            return price
        except Exception as e:
            self.logger().error(f"Error getting price: {str(e)}")
            return None

    async def wait_for_confirmation(self, order_id: str):
        """Wait for transaction confirmation"""
        import asyncio
        timeout = 30
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            order = self.gateway_connector.get_order(order_id)
            if order and order.is_done:
                if order.is_filled:
                    self.logger().info(f"Transaction {order_id} confirmed")
                else:
                    self.logger().error(f"Transaction {order_id} failed")
                return
            await asyncio.sleep(1)

        self.logger().warning(f"Transaction {order_id} timed out")

    def on_stop(self):
        """Clean up"""
        if self.gateway_connector:
            self.logger().info("Stopping gateway connector...")
        self.logger().info("Strategy stopped")
