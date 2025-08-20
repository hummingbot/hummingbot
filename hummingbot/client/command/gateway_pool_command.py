#!/usr/bin/env python
import json
from typing import TYPE_CHECKING, List, Optional, TypedDict

from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class PoolListInfo(TypedDict):
    """Pool information structure returned by gateway get_pool endpoint."""
    type: str  # "amm" or "clmm"
    network: str
    baseSymbol: str
    quoteSymbol: str
    address: str


def ensure_gateway_online(func):
    def wrapper(self, *args, **kwargs):
        if self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayPoolCommand:
    """Commands for managing gateway pools."""

    @ensure_gateway_online
    def gateway_pool(self, connector: Optional[str], trading_pair: Optional[str], action: Optional[str], args: List[str] = None):
        """
        View or update pool information.
        Usage:
            gateway pool <connector> <trading_pair>                - View pool information
            gateway pool <connector> <trading_pair> update         - Add/update pool information (interactive)
            gateway pool <connector> <trading_pair> update <address> - Add/update pool information (direct)
        """
        if args is None:
            args = []

        if not connector or not trading_pair:
            # Show help when insufficient arguments provided
            self.notify("\nGateway Pool Commands:")
            self.notify("  gateway pool <connector> <trading_pair>                - View pool information")
            self.notify("  gateway pool <connector> <trading_pair> update         - Add/update pool information (interactive)")
            self.notify("  gateway pool <connector> <trading_pair> update <address> - Add/update pool information (direct)")
            self.notify("\nExamples:")
            self.notify("  gateway pool uniswap/amm ETH-USDC")
            self.notify("  gateway pool raydium/clmm SOL-USDC update")
            self.notify("  gateway pool uniswap/amm ETH-USDC update 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640")
            return

        if action == "update":
            if args and len(args) > 0:
                # Non-interactive mode: gateway pool <connector> <trading_pair> update <address>
                pool_address = args[0]
                safe_ensure_future(
                    self._update_pool_direct(connector, trading_pair, pool_address),
                    loop=self.ev_loop
                )
            else:
                # Interactive mode: gateway pool <connector> <trading_pair> update
                safe_ensure_future(
                    self._update_pool_interactive(connector, trading_pair),
                    loop=self.ev_loop
                )
        else:
            safe_ensure_future(
                self._view_pool(connector, trading_pair),
                loop=self.ev_loop
            )

    async def _view_pool(
        self,  # type: HummingbotApplication
        connector: str,
        trading_pair: str
    ):
        """View pool information."""
        try:
            # Parse connector format
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            connector_parts = connector.split("/")
            connector_name = connector_parts[0]
            trading_type = connector_parts[1]

            # Parse trading pair
            if "-" not in trading_pair:
                self.notify(f"Error: Invalid trading pair format '{trading_pair}'. Use format like 'ETH-USDC'")
                return

            # Capitalize the trading pair
            trading_pair = trading_pair.upper()

            # Get chain and network from connector
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )

            if error:
                self.notify(error)
                return

            self.notify(f"\nFetching pool information for {trading_pair} on {connector}...")

            # Get pool information
            response = await self._get_gateway_instance().get_pool(
                trading_pair=trading_pair,
                connector=connector_name,
                network=network,
                type=trading_type
            )

            if "error" in response:
                self.notify(f"\nError: {response['error']}")
                self.notify(f"Pool {trading_pair} not found on {connector}")
                self.notify(f"You may need to add it using 'gateway pool {connector} {trading_pair} update'")
            else:
                # Display pool information
                try:
                    GatewayPoolCommand._display_pool_info(self, response, connector, trading_pair)
                except Exception as display_error:
                    # Log the response structure for debugging
                    self.notify(f"\nReceived pool data: {response}")
                    self.notify(f"Error displaying pool information: {str(display_error)}")

        except Exception as e:
            self.notify(f"Error fetching pool information: {str(e)}")

    async def _update_pool_direct(
        self,  # type: HummingbotApplication
        connector: str,
        trading_pair: str,
        pool_address: str
    ):
        """Direct mode to add a pool with just the address."""
        try:
            # Parse connector format
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            connector_parts = connector.split("/")
            connector_name = connector_parts[0]
            trading_type = connector_parts[1]

            # Parse trading pair
            if "-" not in trading_pair:
                self.notify(f"Error: Invalid trading pair format '{trading_pair}'. Use format like 'ETH-USDC'")
                return

            # Capitalize the trading pair
            trading_pair = trading_pair.upper()

            tokens = trading_pair.split("-")
            base_token = tokens[0]
            quote_token = tokens[1]

            # Get chain and network from connector
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )

            if error:
                self.notify(error)
                return

            self.notify(f"\nAdding pool for {trading_pair} on {connector}")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")
            self.notify(f"Pool Address: {pool_address}")

            # Create pool data
            pool_data = {
                "address": pool_address,
                "baseSymbol": base_token,
                "quoteSymbol": quote_token,
                "type": trading_type
            }

            # Add pool
            self.notify("\nAdding pool...")
            result = await self._get_gateway_instance().add_pool(
                connector=connector_name,
                network=network,
                pool_data=pool_data
            )

            if "error" in result:
                self.notify(f"Error: {result['error']}")
            else:
                self.notify("✓ Pool successfully added!")

                # Restart gateway for changes to take effect
                self.notify("\nRestarting Gateway for changes to take effect...")
                try:
                    await self._get_gateway_instance().post_restart()
                    self.notify("✓ Gateway restarted successfully")
                    self.notify(f"\nPool has been added. You can view it with: gateway pool {connector} {trading_pair}")
                except Exception as e:
                    self.notify(f"⚠️  Failed to restart Gateway: {str(e)}")
                    self.notify("You may need to restart Gateway manually for changes to take effect")

        except Exception as e:
            self.notify(f"Error adding pool: {str(e)}")

    async def _update_pool_interactive(
        self,  # type: HummingbotApplication
        connector: str,
        trading_pair: str
    ):
        """Interactive flow to add a pool."""
        try:
            # Parse connector format
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            connector_parts = connector.split("/")
            connector_name = connector_parts[0]
            trading_type = connector_parts[1]

            # Parse trading pair
            if "-" not in trading_pair:
                self.notify(f"Error: Invalid trading pair format '{trading_pair}'. Use format like 'ETH-USDC'")
                return

            # Capitalize the trading pair
            trading_pair = trading_pair.upper()

            tokens = trading_pair.split("-")
            base_token = tokens[0]
            quote_token = tokens[1]

            # Get chain and network from connector
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )

            if error:
                self.notify(error)
                return

            self.notify(f"\n=== Add Pool for {trading_pair} on {connector} ===")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")

            with begin_placeholder_mode(self):
                # Check if pool already exists
                try:
                    existing_pool = await self._get_gateway_instance().get_pool(
                        trading_pair=trading_pair,
                        connector=connector_name,
                        network=network,
                        type=trading_type
                    )
                except Exception:
                    # Pool doesn't exist, which is fine for adding a new pool
                    existing_pool = {"error": "Pool not found"}

                if "error" not in existing_pool:
                    # Pool exists, show current info
                    self.notify("\nPool already exists:")
                    GatewayPoolCommand._display_pool_info(self, existing_pool, connector, trading_pair)

                    # Ask if they want to update
                    response = await self.app.prompt(
                        prompt="Do you want to update this pool? (Yes/No) >>> "
                    )

                    if response.lower() not in ["y", "yes"]:
                        self.notify("Pool update cancelled")
                        return
                else:
                    self.notify(f"\nPool '{trading_pair}' not found. Let's add it to {chain} ({network}).")

                # Collect pool information
                self.notify("\nEnter pool information:")

                # Pool address
                pool_address = await self.app.prompt(
                    prompt="Pool contract address: "
                )
                if self.app.to_stop_config or not pool_address:
                    self.notify("Pool addition cancelled")
                    return

                # Create pool data
                pool_data = {
                    "address": pool_address,
                    "baseSymbol": base_token,
                    "quoteSymbol": quote_token,
                    "type": trading_type
                }

                # Display summary
                self.notify("\nPool to add:")
                self.notify(json.dumps(pool_data, indent=2))

                # Confirm
                confirm = await self.app.prompt(
                    prompt="Add this pool? (Yes/No) >>> "
                )

                if confirm.lower() not in ["y", "yes"]:
                    self.notify("Pool addition cancelled")
                    return

                # Add pool
                self.notify("\nAdding pool...")
                result = await self._get_gateway_instance().add_pool(
                    connector=connector_name,
                    network=network,
                    pool_data=pool_data
                )

                if "error" in result:
                    self.notify(f"Error: {result['error']}")
                else:
                    self.notify("✓ Pool successfully added!")

                    # Restart gateway for changes to take effect
                    self.notify("\nRestarting Gateway for changes to take effect...")
                    try:
                        await self._get_gateway_instance().post_restart()
                        self.notify("✓ Gateway restarted successfully")
                        self.notify(f"\nPool has been added. You can view it with: gateway pool {connector} {trading_pair}")
                    except Exception as e:
                        self.notify(f"⚠️  Failed to restart Gateway: {str(e)}")
                        self.notify("You may need to restart Gateway manually for changes to take effect")

        except Exception as e:
            self.notify(f"Error updating pool: {str(e)}")

    def _display_pool_info(
        self,
        pool_info: dict,
        connector: str,
        trading_pair: str
    ):
        """Display pool information in a formatted way."""
        self.notify("\n=== Pool Information ===")
        self.notify(f"Connector: {connector}")
        self.notify(f"Trading Pair: {trading_pair}")
        self.notify(f"Pool Type: {pool_info.get('type', 'N/A')}")
        self.notify(f"Network: {pool_info.get('network', 'N/A')}")
        self.notify(f"Base Token: {pool_info.get('baseSymbol', 'N/A')}")
        self.notify(f"Quote Token: {pool_info.get('quoteSymbol', 'N/A')}")
        self.notify(f"Pool Address: {pool_info.get('address', 'N/A')}")
