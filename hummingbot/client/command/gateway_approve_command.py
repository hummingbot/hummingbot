#!/usr/bin/env python
from typing import TYPE_CHECKING, Optional

from hummingbot.connector.gateway.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayApproveCommand:
    """Handles gateway token approval commands"""

    def gateway_approve(self, connector: Optional[str], tokens: Optional[str]):
        if connector is not None and tokens is not None:
            safe_ensure_future(self._update_gateway_approve_tokens(
                connector, tokens), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify the connector and a token to approve.\n")

    async def _update_gateway_approve_tokens(
            self,           # type: HummingbotApplication
            connector: str,
            tokens: str,
    ):
        """
        Allow the user to approve tokens for spending using the connector.
        """
        try:
            # Parse connector format (e.g., "uniswap/amm")
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            # Get chain and network from connector
            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(error)
                return

            # Get default wallet for the chain
            wallet_address = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not wallet_address:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return

            # Create a temporary GatewayBase instance for approval
            gateway_connector = GatewayBase(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[],
                trading_required=False
            )

            # Start the connector network
            await gateway_connector.start_network()

            try:
                # Parse token list
                token_list = [token.strip() for token in tokens.split(",")]

                self.notify(f"\nApproving tokens for {connector}...")

                # Approve each token
                for token in token_list:
                    self.notify(f"Submitting approval for {token}...")

                    # Call the approve method on the connector
                    order_id = await gateway_connector.approve_token(token_symbol=token)

                    self.notify(f"Approval submitted for {token}. Order ID: {order_id}")
                    self.notify("Monitoring transaction status...")

                    # Use the common transaction monitoring helper
                    result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                        connector=gateway_connector,
                        order_id=order_id,
                        notify_fn=self.notify,
                        timeout=60.0,
                        check_interval=1.0,
                        pending_msg_delay=3.0
                    )

                    # Add token-specific success/failure message
                    if result["completed"] and result["success"]:
                        self.notify(f"Token {token} is approved for spending for '{connector}'")
                    elif result["completed"] and not result["success"]:
                        self.notify(f"Token {token} approval failed. Please check your transaction.")

            finally:
                # Stop the connector
                await gateway_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error approving tokens: {e}", exc_info=True)
            self.notify(f"Error approving tokens: {str(e)}")
            return

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """Get the gateway HTTP client instance"""
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        return gateway_instance
