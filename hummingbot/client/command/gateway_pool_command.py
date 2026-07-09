#!/usr/bin/env python
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode
from hummingbot.core.gateway.gateway_http_client import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    def wrapper(self, *args, **kwargs):
        if self.trading_core.gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayPoolCommand:
    """Commands for managing gateway pools."""

    @ensure_gateway_online
    def gateway_pool(self, symbol_or_address: Optional[str], action: Optional[str]):
        """
        View or update pool information.
        Usage:
            gateway pool <symbol_or_address>       - View pool information
            gateway pool <symbol_or_address> update - Save pool from GeckoTerminal
        """
        if not symbol_or_address:
            # Show help when no arguments provided
            self.notify("\nGateway Pool Commands:")
            self.notify("  gateway pool <symbol_or_address>       - View pool information")
            self.notify("  gateway pool <symbol_or_address> update - Save pool from GeckoTerminal")
            self.notify("\nExamples:")
            self.notify("  gateway pool SOL-USDC      # Search by trading pair")
            self.notify("  gateway pool SOL           # Search by token symbol")
            self.notify("  gateway pool ORCA          # Search by base or quote symbol")
            self.notify("  gateway pool 58oQChx...    # Search by pool address")
            self.notify("  gateway pool So111...      # Search by token address")
            self.notify("  gateway pool SOL-USDC update")
            return

        if action == "update":
            safe_ensure_future(
                self._update_pool_interactive(symbol_or_address),
                loop=self.ev_loop
            )
        else:
            safe_ensure_future(
                self._view_pool(symbol_or_address),
                loop=self.ev_loop
            )

    async def _view_pool(
        self,  # type: HummingbotApplication
        symbol_or_address: str
    ):
        """View pool information across all chains."""
        try:
            # Get all available chains from the Chain enum
            from hummingbot.connector.gateway.common_types import Chain
            chains_to_check = [chain.chain for chain in Chain]
            found_pools: List[Dict] = []

            self.notify(f"\nSearching for '{symbol_or_address}' across all chains' default networks...")

            search_lower = symbol_or_address.lower()

            for chain in chains_to_check:
                # Get default network for this chain
                default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
                if not default_network:
                    continue

                # Get all pools for this chain/network
                response = await self._get_gateway_instance().list_pools(
                    chain=chain,
                    network=default_network,
                    fail_silently=True
                )

                if "error" not in response and isinstance(response, list):
                    for pool in response:
                        # Search across multiple fields: address, baseTokenAddress, quoteTokenAddress, baseSymbol, quoteSymbol
                        address = pool.get("address", "").lower()
                        base_token_address = pool.get("baseTokenAddress", "").lower()
                        quote_token_address = pool.get("quoteTokenAddress", "").lower()
                        base_symbol = pool.get("baseSymbol", "").lower()
                        quote_symbol = pool.get("quoteSymbol", "").lower()
                        trading_pair = f"{base_symbol}-{quote_symbol}"

                        # Check if search term matches any field
                        matches = (
                            search_lower in address or
                            search_lower in base_token_address or
                            search_lower in quote_token_address or
                            search_lower in base_symbol or
                            search_lower in quote_symbol or
                            search_lower in trading_pair
                        )
                        if matches:
                            pool_info = {
                                "chain": chain,
                                "network": default_network,
                                "connector": pool.get("connector", "N/A"),
                                "type": pool.get("type", "N/A"),
                                "pair": f"{pool.get('baseSymbol', '?')}-{pool.get('quoteSymbol', '?')}",
                                "address": pool.get("address", "N/A"),
                                "feePct": pool.get("feePct", "N/A")
                            }
                            found_pools.append(pool_info)

            if found_pools:
                self._display_pools_table(found_pools)
            else:
                self.notify(f"\nNo pools matching '{symbol_or_address}' found on any chain's default network.")
                self.notify("You may need to add it using 'gateway pool <address> update'")

        except Exception as e:
            self.notify(f"Error fetching pool information: {str(e)}")

    async def _update_pool_interactive(
        self,  # type: HummingbotApplication
        symbol_or_address: str
    ):
        """Interactive flow to update or add a pool."""
        try:
            with begin_placeholder_mode(self):
                # Ask for chain
                chain = await self.app.prompt(
                    prompt="Enter chain (e.g., ethereum, solana): "
                )

                if self.app.to_stop_config or not chain:
                    self.notify("Pool update cancelled")
                    return

                # Get default network for the chain
                default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
                if not default_network:
                    self.notify(f"Could not determine default network for chain '{chain}'")
                    return

                # Build chainNetwork string
                chain_network = f"{chain}-{default_network}"

                # Check if this looks like an address
                is_address = self._looks_like_address(symbol_or_address)

                if is_address:
                    # Direct address provided, use save endpoint
                    pool_address = symbol_or_address
                else:
                    # Symbol or trading pair provided, search for existing pools first
                    search_lower = symbol_or_address.lower()
                    response = await self._get_gateway_instance().list_pools(
                        chain=chain,
                        network=default_network,
                        fail_silently=True
                    )

                    existing_pools = []
                    if "error" not in response and isinstance(response, list):
                        for pool in response:
                            base_symbol = pool.get("baseSymbol", "").lower()
                            quote_symbol = pool.get("quoteSymbol", "").lower()
                            trading_pair = f"{base_symbol}-{quote_symbol}"
                            matches = (
                                search_lower in base_symbol or
                                search_lower in quote_symbol or
                                search_lower in trading_pair
                            )
                            if matches:
                                existing_pools.append(pool)

                    if existing_pools:
                        # Pool exists, show current info
                        self.notify("\nExisting pool(s) found:")
                        self._display_pools_table([{
                            "chain": chain,
                            "network": default_network,
                            "connector": p.get("connector", "N/A"),
                            "type": p.get("type", "N/A"),
                            "pair": f"{p.get('baseSymbol', '?')}-{p.get('quoteSymbol', '?')}",
                            "address": p.get("address", "N/A"),
                            "feePct": p.get("feePct", "N/A")
                        } for p in existing_pools])

                        # Ask if they want to add another
                        add_response = await self.app.prompt(
                            prompt="Do you want to add a new pool for this pair? (Yes/No) >>> "
                        )

                        if add_response.lower() not in ["y", "yes"]:
                            self.notify("Pool update cancelled")
                            return

                    # Ask for pool address
                    pool_address = await self.app.prompt(
                        prompt="Enter pool contract address: "
                    )
                    if self.app.to_stop_config or not pool_address:
                        self.notify("Pool update cancelled")
                        return

                # Save pool using GeckoTerminal lookup
                self.notify(f"\nSaving pool {pool_address} on {chain_network}...")
                self.notify("Fetching pool information from GeckoTerminal...")

                result = await self._get_gateway_instance().save_pool(
                    chain_network=chain_network,
                    address=pool_address
                )

                if "error" in result:
                    self.notify(f"Error: {result['error']}")
                else:
                    self.notify("✓ Pool successfully saved!")

                    # Display saved pool info
                    pool = result.get("pool", {})
                    self.notify("\nSaved pool information:")
                    self.notify(f"  Connector: {pool.get('connector', 'N/A')}")
                    self.notify(f"  Type: {pool.get('type', 'N/A')}")
                    self.notify(f"  Trading Pair: {pool.get('baseSymbol', '?')}-{pool.get('quoteSymbol', '?')}")
                    self.notify(f"  Address: {pool.get('address', 'N/A')}")
                    self.notify(f"  Fee: {pool.get('feePct', 'N/A')}%")

                    # Show tokens added if any
                    tokens_added = result.get("tokensAdded", [])
                    if tokens_added:
                        self.notify(f"\nAuto-added tokens: {', '.join(tokens_added)}")

                    # Restart gateway for changes to take effect
                    self.notify("\nRestarting Gateway for changes to take effect...")
                    try:
                        await self._get_gateway_instance().post_restart()
                        self.notify("✓ Gateway restarted successfully")
                        trading_pair = f"{pool.get('baseSymbol', '?')}-{pool.get('quoteSymbol', '?')}"
                        self.notify(f"\nYou can now use 'gateway pool {trading_pair}' to view the pool information.")
                    except Exception as e:
                        self.notify(f"⚠️  Failed to restart Gateway: {str(e)}")
                        self.notify("You may need to restart Gateway manually for changes to take effect")

        except Exception as e:
            self.notify(f"Error updating pool: {str(e)}")

    def _looks_like_address(self, value: str) -> bool:
        """Check if a value looks like a blockchain address."""
        # EVM addresses start with 0x and are 42 chars
        if value.startswith("0x") and len(value) == 42:
            return True
        # Solana addresses are base58, typically 32-44 chars, no hyphens
        if len(value) >= 32 and "-" not in value and not value.startswith("0x"):
            return True
        return False

    def _display_pools_table(self, pools: List[Dict]):
        """Display pools in a table format."""
        self.notify("\nFound pools:")

        # Create DataFrame for display
        df = pd.DataFrame(pools)

        # Reorder columns for better display
        columns_order = ["chain", "network", "connector", "type", "pair", "address", "feePct"]
        available_columns = [col for col in columns_order if col in df.columns]
        df = df[available_columns]

        # Format the dataframe for display
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self.notify("\n".join(lines))

    def _display_single_pool(
        self,
        pool_info: dict,
        chain: str,
        network: str
    ):
        """Display a single pool's information."""
        self.notify(f"\nChain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Connector: {pool_info.get('connector', 'N/A')}")
        self.notify(f"Type: {pool_info.get('type', 'N/A')}")
        self.notify(f"Base Token: {pool_info.get('baseSymbol', 'N/A')}")
        self.notify(f"Quote Token: {pool_info.get('quoteSymbol', 'N/A')}")
        self.notify(f"Address: {pool_info.get('address', 'N/A')}")
        self.notify(f"Fee: {pool_info.get('feePct', 'N/A')}%")
