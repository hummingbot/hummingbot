#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    """Decorator to ensure gateway is online before executing commands."""

    def wrapper(self, *args, **kwargs):
        from hummingbot.connector.gateway.core import GatewayStatus
        if hasattr(self, '_gateway_monitor') and self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayWrapCommand:
    """Commands for wrapping and unwrapping native tokens."""

    @ensure_gateway_online
    def gateway_wrap(self, amount: Optional[str] = None):
        """
        Command to wrap native tokens to wrapped tokens
        Usage: gateway wrap [amount]
        """
        if amount:
            safe_ensure_future(self._wrap_tokens("ethereum", amount), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify the amount to wrap.\n"
                "Usage: gateway wrap <amount>\n"
                "Example: gateway wrap 0.1\n"
            )

    @ensure_gateway_online
    def gateway_unwrap(self, amount: Optional[str] = None):
        """
        Command to unwrap wrapped tokens to native tokens
        Usage: gateway unwrap [amount]
        """
        if amount:
            safe_ensure_future(self._unwrap_tokens("ethereum", amount), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify the amount to unwrap.\n"
                "Usage: gateway unwrap <amount>\n"
                "Example: gateway unwrap 0.1\n"
            )

    async def _wrap_tokens(self, chain: str, amount: str):
        """
        Wrap native tokens to wrapped tokens (ETH→WETH, BNB→WBNB, AVAX→WAVAX, etc.)
        """
        try:
            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify("Error: Invalid amount format")
                return

            # Get default network
            network = await self._get_default_network_for_chain(chain)
            if not network:
                self.notify(f"Error: Could not determine default network for {chain}")
                return

            # Get default wallet for this chain
            wallet_address = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not wallet_address:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return

            # Get native token info from parent class method
            native_token = await self._get_native_currency_symbol(chain, network)
            if not native_token:
                self.notify(f"Could not determine native token for {chain} {network}")
                return

            # Wrapped token is always W + native token
            wrapped_token = f"W{native_token.upper()}"

            self.notify(f"\nWrapping {amount} {native_token} to {wrapped_token} on {network}...")
            self.notify(f"Wallet: {wallet_address}")

            # Call the wrap endpoint
            try:
                wrap_resp = await self._get_gateway_instance().api_request(
                    method="post",
                    path=f"chains/{chain}/wrap",
                    params={
                        "network": network,
                        "address": wallet_address,
                        "amount": amount
                    }
                )

                if not wrap_resp:
                    self.notify("Error: No response from gateway")
                    return

                # Extract transaction details
                tx_hash = wrap_resp.get("signature")
                fee = wrap_resp.get("fee", "0")
                wrapped_address = wrap_resp.get("wrappedAddress")

                if not tx_hash:
                    self.notify("Error: No transaction hash received")
                    return

                self.notify(f"\nTransaction submitted. Hash: {tx_hash}")
                self.notify(f"Wrapped token contract: {wrapped_address}")
                self.notify(f"Estimated fee: {fee} {native_token}")

                # Get shared utility connector
                connector = self._get_utility_connector(chain, network, wallet_address)

                # Track the transaction
                order_id = await connector.execute_transaction(
                    tx_type="wrap",
                    chain=chain,
                    network=network,
                    tx_hash=tx_hash,
                    amount=amount_decimal,
                    token=native_token,
                    native_token=native_token,
                    wrapped_token=wrapped_token
                )

                # Wait for transaction to complete
                await self._wait_for_transaction(connector, order_id, tx_hash, "wrap",
                                                 amount, native_token, wrapped_token)

            except Exception as e:
                self.notify(f"\nError executing wrap: {str(e)}")

        except Exception as e:
            self.notify(f"Error in wrap tokens: {str(e)}")

    async def _unwrap_tokens(self, chain: str, amount: str):
        """
        Unwrap wrapped tokens to native tokens (WETH→ETH, WBNB→BNB, WAVAX→AVAX, etc.)
        """
        try:
            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify("Error: Invalid amount format")
                return

            # Get default network
            network = await self._get_default_network_for_chain(chain)
            if not network:
                self.notify(f"Error: Could not determine default network for {chain}")
                return

            # Get default wallet for this chain
            wallet_address = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not wallet_address:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return

            # Get native token info from parent class method
            native_token = await self._get_native_currency_symbol(chain, network)
            if not native_token:
                self.notify(f"Could not determine native token for {chain} {network}")
                return

            # Wrapped token is always W + native token
            wrapped_token = f"W{native_token.upper()}"

            self.notify(f"\nUnwrapping {amount} {wrapped_token} to {native_token} on {network}...")
            self.notify(f"Wallet: {wallet_address}")

            # Call the unwrap endpoint
            try:
                unwrap_resp = await self._get_gateway_instance().api_request(
                    method="post",
                    path=f"chains/{chain}/unwrap",
                    params={
                        "network": network,
                        "address": wallet_address,
                        "amount": amount
                    }
                )

                if not unwrap_resp:
                    self.notify("Error: No response from gateway")
                    return

                # Extract transaction details
                tx_hash = unwrap_resp.get("signature")
                fee = unwrap_resp.get("fee", "0")

                if not tx_hash:
                    self.notify("Error: No transaction hash received")
                    return

                self.notify(f"\nTransaction submitted. Hash: {tx_hash}")
                self.notify(f"Estimated fee: {fee} {native_token}")

                # Get shared utility connector
                connector = self._get_utility_connector(chain, network, wallet_address)

                # Track the transaction
                order_id = await connector.execute_transaction(
                    tx_type="unwrap",
                    chain=chain,
                    network=network,
                    tx_hash=tx_hash,
                    amount=amount_decimal,
                    token=wrapped_token,
                    native_token=native_token,
                    wrapped_token=wrapped_token
                )

                # Wait for transaction to complete
                await self._wait_for_transaction(connector, order_id, tx_hash, "unwrap",
                                                 amount, wrapped_token, native_token)

            except Exception as e:
                self.notify(f"\nError executing unwrap: {str(e)}")

        except Exception as e:
            self.notify(f"Error in unwrap tokens: {str(e)}")
