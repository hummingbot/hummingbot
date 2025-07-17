#!/usr/bin/env python
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from hummingbot.connector.gateway.utils.command_utils import GatewayCommandUtils
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayPoolCommand:
    """Handles gateway pool-related commands"""

    @GatewayCommandUtils.ensure_gateway_online
    def gateway_pool(self, action: str = None, args: List[str] = None):
        """
        Manage pools in gateway.
        Usage:
            gateway pool list <connector> <network> [type]     - List pools
            gateway pool show <connector> <network> <address>  - Show pool details
            gateway pool add <connector> <network>             - Add a new pool (interactive)
            gateway pool remove <connector> <network> <address> - Remove pool by address
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway pool list <connector> <network> [type]       - List pools")
            self.notify("  gateway pool show <connector> <network> <address>    - Show pool details")
            self.notify("  gateway pool add <connector> <network>               - Add a new pool (interactive)")
            self.notify("  gateway pool remove <connector> <network> <address>  - Remove pool by address")
            self.notify("\nExamples:")
            self.notify("  gateway pool list uniswap mainnet")
            self.notify("  gateway pool list raydium mainnet-beta clmm")
            self.notify("  gateway pool add raydium mainnet-beta")
            return

        if action == "list":
            # Parse positional arguments: [connector] [network] [type]
            connector = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            pool_type = args[2] if args and len(args) > 2 else None
            safe_ensure_future(self._gateway_pool_list(connector, network, pool_type), loop=self.ev_loop)

        elif action == "add":
            if args is None or len(args) < 2:
                self.notify("Error: connector and network parameters are required for 'add' action")
                return
            connector = args[0]
            network = args[1]
            safe_ensure_future(self._gateway_pool_add_interactive(connector, network), loop=self.ev_loop)

        elif action == "remove":
            if args is None or len(args) < 3:
                self.notify("Error: connector, network and address parameters are required for 'remove' action")
                return
            connector = args[0]
            network = args[1]
            address = args[2]
            safe_ensure_future(self._gateway_pool_remove(connector, network, address), loop=self.ev_loop)

        elif action == "show":
            if args is None or len(args) < 3:
                self.notify("Error: connector, network and address parameters are required for 'show' action")
                return
            connector = args[0]
            network = args[1]
            address = args[2]
            safe_ensure_future(self._gateway_pool_show(connector, network, address), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'show', 'add', or 'remove'.")

    async def _gateway_pool_list(self, connector: Optional[str] = None, network: Optional[str] = None, pool_type: Optional[str] = None):
        """List pools from gateway with optional filters."""
        try:
            # Validate connector
            if not connector:
                self.notify("Error: Connector is required")
                self.notify("Usage: gateway pool list <connector> <network> [type]")
                self.notify("Example: gateway pool list uniswap base")
                return

            # Parse connector name to get base name
            base_connector, _ = GatewayCommandUtils.parse_connector_trading_type(connector)

            # Validate connector exists
            connector_info = await self._get_gateway_instance().get_connector_info(base_connector)
            if not connector_info:
                self.notify(f"Error: Connector '{base_connector}' not found")
                return

            # Use default network if not provided
            if not network:
                chain = connector_info.get("chain", "")
                network, error = await GatewayCommandUtils.get_network_for_chain(
                    self._get_gateway_instance(), chain
                )
                if error:
                    self.notify(error)
                    return
                self.notify(f"Using default network: {network}")

            # Get pools for specific connector and network
            pools = await self._get_gateway_instance().get_pools(base_connector, network, pool_type)

            if not pools:
                filters = f"{connector}/{network}"
                if pool_type:
                    filters += f" (type={pool_type})"
                self.notify(f"No pools found for {filters}")
                return

            # Display pools in a table (without fee column)
            columns = ["Type", "Base", "Quote", "Address"]
            data = []
            for pool in pools:
                data.append([
                    pool.get("type", ""),
                    pool.get("baseSymbol", ""),
                    pool.get("quoteSymbol", ""),
                    pool.get("address", "")[:10] + "..." if pool.get("address") else ""
                ])

            df = pd.DataFrame(data, columns=columns)
            self.notify(f"\nPools for {connector}/{network} ({len(pools)} total):")
            self.notify(df.to_string(index=False))

        except Exception as e:
            self.notify(f"Error listing pools: {str(e)}")

    async def _gateway_pool_add_interactive(self, connector: str, network: str):
        """Add a new pool to the gateway - interactive mode."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            self.notify(f"\nAdding a new pool to {connector}/{network}")

            # Prompt for pool type
            self.notify("\nAvailable pool types:")
            self.notify("  - amm  : Automated Market Maker")
            self.notify("  - clmm : Concentrated Liquidity Market Maker")

            pool_type = await self.app.prompt(prompt="\nPool type (amm/clmm): ")
            if self.app.to_stop_config or not pool_type:
                self.notify("Pool addition cancelled")
                return

            if pool_type.lower() not in ["amm", "clmm"]:
                self.notify(f"Error: Invalid pool type '{pool_type}'. Must be 'amm' or 'clmm'")
                return

            # Parse connector to get chain
            base_connector, _ = GatewayCommandUtils.parse_connector_trading_type(connector)
            connector_info = await self._get_gateway_instance().get_connector_info(base_connector)
            chain = connector_info.get("chain", "ethereum") if connector_info else "ethereum"

            # Get available tokens for this network
            token_symbols = await GatewayCommandUtils.get_available_tokens(
                self._get_gateway_instance(), chain, network
            )
            if token_symbols:
                self.notify(f"\nAvailable tokens on {chain}/{network}:")
                # Display tokens in columns
                cols = 4
                for i in range(0, len(token_symbols), cols):
                    row = "  " + "  ".join(f"{sym:10}" for sym in token_symbols[i:i + cols])
                    self.notify(row)

            # Prompt for base token
            base = await self.app.prompt(prompt="\nBase token symbol (e.g., WETH): ")
            if self.app.to_stop_config or not base:
                self.notify("Pool addition cancelled")
                return
            base = GatewayCommandUtils.normalize_token_symbol(base)

            # Prompt for quote token
            quote = await self.app.prompt(prompt="Quote token symbol (e.g., USDC): ")
            if self.app.to_stop_config or not quote:
                self.notify("Pool addition cancelled")
                return
            quote = GatewayCommandUtils.normalize_token_symbol(quote)

            # Prompt for pool address
            address = await self.app.prompt(prompt="Pool contract address: ")
            if self.app.to_stop_config or not address:
                self.notify("Pool addition cancelled")
                return

            # Validate address format
            address, error = GatewayCommandUtils.validate_address(address)
            if error:
                self.notify(error)
                return

            # Confirm addition
            self.notify("\nPool to be added:")
            self.notify(f"  Connector: {connector}")
            self.notify(f"  Network: {network}")
            self.notify(f"  Type: {pool_type}")
            self.notify(f"  Base Token: {base}")
            self.notify(f"  Quote Token: {quote}")
            self.notify(f"  Address: {address}")

            confirm = await self.app.prompt(prompt="\nDo you want to add this pool? (Yes/No) >>> ")
            if confirm.lower() not in ["y", "yes"]:
                self.notify("Pool addition cancelled")
                return

            # Add pool
            pool_data = {
                "type": pool_type,
                "baseToken": base,
                "quoteToken": quote,
                "address": address
            }
            response = await self._get_gateway_instance().add_pool(connector, network, pool_data)

            if "error" in response:
                self.notify(f"Error adding pool: {response['error']}")
            else:
                self.notify(f"\n✓ {response.get('message', 'Pool added successfully')}")
                if response.get("requiresRestart", False):
                    self.notify("⚠ Gateway restart required for changes to take effect")
                    self.notify("  Please restart the gateway service")

        except Exception as e:
            self.notify(f"Error adding pool: {str(e)}")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_pool_remove(self, connector: str, network: str, address: str):
        """Remove a pool from the gateway."""
        try:
            # Try to get pool details first
            pool_info = await self._get_gateway_instance().get_pool(address, connector, network)

            if "error" not in pool_info and "pool" in pool_info:
                pool = pool_info["pool"]
                self.notify(f"\nRemoving pool from {connector}/{network}:")
                self.notify(f"  Type: {pool.get('type', 'Unknown')}")
                self.notify(f"  Base: {pool.get('baseToken', 'Unknown')}")
                self.notify(f"  Quote: {pool.get('quoteToken', 'Unknown')}")
                self.notify(f"  Address: {address}")
            else:
                self.notify(f"\nRemoving pool {address} from {connector}/{network}")

            confirm = await self.app.prompt(prompt="\nDo you want to remove this pool? (Yes/No) >>> ")
            if confirm.lower() in ["y", "yes"]:
                # Remove pool
                response = await self._get_gateway_instance().remove_pool(address, connector, network)

                if "error" in response:
                    self.notify(f"Error removing pool: {response['error']}")
                else:
                    self.notify(f"\n✓ {response.get('message', 'Pool removed successfully')}")
                    if response.get("requiresRestart", False):
                        self.notify("⚠ Gateway restart required for changes to take effect")
                        self.notify("  Please restart the gateway service")
            else:
                self.notify("Pool removal cancelled")

        except Exception as e:
            self.notify(f"Error removing pool: {str(e)}")

    async def _gateway_pool_show(self, connector: str, network: str, address: str):
        """Show details for a specific pool."""
        try:
            # Search for the pool using the address
            pools = await self._get_gateway_instance().get_pools(connector, network)

            # Filter pools by address
            matching_pool = None
            for pool in pools:
                if pool.get("address", "").lower() == address.lower():
                    matching_pool = pool
                    break

            if not matching_pool:
                self.notify(f"Pool '{address}' not found on {connector}/{network}")
                return

            # Display pool details
            self.notify("\nPool Details:")
            self.notify(f"  Connector: {connector}")
            self.notify(f"  Network: {network}")
            self.notify(f"  Type: {matching_pool.get('type', 'N/A')}")
            self.notify(f"  Base Token: {matching_pool.get('baseSymbol', 'N/A')}")
            self.notify(f"  Quote Token: {matching_pool.get('quoteSymbol', 'N/A')}")
            self.notify(f"  Address: {matching_pool.get('address', 'N/A')}")

        except Exception as e:
            error_msg = str(e)
            if "NotFoundError" in error_msg or "404" in error_msg:
                self.notify(f"Pool '{address}' not found on {connector}/{network}")
                self.notify("Please check the pool address or try adding it with 'gateway pool add'")
            else:
                self.notify(f"Error retrieving pool information: {error_msg}")
