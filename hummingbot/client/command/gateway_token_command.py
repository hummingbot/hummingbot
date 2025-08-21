#!/usr/bin/env python
import json
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

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
        """View token information across all chains."""
        try:
            # Get all available chains from the Chain enum
            from hummingbot.connector.gateway.common_types import Chain
            chains_to_check = [chain.chain for chain in Chain]
            found_tokens: List[Dict] = []

            self.notify(f"\nSearching for token '{symbol_or_address}' across all chains' default networks...")

            for chain in chains_to_check:
                # Get default network for this chain
                default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
                if not default_network:
                    continue

                # Try to get the token
                response = await self._get_gateway_instance().get_token(
                    symbol_or_address=symbol_or_address,
                    chain=chain,
                    network=default_network,
                    fail_silently=True  # Don't raise error if token not found
                )

                if "error" not in response:
                    # Extract token data - it might be nested under 'token' key
                    token_data = response.get("token", response)

                    # Add chain and network info to token data
                    token_info = {
                        "chain": chain,
                        "network": default_network,
                        "symbol": token_data.get("symbol", "N/A"),
                        "name": token_data.get("name", "N/A"),
                        "address": token_data.get("address", "N/A"),
                        "decimals": token_data.get("decimals", "N/A")
                    }
                    found_tokens.append(token_info)

            if found_tokens:
                self._display_tokens_table(found_tokens)
            else:
                self.notify(f"\nToken '{symbol_or_address}' not found on any chain's default network.")
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
                    network=default_network,
                    fail_silently=True  # Don't raise error if token not found
                )

                if "error" not in existing_token:
                    # Token exists, show current info
                    self.notify("\nCurrent token information:")
                    # Extract token data - it might be nested under 'token' key
                    token_data = existing_token.get("token", existing_token)
                    self._display_single_token(token_data, chain, default_network)

                    # Ask if they want to update
                    response = await self.app.prompt(
                        prompt="Do you want to update this token? (Yes/No) >>> "
                    )

                    if response.lower() not in ["y", "yes"]:
                        self.notify("Token update cancelled")
                        return
                else:
                    self.notify(f"\nToken '{symbol}' not found. Let's add it to {chain} ({default_network}).")

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
                    prompt="Add/update this token? (Yes/No) >>> "
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

                    # Restart gateway for changes to take effect
                    self.notify("\nRestarting Gateway for changes to take effect...")
                    try:
                        await self._get_gateway_instance().post_restart()
                        self.notify("✓ Gateway restarted successfully")
                        self.notify(f"\nYou can now use 'gateway token {token_symbol}' to view the token information.")
                    except Exception as e:
                        self.notify(f"⚠️  Failed to restart Gateway: {str(e)}")
                        self.notify("You may need to restart Gateway manually for changes to take effect")

        except Exception as e:
            self.notify(f"Error updating token: {str(e)}")

    def _display_tokens_table(self, tokens: List[Dict]):
        """Display tokens in a table format."""
        self.notify("\nFound tokens:")

        # Create DataFrame for display
        df = pd.DataFrame(tokens)

        # Reorder columns for better display
        columns_order = ["chain", "network", "symbol", "name", "address", "decimals"]
        df = df[columns_order]

        # Format the dataframe for display
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self.notify("\n".join(lines))

    def _display_single_token(
        self,
        token_info: dict,
        chain: str,
        network: str
    ):
        """Display a single token's information."""
        self.notify(f"\nChain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Symbol: {token_info.get('symbol', 'N/A')}")
        self.notify(f"Name: {token_info.get('name', 'N/A')}")
        self.notify(f"Address: {token_info.get('address', 'N/A')}")
        self.notify(f"Decimals: {token_info.get('decimals', 'N/A')}")
