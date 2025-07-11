#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.command.gateway_pool_command import GatewayPoolCommand
from hummingbot.client.command.gateway_swap_command import GatewaySwapCommand
from hummingbot.client.command.gateway_token_command import GatewayTokenCommand
from hummingbot.client.command.gateway_wallet_command import GatewayWalletCommand
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.gateway.core import GatewayClient, GatewayStatus
from hummingbot.connector.gateway.utils.gateway_utils import get_gateway_paths
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_dict_display
from hummingbot.core.utils.ssl_cert import create_self_sign_certs

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    def wrapper(self, *args, **kwargs):
        if self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayCommand(GatewayChainApiManager, GatewayTokenCommand, GatewayWalletCommand, GatewayPoolCommand, GatewaySwapCommand):
    """Main gateway command handler that inherits from specialized command classes."""
    client_config_map: ClientConfigMap
    _market: Dict[str, Any] = {}

    def __init__(self,  # type: HummingbotApplication
                 client_config_map: ClientConfigMap
                 ):
        self.client_config_map = client_config_map

    @ensure_gateway_online
    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_balance(self, chain: Optional[str] = None, network: Optional[str] = None,
                        address: Optional[str] = None, tokens: Optional[str] = None):
        safe_ensure_future(self._get_balances(chain, network, address, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_allowance(self, spender: Optional[str] = None, network: Optional[str] = None,
                          address: Optional[str] = None, tokens: Optional[str] = None):
        """
        Command to check token allowances for Ethereum-based connectors
        Usage: gateway allowance [spender] [network] [address] [tokens]
        """
        safe_ensure_future(self._get_allowances(spender, network, address, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_approve(self, spender: Optional[str] = None, network: Optional[str] = None,
                        tokens: Optional[str] = None):
        """
        Command to approve tokens for spending on a connector
        Usage: gateway approve [spender] [network] [tokens]
        """
        if all([spender, network, tokens]):
            safe_ensure_future(self._approve_tokens(spender, network, tokens), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify all required parameters: spender, network, and tokens.\n"
                "Usage: gateway approve <spender> <network> <tokens>\n"
                "Example: gateway approve uniswap/amm mainnet USDC,USDT\n")

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_ping(self, chain: Optional[str] = None, network: Optional[str] = None):
        """
        Test gateway connectivity and check network status.
        Usage:
            gateway ping              - Check all chains with default networks
            gateway ping [chain]      - Check specific chain with default network
            gateway ping [chain] [network] - Check specific chain and network
        """
        safe_ensure_future(self._gateway_ping(chain, network), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_list(self):
        safe_ensure_future(self._gateway_list(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_config(self, action: str = None, namespace: str = None, args: List[str] = None):
        """
        Gateway configuration management.
        Usage:
            gateway config show [namespace]
            gateway config update <namespace> <path> <value>
        """
        if args is None:
            args = []

        if action == "show":
            # Format: gateway config show [namespace]
            # namespace can be: server, uniswap, ethereum-mainnet, solana-devnet, etc.
            safe_ensure_future(self._show_gateway_configuration(namespace=namespace), loop=self.ev_loop)
        elif action is None:
            # Show help when no action is provided
            self.notify("\nUsage:")
            self.notify("  gateway config show [namespace]")
            self.notify("  gateway config update <namespace> <path> <value>")
            self.notify("\nExamples:")
            self.notify("  gateway config show ethereum-mainnet")
            self.notify("  gateway config show uniswap")
            self.notify("  gateway config update ethereum-mainnet gasLimitTransaction 3000000")
        elif action == "update":
            if namespace is None:
                self.notify("Error: namespace is required for config update")
                return

            # Handle the format: gateway config update <namespace> <path> <value>
            # where namespace includes network (e.g., ethereum-mainnet, solana-mainnet-beta)
            if len(args) >= 2:
                path = args[0]
                value = args[1]
            else:
                self.notify("Error: path and value are required for config update")
                self.notify("Usage: gateway config update <namespace> <path> <value>")
                self.notify("Example: gateway config update solana-mainnet-beta nodeURL https://api.mainnet-beta.solana.com")
                return

            safe_ensure_future(self._update_gateway_configuration(namespace, path, value), loop=self.ev_loop)
        else:
            # Show help if unrecognized action
            self.notify("\nUsage:")
            self.notify("  gateway config show [namespace]")
            self.notify("  gateway config update <namespace> <path> <value>")

    # Delegate to inherited methods from GatewayWalletCommand
    # The @ensure_gateway_online decorator is handled by the parent method

    # Delegate to inherited methods from GatewayTokenCommand
    # The @ensure_gateway_online decorator is handled by the parent method

    # Delegate to inherited methods from GatewayPoolCommand
    # The @ensure_gateway_online decorator is handled by the parent method

    @ensure_gateway_online
    def gateway_wrap(self, network: Optional[str] = None, amount: Optional[str] = None):
        """
        Command to wrap native tokens to wrapped tokens
        Usage: gateway wrap [network] [amount]
        """
        if all([network, amount]):
            safe_ensure_future(self._wrap_tokens(network, amount), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify both network and amount.\n"
                "Usage: gateway wrap <network> <amount>\n"
                "Example: gateway wrap mainnet 0.1\n"
            )

    async def _gateway_ping(self, chain: Optional[str] = None, network: Optional[str] = None):
        """
        Test gateway connectivity and check network status.
        If chain and network are specified, check only that specific network.
        Otherwise, check default network for each chain.
        """
        try:
            # First check if gateway is running
            gateway_status = await self._get_gateway_instance().ping_gateway()
            if not gateway_status:
                self.notify("\nUnable to connect to gateway.")
                return

            self.notify("\nGateway Status: Online")

            # If specific chain and network are provided, check only that
            if chain and network:
                await self._check_network_status(chain, network)
                return

            # If only chain is provided, check default network for that chain
            if chain and not network:
                # Get available networks for this chain
                chains_resp = await self._get_gateway_instance().get_chains()
                chain_found = False
                for chain_info in chains_resp:
                    if chain_info.get("chain", "").lower() == chain.lower():
                        chain_found = True
                        networks = chain_info.get("networks", [])
                        if networks:
                            # Use default network logic
                            default_network = await self._get_default_network_for_chain(chain)
                            if not default_network:
                                default_network = networks[0]
                            await self._check_network_status(chain, default_network)
                        break

                if not chain_found:
                    self.notify(f"\nChain '{chain}' not found. Available chains:")
                    for chain_info in chains_resp:
                        self.notify(f"  - {chain_info.get('chain', '')}")
                return

            # Otherwise, check all chains with their default networks
            chains_resp = await self._get_gateway_instance().get_chains()
            if not chains_resp:
                self.notify("Unable to fetch chains from gateway.")
                return

            # For each chain, check the default network connection
            for chain_info in chains_resp:
                chain_name = chain_info.get("chain", "")
                networks = chain_info.get("networks", [])

                if not networks:
                    continue

                # Use the same default network logic as gateway balance
                default_network = await self._get_default_network_for_chain(chain_name)
                if not default_network:
                    # Fallback to first network if no default
                    default_network = networks[0]

                await self._check_network_status(chain_name, default_network)

        except Exception as e:
            self.notify(f"\nError pinging gateway: {str(e)}")

    async def _check_network_status(self, chain: str, network: str):
        """Check the status of a specific chain and network."""
        self.notify(f"\nChain: {chain}")
        self.notify(f"Network: {network}")

        # Get network status including block number
        start_time = time.time()
        try:
            # Get network status from gateway
            status_resp = await self._get_gateway_instance().get_network_status(chain, network)

            # Calculate latency
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds

            if status_resp:
                self.notify("Status: Connected")

                # Display RPC URL if available
                rpc_url = status_resp.get("rpcUrl")
                if rpc_url:
                    self.notify(f"RPC URL: {rpc_url}")

                # Display current block number
                block_number = status_resp.get("currentBlockNumber")
                if block_number is not None:
                    self.notify(f"Current Block: {block_number:,}")

                # Try to get native currency as well
                try:
                    native_currency = await self._get_native_currency_symbol(chain, network)
                    if native_currency:
                        self.notify(f"Native Token: {native_currency}")
                except Exception:
                    pass

                self.notify(f"Latency: {latency:.1f} ms")
            else:
                self.notify("Status: Connected (no status info)")
                self.notify(f"Latency: {latency:.1f} ms")

        except asyncio.TimeoutError:
            self.notify("Status: Timeout")
        except Exception as e:
            self.notify(f"Status: Error - {str(e)}")

    async def _generate_certs(
            self,       # type: HummingbotApplication
            from_client_password: bool = False,
    ):

        certs_path: str = get_gateway_paths(
            self.client_config_map).local_certs_path.as_posix()

        if not from_client_password:
            with begin_placeholder_mode(self):
                while True:
                    pass_phase = await self.app.prompt(
                        prompt='Enter pass phrase to generate Gateway SSL certifications  >>> ',
                        is_password=True
                    )
                    if pass_phase is not None and len(pass_phase) > 0:
                        break
                    self.notify("Error: Invalid pass phrase")
        else:
            pass_phase = Security.secrets_manager.password.get_secret_value()
        create_self_sign_certs(pass_phase, certs_path)
        self.notify(
            f"Gateway SSL certification files are created in {certs_path}.")
        self._get_gateway_instance().reload_certs(self.client_config_map)

    async def ping_gateway_api(self, max_wait: int) -> bool:
        """
        Try to reach the gateway API for up to max_wait seconds
        """
        now = int(time.time())
        gateway_live = await self._get_gateway_instance().ping_gateway()
        while not gateway_live:
            later = int(time.time())
            if later - now > max_wait:
                return False
            await asyncio.sleep(0.5)
            gateway_live = await self._get_gateway_instance().ping_gateway()
            later = int(time.time())

        return True

    async def _gateway_status(self):
        if self._gateway_monitor.gateway_status is GatewayStatus.ONLINE:
            try:
                status = await self._get_gateway_instance().get_gateway_status()
                if status is None or status == []:
                    self.notify("There are currently no connectors online.")
                else:
                    self.notify(pd.DataFrame(status))
            except Exception:
                self.notify(
                    "\nError: Unable to fetch status of connected Gateway server.")
        else:
            self.notify(
                "\nNo connection to Gateway server exists. Ensure Gateway server is running.")

    async def _update_gateway_configuration(self, namespace: str, path: str, value: Any):
        try:
            # Try to parse value as appropriate type
            try:
                # Try to parse as number first
                if "." in value:
                    parsed_value = float(value)
                else:
                    parsed_value = int(value)
            except ValueError:
                # Try to parse as boolean
                if value.lower() in ["true", "false"]:
                    parsed_value = value.lower() == "true"
                else:
                    # Keep as string
                    parsed_value = value

            response = await self._get_gateway_instance().update_config(
                namespace=namespace,
                path=path,
                value=parsed_value
            )
            self.notify(f"\n✓ {response.get('message', 'Configuration updated successfully')}")
        except Exception as e:
            self.notify(f"\nError: Gateway configuration update failed: {str(e)}")

    async def _show_gateway_configuration(
        self,  # type: HummingbotApplication
        namespace: Optional[str] = None,
    ):
        host = self.client_config_map.gateway.gateway_api_host
        port = self.client_config_map.gateway.gateway_api_port
        try:
            # Use new get_config method with only namespace
            config_dict = await self._get_gateway_instance().get_config(namespace=namespace)

            # Format the title
            title_parts = ["Gateway Configuration"]
            if namespace:
                title_parts.append(f"namespace: {namespace}")
            title = f"\n{' - '.join(title_parts)} ({host}:{port}):"

            self.notify(title)
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            remote_host = ':'.join([host, port])
            self.notify(f"\nError: Connection to Gateway {remote_host} failed: {str(e)}")

    async def _get_balances(self, chain_filter: Optional[str] = None, network_filter: Optional[str] = None,
                            address_filter: Optional[str] = None, tokens_filter: Optional[str] = None):
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        # Use longer timeout for balance requests since some networks like Base can be slow
        balance_timeout = max(network_timeout, 10.0)  # At least 10 seconds
        self.notify("Updating gateway balances, please wait...")

        try:
            # Get all wallets from gateway
            all_wallets = await self._get_gateway_instance().get_wallets()

            if not all_wallets:
                self.notify("No wallets found in gateway. Please add wallets with 'gateway wallet add <chain>'")
                return

            # Build list of chain/network combinations with their addresses
            chain_network_combos = []
            for wallet_info in all_wallets:
                chain = wallet_info.get("chain", "")
                addresses = wallet_info.get("walletAddresses", [])
                readonly_addresses = wallet_info.get("readOnlyWalletAddresses", [])
                hardware_addresses = wallet_info.get("hardwareWalletAddresses", [])

                # Combine all addresses
                all_addresses = addresses + readonly_addresses + hardware_addresses

                if not all_addresses:
                    continue

                # Apply chain filter
                if chain_filter and chain.lower() != chain_filter.lower():
                    continue

                # Get default network for this chain
                if network_filter:
                    # If user specified a network, use it
                    default_network = network_filter
                else:
                    # Get the default (first) network for this chain
                    default_network = await self._get_default_network_for_chain(chain)
                    if not default_network:
                        continue

                # Use all addresses or filter by specific address
                if address_filter:
                    # Check if address_filter matches any wallet address
                    matching_addresses = [addr for addr in all_addresses if addr.lower() == address_filter.lower()]
                    if not matching_addresses:
                        continue
                    use_addresses = matching_addresses
                else:
                    # When no filter, show all wallets including read-only
                    use_addresses = all_addresses

                for address in use_addresses:
                    # Mark if this is a read-only or hardware address
                    is_readonly = address in readonly_addresses
                    is_hardware = address in hardware_addresses
                    chain_network_combos.append((chain, default_network, address, is_readonly, is_hardware))

            if not chain_network_combos:
                self.notify("No matching wallets found for the specified filters.")
                return

            # Process each chain/network/address combination
            for chain, network, address, is_readonly, is_hardware in chain_network_combos:
                try:
                    # Determine tokens to check
                    if tokens_filter:
                        # User specified tokens (comma-separated)
                        tokens_to_check = [token.strip() for token in tokens_filter.split(",")]
                        # Skip if user specified tokens but the list is empty (after filtering out empty strings)
                        if not tokens_to_check:
                            self.notify(f"\nNo valid tokens specified for {chain}:{network}")
                            continue
                    else:
                        # No filter specified - fetch all tokens
                        tokens_to_check = []

                    # Get balances from gateway
                    try:
                        tokens_display = "all" if not tokens_to_check else ", ".join(tokens_to_check)
                        self.notify(f"Fetching balances for {chain}:{network} address {address[:8]}... tokens: {tokens_display}")
                        balances_resp = await asyncio.wait_for(
                            self._get_gateway_instance().get_balances(chain, network, address, tokens_to_check),
                            balance_timeout
                        )
                        balances = balances_resp.get("balances", {})
                    except asyncio.TimeoutError:
                        self.notify(f"\nTimeout getting balance for {chain}:{network}")
                        self.notify("This may happen if the network is congested or the RPC endpoint is slow.")
                        self.notify("Try again or check your gateway configuration.")
                        continue

                    # Filter out zero balances unless user specified specific tokens
                    if tokens_filter:
                        # Show all requested tokens even if zero
                        display_balances = balances
                    else:
                        # Show non-zero balances and always show native token
                        display_balances = {}
                        native_token = await self._get_native_currency_symbol(chain, network)

                        for token, bal in balances.items():
                            balance_val = float(bal) if bal else 0
                            # Always include native token (even if zero), include others only if non-zero
                            if (native_token and token.upper() == native_token.upper()) or balance_val > 0:
                                display_balances[token] = bal

                    # Display results
                    self.notify(f"\nChain: {chain.lower()}")
                    self.notify(f"Network: {network}")
                    if is_hardware:
                        self.notify(f"Address: {address} (hardware)")
                    elif is_readonly:
                        self.notify(f"Address: {address} (read-only)")
                    else:
                        self.notify(f"Address: {address}")

                    if display_balances:
                        rows = []
                        for token, bal in display_balances.items():
                            rows.append({
                                "Token": token.upper(),
                                "Balance": PerformanceMetrics.smart_round(Decimal(str(bal)), 4),
                            })

                        df = pd.DataFrame(data=rows, columns=["Token", "Balance"])
                        df.sort_values(by=["Token"], inplace=True)

                        lines = [
                            "    " + line for line in df.to_string(index=False).split("\n")
                        ]
                        self.notify("\n".join(lines))
                    else:
                        self.notify("    No balances found")

                except Exception as e:
                    self.notify(f"\nError getting balance for {chain}:{network}: {str(e)}")
                    if "internalServerError" in str(e) or "Cannot read properties of undefined" in str(e):
                        self.notify("This may be a gateway server configuration issue.")
                        self.notify("Check that the RPC endpoint for this network is properly configured.")

        except Exception as e:
            self.notify(f"Error fetching gateway data: {str(e)}")

    async def _get_default_tokens_for_chain_network(self, chain: str, network: str) -> List[str]:
        """
        Get a list of common/popular tokens for a specific chain and network from gateway.
        Returns top tokens by market cap or trading volume.
        """
        try:
            # Fetch tokens from gateway
            tokens_response = await self._get_gateway_instance().get_tokens(chain, network, fail_silently=True)

            if not tokens_response or not isinstance(tokens_response, dict):
                return []

            tokens_list = tokens_response.get("tokens", [])
            if not tokens_list:
                return []

            # Extract token symbols from the response
            # The tokens are typically sorted by market cap or importance
            # Take the first tokens as "default" tokens
            default_token_limit = 15  # Configurable limit for default tokens
            token_symbols = []
            for token in tokens_list[:default_token_limit]:
                if isinstance(token, dict):
                    symbol = token.get("symbol")
                    if symbol:
                        token_symbols.append(symbol)
                elif isinstance(token, str):
                    # Sometimes tokens might be returned as simple strings
                    token_symbols.append(token)

            return token_symbols

        except Exception as e:
            # Log error but don't fail the entire operation
            self.logger().debug(f"Failed to fetch default tokens for {chain}:{network}: {e}")
            return []

    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            await market._update_balances()
        except Exception as e:
            logging.getLogger().debug(
                f"Failed to update balances for {market}", exc_info=True)
            return str(e)
        return None

    async def _get_native_currency_symbol(self, chain: str, network: str) -> Optional[str]:
        """Get the native currency symbol for a given chain and network."""
        try:
            # Get from gateway configuration for the specific chain-network
            namespace = f"{chain}-{network}"
            config = await self._get_gateway_instance().get_configuration(namespace)

            # The native currency symbol is directly in the config
            if config and "nativeCurrencySymbol" in config:
                return config["nativeCurrencySymbol"]

            return None
        except Exception as e:
            self.logger().debug(f"Failed to get native currency for {chain}-{network}: {e}")
            return None

    async def _gateway_list(
        self           # type: HummingbotApplication
    ):
        connector_dict: Dict[str, Dict[str, Any]] = await self._get_gateway_instance().get_connectors()
        connectors_tiers: List[Dict[str, Any]] = []

        for connector_name, connector in connector_dict.items():
            # Chain and networks are now directly in the connector config
            chain = connector["chain"]
            networks = connector["networks"]

            # Convert to string for display
            chain_type_str = chain
            networks_str = ", ".join(networks) if networks else "N/A"

            # Extract trading types and convert to string
            trading_types: List[str] = connector.get("trading_types", [])
            trading_types_str = ", ".join(trading_types) if trading_types else "N/A"

            # Create a new dictionary with the fields we want to display
            display_connector = {
                "connector": connector.get("name", ""),
                "chain_type": chain_type_str,  # Use string instead of list
                "networks": networks_str,      # Use string instead of list
                "trading_types": trading_types_str
            }

            connectors_tiers.append(display_connector)

        # Make sure to include all fields in the dataframe
        columns = ["connector", "chain_type", "networks", "trading_types"]
        connectors_df = pd.DataFrame(connectors_tiers, columns=columns)

        lines = ["    " + line for line in format_df_for_printout(
            connectors_df,
            table_format=self.client_config_map.tables_format).split("\n")]
        self.notify("\n".join(lines))

    async def _approve_tokens(self, spender: str, network: str, tokens: str):
        """
        Approve tokens for spending on a connector.
        """
        try:
            self.logger().info(
                f"Approving tokens {tokens} for {spender} on {network} network")

            # Get wallet for ethereum chain from gateway
            try:
                wallets_resp = await self._get_gateway_instance().get_wallets("ethereum")
                if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                    self.notify("No wallet found for ethereum. Please add one with 'gateway wallet add ethereum'")
                    return
                wallet_address = wallets_resp[0]["walletAddresses"][0]
            except Exception as e:
                self.notify(f"Error fetching wallet: {str(e)}")
                return

            # Approve each token separately
            token_list = [t.strip() for t in tokens.split(",")]
            for token in token_list:
                self.notify(f"Approving {token} for {spender}...")

                try:
                    resp = await self._get_gateway_instance().approve_token(network, wallet_address, token, spender)
                    transaction_hash = resp.get("approval", {}).get("hash")

                    if not transaction_hash:
                        self.notify(f"Failed to get transaction hash for {token} approval")
                        continue

                    # Monitor transaction status
                    displayed_pending = False
                    while True:
                        poll_resp = await self._get_gateway_instance().get_transaction_status("ethereum", network, transaction_hash)
                        transaction_status = poll_resp.get("txStatus")

                        if transaction_status == 1:  # Confirmed
                            self.notify(f"✓ Token {token} is approved for spending on {spender}")
                            break
                        elif transaction_status == 2:  # Pending
                            if not displayed_pending:
                                self.notify(f"Token {token} approval transaction pending. Hash: {transaction_hash}")
                                displayed_pending = True
                            await asyncio.sleep(2)
                        else:  # Failed or unknown
                            self.notify(f"✗ Token {token} approval failed. Please try manual approval.")
                            break

                except Exception as e:
                    self.notify(f"Error approving {token}: {str(e)}")
                    continue

        except Exception as e:
            self.notify(f"Error in approve tokens: {str(e)}")

    async def _wrap_tokens(self, network: str, amount: str):
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

            # Get ethereum wallet
            try:
                wallets_resp = await self._get_gateway_instance().get_wallets("ethereum")
                if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                    self.notify("No wallet found for ethereum. Please add one with 'gateway wallet add ethereum'")
                    return
                wallet_address = wallets_resp[0]["walletAddresses"][0]
            except Exception as e:
                self.notify(f"Error fetching wallet: {str(e)}")
                return

            # Get native token info
            native_token = await self._get_native_currency_symbol("ethereum", network)
            if not native_token:
                self.notify(f"Could not determine native token for {network}")
                return

            # Map native token to wrapped token
            wrapped_token_map = {
                "ETH": "WETH",
                "BNB": "WBNB",
                "AVAX": "WAVAX",
                "MATIC": "WMATIC"
            }

            wrapped_token = wrapped_token_map.get(native_token.upper())
            if not wrapped_token:
                self.notify(f"Wrapping not supported for {native_token}")
                return

            self.notify(f"\nWrapping {amount} {native_token} to {wrapped_token} on {network}...")
            self.notify(f"Wallet: {wallet_address}")

            # Call the wrap endpoint
            try:
                wrap_resp = await self._get_gateway_instance().api_request(
                    "post",
                    "chains/ethereum/wrap",
                    {
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

                # Monitor transaction
                self.notify("\nMonitoring transaction...")
                displayed_pending = False

                while True:
                    poll_resp = await self._get_gateway_instance().get_transaction_status("ethereum", network, tx_hash)
                    tx_status = poll_resp.get("txStatus")

                    if tx_status == 1:  # Confirmed
                        self.notify(f"\n✓ Successfully wrapped {amount} {native_token} to {wrapped_token}")
                        self.notify(f"Transaction confirmed in block {poll_resp.get('txBlock', 'unknown')}")
                        break
                    elif tx_status == 2:  # Pending
                        if not displayed_pending:
                            self.notify("Transaction pending...")
                            displayed_pending = True
                        await asyncio.sleep(2)
                    else:  # Failed or unknown
                        self.notify("\n✗ Transaction failed")
                        if poll_resp.get("txReceipt"):
                            self.notify(f"Receipt: {poll_resp.get('txReceipt')}")
                        break

            except Exception as e:
                self.notify(f"\nError executing wrap: {str(e)}")

        except Exception as e:
            self.notify(f"Error in wrap tokens: {str(e)}")

    async def _update_gateway_approve_tokens(
            self,           # type: HummingbotApplication
            connector_chain_network: str,
            tokens: str,
    ):
        """
        Allow the user to approve tokens for spending.
        """
        try:
            # Parse the connector_chain_network format
            parts = connector_chain_network.split("_")
            if len(parts) < 3:
                self.notify(f"Invalid format: {connector_chain_network}. Expected format: connector_chain_network")
                return

            # Get connector info
            connectors_resp = await self._get_gateway_instance().get_connectors()
            connectors = connectors_resp.get("connectors", [])

            # Find matching connector
            connector_info = None
            for conn in connectors:
                if connector_chain_network.startswith(conn["name"]):
                    connector_info = conn
                    break

            if not connector_info:
                self.notify(
                    f"'{connector_chain_network}' is not available. You can review available gateway connectors with the command 'gateway list'.")
                return

            chain = connector_info["chain"]
            connector = connector_info["name"]
            # Extract network from connector_chain_network
            network_part = connector_chain_network.split(f"{connector}_{chain}_")
            network = network_part[1] if len(network_part) > 1 else connector_info["networks"][0]

            self.logger().info(
                f"Connector {connector} Tokens {tokens} will now be approved for spending for '{connector_chain_network}'.")

            # Get wallet for the chain from gateway
            try:
                wallets_resp = await self._get_gateway_instance().get_wallets(chain)
                if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                    self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                    return
                wallet_address = wallets_resp[0]["walletAddresses"][0]
            except Exception as e:
                self.notify(f"Error fetching wallet: {str(e)}")
                return

            try:
                resp: Dict[str, Any] = await self._get_gateway_instance().approve_token(network, wallet_address, tokens, connector)
                transaction_hash: Optional[str] = resp.get("signature")
                if not transaction_hash:
                    self.logger().error(f"No transaction hash returned from approval request. Response: {resp}")
                    self.notify("Error: No transaction hash returned from approval request.")
                    return
                displayed_pending: bool = False
                while True:
                    pollResp: Dict[str, Any] = await self._get_gateway_instance().get_transaction_status("ethereum", network, transaction_hash)
                    transaction_status: Optional[str] = pollResp.get(
                        "txStatus")
                    if transaction_status == 1:
                        self.logger().info(
                            f"Token {tokens} is approved for spending for '{connector}' for Wallet: {wallet_address}.")
                        self.notify(
                            f"Token {tokens} is approved for spending for '{connector}' for Wallet: {wallet_address}.")
                        break
                    elif transaction_status == 2:
                        if not displayed_pending:
                            self.logger().info(
                                f"Token {tokens} approval transaction is pending. Transaction hash: {transaction_hash}")
                            displayed_pending = True
                            await asyncio.sleep(2)
                        continue
                    else:
                        self.logger().info(
                            f"Tokens {tokens} is not approved for spending. Please use manual approval.")
                        self.notify(
                            f"Tokens {tokens} is not approved for spending. Please use manual approval.")
                        break

            except Exception as e:
                self.logger().error(f"Error approving tokens: {e}")
                return
        except Exception as e:
            self.notify(f"Error processing approve tokens request: {str(e)}")

    def _get_gateway_instance(
        self  # type: HummingbotApplication
    ) -> GatewayClient:
        # Pass the client config map to GatewayClient
        return GatewayClient.get_instance(self.client_config_map)

    async def _get_allowances(self, spender: Optional[str] = None, network: Optional[str] = None,
                              address: Optional[str] = None, tokens: Optional[str] = None):
        """Get token allowances for Ethereum-based connectors"""
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Checking token allowances, please wait...")
        try:
            # Validate parameters
            if not all([spender, network]):
                self.notify("\nPlease specify both spender and network.")
                self.notify("Usage: gateway allowance <spender> <network> [address] [tokens]")
                self.notify("Example: gateway allowance uniswap/amm mainnet")
                return

            # Get ethereum wallet
            wallets_resp = await self._get_gateway_instance().get_wallets("ethereum")
            if not wallets_resp:
                self.notify("No wallet found for ethereum. Please add one with 'gateway wallet add ethereum'")
                return

            # Get all addresses and track their types
            all_addresses = []
            address_types = {}  # Track whether addresses are regular, read-only, or hardware
            for wallet in wallets_resp:
                if wallet.get("chain", "").lower() == "ethereum":
                    regular_addresses = wallet.get("walletAddresses", [])
                    readonly_addresses = wallet.get("readOnlyWalletAddresses", [])
                    hardware_addresses = wallet.get("hardwareWalletAddresses", [])

                    # Add addresses and track their types
                    for addr in regular_addresses:
                        all_addresses.append(addr)
                        address_types[addr] = "regular"
                    for addr in readonly_addresses:
                        all_addresses.append(addr)
                        address_types[addr] = "read-only"
                    for addr in hardware_addresses:
                        all_addresses.append(addr)
                        address_types[addr] = "hardware"

            if not all_addresses:
                self.notify("No wallet addresses found for ethereum. Please add one with 'gateway wallet add ethereum'")
                return

            # Use specified address or all addresses
            if address:
                addresses_to_check = [address]
            else:
                addresses_to_check = all_addresses

            # Determine tokens to check
            if tokens:
                # User specified tokens
                tokens_to_check = [token.strip() for token in tokens.split(",")]
            else:
                # No tokens specified - fetch all tokens from gateway
                self.notify("Fetching all token allowances...")
                try:
                    all_tokens_resp = await self._get_gateway_instance().get_tokens("ethereum", network)
                    all_tokens = all_tokens_resp.get("tokens", [])
                    # Filter out native token for allowances
                    native_token = await self._get_native_currency_symbol("ethereum", network)
                    tokens_to_check = []
                    for token_info in all_tokens:
                        symbol = token_info.get("symbol", "")
                        if symbol and native_token and symbol.upper() != native_token.upper():
                            tokens_to_check.append(symbol)
                        elif symbol and not native_token:
                            # If we can't determine native token, include all tokens
                            tokens_to_check.append(symbol)
                except Exception as e:
                    self.notify(f"Warning: Could not fetch tokens: {str(e)}")
                    tokens_to_check = []

            if not tokens_to_check:
                self.notify("No tokens to check allowances for.")
                return

            # Check allowances for each address
            for wallet_address in addresses_to_check:
                try:
                    # Get allowances from gateway
                    allowances_resp = await asyncio.wait_for(
                        self._get_gateway_instance().get_allowances(
                            network, wallet_address, spender, tokens_to_check
                        ),
                        network_timeout
                    )

                    allowances = allowances_resp.get("approvals", {}) if allowances_resp else {}

                    # Display results
                    self.notify(f"\nNetwork: {network}")
                    # Display wallet address with type
                    wallet_type = address_types.get(wallet_address, "regular")
                    if wallet_type == "hardware":
                        self.notify(f"Wallet: {wallet_address} (hardware)")
                    elif wallet_type == "read-only":
                        self.notify(f"Wallet: {wallet_address} (read-only)")
                    else:
                        self.notify(f"Wallet: {wallet_address}")
                    self.notify(f"Spender: {spender}")

                    if allowances:
                        rows = []
                        for token, allowance in allowances.items():
                            allowance_val = float(allowance) if allowance else 0
                            allowance_threshold = 999999  # Threshold for displaying large allowances
                            display_allowance = (
                                PerformanceMetrics.smart_round(Decimal(str(allowance)), 4)
                                if allowance_val < allowance_threshold else f"{allowance_threshold}+"
                            )
                            rows.append({
                                "Token": token.upper(),
                                "Allowance": display_allowance,
                                "Status": "✓ Approved" if allowance_val > 0 else "✗ Not Approved"
                            })

                        if rows:
                            df = pd.DataFrame(data=rows, columns=["Token", "Allowance", "Status"])
                            df.sort_values(by=["Token"], inplace=True)

                            lines = [
                                "    " + line for line in df.to_string(index=False).split("\n")
                            ]
                            self.notify("\n".join(lines))
                        else:
                            self.notify("    No token allowances found")
                    else:
                        self.notify("    No token allowances found")

                except asyncio.TimeoutError:
                    self.notify(f"\nTimeout checking allowances for {spender} on {network}")
                except Exception as e:
                    self.notify(f"\nError checking allowances: {str(e)}")

        except Exception as e:
            self.notify(f"Error: {str(e)}")

    async def _get_default_network_for_chain(self, chain: str) -> Optional[str]:
        """Get the default network for a given chain."""
        # Define sensible defaults for main chains
        # These defaults are used by both gateway ping and gateway balance commands
        # to ensure consistency across the application
        default_networks = {
            "ethereum": "mainnet",
            "solana": "mainnet-beta"
        }

        # Check if we have a predefined default for this chain
        chain_lower = chain.lower()
        if chain_lower in default_networks:
            return default_networks[chain_lower]

        # Fallback to getting the first network from gateway
        try:
            # Get chains from gateway
            chains_resp = await self._get_gateway_instance().get_chains()
            if chains_resp:
                # Find the chain info
                chain_info = next((c for c in chains_resp if c["chain"] == chain), None)
                if chain_info:
                    networks = chain_info.get("networks", [])
                    if networks:
                        # Return the first network
                        return networks[0]
        except Exception:
            pass
        return None
