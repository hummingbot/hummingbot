#!/usr/bin/env python
import asyncio
from typing import TYPE_CHECKING, Optional

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayApproveCommand:
    """Handles gateway token approval commands"""

    def gateway_approve(self, connector: Optional[str], token: Optional[str]):
        if connector is not None and token is not None:
            safe_ensure_future(self._update_gateway_approve_token(
                connector, token), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify an Ethereum connector and a token to approve.\n")

    async def _update_gateway_approve_token(
            self,           # type: HummingbotApplication
            connector: str,
            token: str,
    ):
        """
        Allow the user to approve a token for spending using the connector.
        """
        try:
            # Parse connector format (e.g., "uniswap/amm")
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            # Get chain and network from connector
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )
            if error:
                self.notify(error)
                return

            # Get default wallet for the chain
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
            )
            if error:
                self.notify(error)
                return

            wallet_display_address = GatewayCommandUtils.format_address_display(wallet_address)

            # Clean up token symbol/address
            token = token.strip()

            # Create a temporary GatewayBase instance for gas estimation and approval
            gateway_connector = GatewayBase(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[],
                trading_required=True  # Set to True to enable gas estimation
            )

            # Start the connector network
            await gateway_connector.start_network()

            # Get current allowance
            self.notify(f"\nFetching {connector} allowance for {token}...")

            # Display approval transaction header
            self.notify("\n=== Approve Transaction ===")
            self.notify(f"Connector: {connector}")
            self.notify(f"Network: {chain} {network}")
            self.notify(f"Wallet: {wallet_display_address}")

            try:
                allowance_resp = await self._get_gateway_instance().get_allowances(
                    chain, network, wallet_address, [token], connector, fail_silently=True
                )
                current_allowances = allowance_resp.get("approvals", {})
                current_allowance = current_allowances.get(token, "0")
            except Exception as e:
                self.logger().warning(f"Failed to get current allowance: {e}")
                current_allowance = "0"

            # Get token info and display approval details
            token_info = gateway_connector.get_token_info(token)
            token_data_for_display = {token: token_info} if token_info else {}
            formatted_rows = GatewayCommandUtils.format_allowance_display(
                {token: current_allowance},
                token_data=token_data_for_display
            )

            formatted_row = formatted_rows[0] if formatted_rows else {"Symbol": token.upper(), "Address": "Unknown", "Allowance": "0"}

            self.notify("\nToken to approve:")
            self.notify(f"  Symbol: {formatted_row['Symbol']}")
            self.notify(f"  Address: {formatted_row['Address']}")
            self.notify(f"  Current Allowance: {formatted_row['Allowance']}")

            # Log the connector state for debugging
            self.logger().info(f"Gateway connector initialized: chain={chain}, network={network}, connector={connector}")
            self.logger().info(f"Network transaction fee before check: {gateway_connector.network_transaction_fee}")

            # Wait a moment for gas estimation to complete if needed
            await asyncio.sleep(0.5)

            # Collect warnings throughout the command
            warnings = []

            # Get fee estimation from gateway
            self.notify(f"\nEstimating transaction fees for {chain} {network}...")
            fee_info = await self._get_gateway_instance().estimate_transaction_fee(
                chain,
                network,
                transaction_type="approve"
            )

            native_token = fee_info.get("native_token", chain.upper())
            gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else None

            # Get all tokens to check (include native token for gas)
            tokens_to_check = [token]
            if native_token and native_token.upper() != token.upper():
                tokens_to_check.append(native_token)

            # Get current balances
            current_balances = await self._get_gateway_instance().get_wallet_balances(
                chain=chain,
                network=network,
                wallet_address=wallet_address,
                tokens_to_check=tokens_to_check,
                native_token=native_token
            )

            # For approve, there's no token balance change, only gas fee
            balance_changes = {}

            # Display balance impact table (only gas fee impact)
            GatewayCommandUtils.display_balance_impact_table(
                app=self,
                wallet_address=wallet_address,
                current_balances=current_balances,
                balance_changes=balance_changes,
                native_token=native_token,
                gas_fee=gas_fee_estimate or 0,
                warnings=warnings,
                title="Balance Impact After Approval"
            )

            # Display transaction fee details
            GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

            # Display any warnings
            GatewayCommandUtils.display_warnings(self, warnings)

            # Ask for confirmation
            await GatewayCommandUtils.enter_interactive_mode(self)
            try:
                if not await GatewayCommandUtils.prompt_for_confirmation(
                    self, "Do you want to proceed with the approval?"
                ):
                    self.notify("Approval cancelled")
                    return

                self.notify(f"\nApproving {token} for {connector}...")

                # Submit approval
                self.notify(f"\nSubmitting approval for {token}...")

                # Call the approve method on the connector
                order_id = await gateway_connector.approve_token(token_symbol=token)

                self.notify(f"Approval submitted for {token}. Order ID: {order_id}")
                self.notify("Monitoring transaction status...")

                # Use the common transaction monitoring helper
                result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                    app=self,
                    connector=gateway_connector,
                    order_id=order_id,
                    timeout=60.0,
                    check_interval=1.0,
                    pending_msg_delay=3.0
                )

                # Add token-specific success/failure message
                if result["completed"] and result["success"]:
                    self.notify(f"✓ Token {token} is approved for spending on {connector}")
                elif result["completed"] and not result["success"]:
                    self.notify(f"✗ Token {token} approval failed. Please check your transaction.")

            finally:
                await GatewayCommandUtils.exit_interactive_mode(self)
                # Stop the connector
                await gateway_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error approving token: {e}", exc_info=True)
            self.notify(f"Error approving token: {str(e)}")
            return

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """Get the gateway HTTP client instance"""
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        return gateway_instance
