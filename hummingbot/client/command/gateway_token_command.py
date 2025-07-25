#!/usr/bin/env python
import json
from typing import TYPE_CHECKING, Optional

from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    def wrapper(self, *args, **kwargs):
        if self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayTokenCommand:
    """Commands for managing gateway tokens."""

    @ensure_gateway_online
    def gateway_token(self, symbol_or_address: Optional[str], action: Optional[str]):
        """
        View or update token information.
        Usage:
            gateway token <symbol_or_address>       - View token information
            gateway token <symbol> update           - Update token information
        """
        if not symbol_or_address:
            # Show help when no arguments provided
            self.notify("\nGateway Token Commands:")
            self.notify("  gateway token <symbol_or_address>       - View token information")
            self.notify("  gateway token <symbol> update           - Update token information")
            self.notify("\nExamples:")
            self.notify("  gateway token SOL")
            self.notify("  gateway token 0x1234...5678")
            self.notify("  gateway token USDC update")
            return

        if action == "update":
            safe_ensure_future(
                self._update_token_interactive(symbol_or_address),
                loop=self.ev_loop
            )
        else:
            safe_ensure_future(
                self._view_token(symbol_or_address),
                loop=self.ev_loop
            )

    async def _view_token(
        self,  # type: HummingbotApplication
        symbol_or_address: str
    ):
        """View token information."""
        try:
            # First need to determine chain and network
            # For now, we'll check ethereum and solana
            chains_to_check = ["ethereum", "solana"]
            token_found = False

            for chain in chains_to_check:
                # Get default network for this chain
                default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
                if not default_network:
                    continue

                # Try to get the token
                token_info = await self._get_gateway_instance().get_token(
                    symbol_or_address=symbol_or_address,
                    chain=chain,
                    network=default_network
                )

                if "error" not in token_info:
                    token_found = True
                    self._display_token_info(token_info, chain, default_network)
                    break

            if not token_found:
                self.notify(f"\nToken '{symbol_or_address}' not found on any supported chain.")
                self.notify("You may need to add it using 'gateway token <symbol> update'")

        except Exception as e:
            self.notify(f"Error fetching token information: {str(e)}")

    async def _update_token_interactive(
        self,  # type: HummingbotApplication
        symbol: str
    ):
        """Interactive flow to update or add a token."""
        try:
            with begin_placeholder_mode(self):
                # Ask for chain
                chain = await self.app.prompt(
                    prompt="Enter chain (e.g., ethereum, solana): "
                )

                if self.app.to_stop_config or not chain:
                    self.notify("Token update cancelled")
                    return

                # Get default network for the chain
                default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
                if not default_network:
                    self.notify(f"Could not determine default network for chain '{chain}'")
                    return

                # Check if token exists
                existing_token = await self._get_gateway_instance().get_token(
                    symbol_or_address=symbol,
                    chain=chain,
                    network=default_network
                )

                if "error" not in existing_token:
                    # Token exists, show current info
                    self.notify("\nCurrent token information:")
                    self._display_token_info(existing_token, chain, default_network)

                    # Ask if they want to update
                    response = await self.app.prompt(
                        prompt="\nDo you want to update this token? (Yes/No) >>> "
                    )

                    if response.lower() not in ["y", "yes"]:
                        self.notify("Token update cancelled")
                        return
                else:
                    self.notify(f"\nToken '{symbol}' not found. Let's add it.")

                # Collect token information
                self.notify("\nEnter token information:")

                # Symbol (pre-filled)
                token_symbol = await self.app.prompt(
                    prompt=f"Symbol [{symbol}]: "
                )
                if not token_symbol:
                    token_symbol = symbol

                # Name
                token_name = await self.app.prompt(
                    prompt="Name: "
                )
                if self.app.to_stop_config or not token_name:
                    self.notify("Token update cancelled")
                    return

                # Address
                token_address = await self.app.prompt(
                    prompt="Contract address: "
                )
                if self.app.to_stop_config or not token_address:
                    self.notify("Token update cancelled")
                    return

                # Decimals
                decimals_str = await self.app.prompt(
                    prompt="Decimals [18]: "
                )
                try:
                    decimals = int(decimals_str) if decimals_str else 18
                except ValueError:
                    self.notify("Invalid decimals value. Using default: 18")
                    decimals = 18

                # Create token data
                token_data = {
                    "symbol": token_symbol.upper(),
                    "name": token_name,
                    "address": token_address,
                    "decimals": decimals
                }

                # Display summary
                self.notify("\nToken to add/update:")
                self.notify(json.dumps(token_data, indent=2))

                # Confirm
                confirm = await self.app.prompt(
                    prompt="\nAdd/update this token? (Yes/No) >>> "
                )

                if confirm.lower() not in ["y", "yes"]:
                    self.notify("Token update cancelled")
                    return

                # Add/update token
                self.notify("\nAdding/updating token...")
                result = await self._get_gateway_instance().add_token(
                    chain=chain,
                    network=default_network,
                    token_data=token_data
                )

                if "error" in result:
                    self.notify(f"Error: {result['error']}")
                else:
                    self.notify("✓ Token successfully added/updated!")

                    # Show the updated token info
                    updated_token = await self._get_gateway_instance().get_token(
                        symbol_or_address=token_symbol,
                        chain=chain,
                        network=default_network
                    )
                    if "error" not in updated_token:
                        self.notify("\nUpdated token information:")
                        self._display_token_info(updated_token, chain, default_network)

        except Exception as e:
            self.notify(f"Error updating token: {str(e)}")

    def _display_token_info(
        self,
        token_info: dict,
        chain: str,
        network: str
    ):
        """Display token information in a formatted way."""
        self.notify("\n=== Token Information ===")
        self.notify(f"Chain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Symbol: {token_info.get('symbol', 'N/A')}")
        self.notify(f"Name: {token_info.get('name', 'N/A')}")
        self.notify(f"Address: {token_info.get('address', 'N/A')}")
        self.notify(f"Decimals: {token_info.get('decimals', 'N/A')}")

        # Display any additional fields
        standard_fields = {'symbol', 'name', 'address', 'decimals', 'chain', 'network'}
        extra_fields = {k: v for k, v in token_info.items() if k not in standard_fields}
        if extra_fields:
            self.notify("\nAdditional Information:")
            for key, value in extra_fields.items():
                self.notify(f"  {key}: {value}")
