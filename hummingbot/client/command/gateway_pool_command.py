#!/usr/bin/env python
import json
from typing import TYPE_CHECKING, List, Optional, TypedDict

from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode
from hummingbot.core.gateway.gateway_http_client import GatewayStatus
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
        if self.trading_core.gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
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

            # Fetch pool info from Gateway
            self.notify("\nFetching pool information from Gateway...")
            try:
                pool_info_response = await self._get_gateway_instance().pool_info(
                    connector=connector,
                    network=network,
                    pool_address=pool_address
                )

                if "error" in pool_info_response:
                    self.notify(f"Error fetching pool info: {pool_info_response['error']}")
                    self.notify("Cannot add pool without valid pool information")
                    return

                # Extract pool information from response
                fetched_base_symbol = pool_info_response.get("baseSymbol")
                fetched_quote_symbol = pool_info_response.get("quoteSymbol")
                base_token_address = pool_info_response.get("baseTokenAddress")
                quote_token_address = pool_info_response.get("quoteTokenAddress")
                fee_pct = pool_info_response.get("feePct")

                # If symbols are missing, try to fetch them from token addresses
                if not fetched_base_symbol and base_token_address:
                    try:
                        base_token_info = await self._get_gateway_instance().get_token(
                            symbol_or_address=base_token_address,
                            chain=chain,
                            network=network
                        )
                        if "token" in base_token_info and "symbol" in base_token_info["token"]:
                            fetched_base_symbol = base_token_info["token"]["symbol"]
                    except Exception:
                        # Silently skip - symbols are optional
                        pass

                if not fetched_quote_symbol and quote_token_address:
                    try:
                        quote_token_info = await self._get_gateway_instance().get_token(
                            symbol_or_address=quote_token_address,
                            chain=chain,
                            network=network
                        )
                        if "token" in quote_token_info and "symbol" in quote_token_info["token"]:
                            fetched_quote_symbol = quote_token_info["token"]["symbol"]
                    except Exception:
                        # Silently skip - symbols are optional
                        pass

                # Show warning if symbols couldn't be fetched
                if not fetched_base_symbol or not fetched_quote_symbol:
                    self.notify("\n⚠️  Warning: Could not determine token symbols from pool")
                    if not fetched_base_symbol:
                        self.notify(f"  - Base token symbol unknown (address: {base_token_address})")
                    if not fetched_quote_symbol:
                        self.notify(f"  - Quote token symbol unknown (address: {quote_token_address})")
                    self.notify("  Pool will be added without symbols")

                # Display fetched pool information
                self.notify("\n=== Pool Information ===")
                self.notify(f"Connector: {connector}")
                if fetched_base_symbol and fetched_quote_symbol:
                    self.notify(f"Trading Pair: {fetched_base_symbol}-{fetched_quote_symbol}")
                self.notify(f"Pool Type: {trading_type}")
                self.notify(f"Network: {network}")
                self.notify(f"Base Token: {fetched_base_symbol if fetched_base_symbol else 'N/A'}")
                self.notify(f"Quote Token: {fetched_quote_symbol if fetched_quote_symbol else 'N/A'}")
                self.notify(f"Base Token Address: {base_token_address}")
                self.notify(f"Quote Token Address: {quote_token_address}")
                if fee_pct is not None:
                    self.notify(f"Fee: {fee_pct}%")
                self.notify(f"Pool Address: {pool_address}")

                # Create pool data with required and optional fields
                pool_data = {
                    "address": pool_address,
                    "type": trading_type,
                    "baseTokenAddress": base_token_address,
                    "quoteTokenAddress": quote_token_address
                }
                # Add optional fields
                if fetched_base_symbol:
                    pool_data["baseSymbol"] = fetched_base_symbol
                if fetched_quote_symbol:
                    pool_data["quoteSymbol"] = fetched_quote_symbol
                if fee_pct is not None:
                    pool_data["feePct"] = fee_pct

                # Display pool data that will be stored
                self.notify("\nPool to add:")
                self.notify(json.dumps(pool_data, indent=2))

            except Exception as e:
                self.notify(f"Error fetching pool information: {str(e)}")
                self.notify("Cannot add pool without valid pool information")
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

                # Fetch pool info from Gateway
                self.notify("\nFetching pool information from Gateway...")
                try:
                    pool_info_response = await self._get_gateway_instance().pool_info(
                        connector=connector,
                        network=network,
                        pool_address=pool_address
                    )

                    if "error" in pool_info_response:
                        self.notify(f"Error fetching pool info: {pool_info_response['error']}")
                        self.notify("Cannot add pool without valid pool information")
                        return

                    # Extract pool information from response
                    fetched_base_symbol = pool_info_response.get("baseSymbol")
                    fetched_quote_symbol = pool_info_response.get("quoteSymbol")
                    base_token_address = pool_info_response.get("baseTokenAddress")
                    quote_token_address = pool_info_response.get("quoteTokenAddress")
                    fee_pct = pool_info_response.get("feePct")

                    # If symbols are missing, try to fetch them from token addresses
                    if not fetched_base_symbol and base_token_address:
                        try:
                            base_token_info = await self._get_gateway_instance().get_token(
                                symbol_or_address=base_token_address,
                                chain=chain,
                                network=network
                            )
                            if "token" in base_token_info and "symbol" in base_token_info["token"]:
                                fetched_base_symbol = base_token_info["token"]["symbol"]
                        except Exception:
                            # Silently skip - symbols are optional
                            pass

                    if not fetched_quote_symbol and quote_token_address:
                        try:
                            quote_token_info = await self._get_gateway_instance().get_token(
                                symbol_or_address=quote_token_address,
                                chain=chain,
                                network=network
                            )
                            if "token" in quote_token_info and "symbol" in quote_token_info["token"]:
                                fetched_quote_symbol = quote_token_info["token"]["symbol"]
                        except Exception:
                            # Silently skip - symbols are optional
                            pass

                    # Show warning if symbols couldn't be fetched
                    if not fetched_base_symbol or not fetched_quote_symbol:
                        self.notify("\n⚠️  Warning: Could not determine token symbols from pool")
                        if not fetched_base_symbol:
                            self.notify(f"  - Base token symbol unknown (address: {base_token_address})")
                        if not fetched_quote_symbol:
                            self.notify(f"  - Quote token symbol unknown (address: {quote_token_address})")
                        self.notify("  Pool will be added without symbols")

                    # Display fetched pool information
                    self.notify("\n=== Pool Information ===")
                    self.notify(f"Connector: {connector}")
                    if fetched_base_symbol and fetched_quote_symbol:
                        self.notify(f"Trading Pair: {fetched_base_symbol}-{fetched_quote_symbol}")
                    self.notify(f"Pool Type: {trading_type}")
                    self.notify(f"Network: {network}")
                    self.notify(f"Base Token: {fetched_base_symbol if fetched_base_symbol else 'N/A'}")
                    self.notify(f"Quote Token: {fetched_quote_symbol if fetched_quote_symbol else 'N/A'}")
                    self.notify(f"Base Token Address: {base_token_address}")
                    self.notify(f"Quote Token Address: {quote_token_address}")
                    if fee_pct is not None:
                        self.notify(f"Fee: {fee_pct}%")
                    self.notify(f"Pool Address: {pool_address}")

                    # Create pool data with required and optional fields
                    pool_data = {
                        "address": pool_address,
                        "type": trading_type,
                        "baseTokenAddress": base_token_address,
                        "quoteTokenAddress": quote_token_address
                    }
                    # Add optional fields
                    if fetched_base_symbol:
                        pool_data["baseSymbol"] = fetched_base_symbol
                    if fetched_quote_symbol:
                        pool_data["quoteSymbol"] = fetched_quote_symbol
                    if fee_pct is not None:
                        pool_data["feePct"] = fee_pct

                    # Display pool data that will be stored
                    self.notify("\nPool to add:")
                    self.notify(json.dumps(pool_data, indent=2))

                    # Confirm
                    confirm = await self.app.prompt(
                        prompt="Add this pool? (Yes/No) >>> "
                    )

                    if confirm.lower() not in ["y", "yes"]:
                        self.notify("Pool addition cancelled")
                        return

                except Exception as e:
                    self.notify(f"Error fetching pool information: {str(e)}")
                    self.notify("Cannot add pool without valid pool information")
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
        self.notify(f"Base Token Address: {pool_info.get('baseTokenAddress', 'N/A')}")
        self.notify(f"Quote Token Address: {pool_info.get('quoteTokenAddress', 'N/A')}")
        self.notify(f"Fee: {pool_info.get('feePct', 'N/A')}%")
        self.notify(f"Pool Address: {pool_info.get('address', 'N/A')}")
