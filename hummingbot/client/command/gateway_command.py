#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.connector.gateway.gateway_paths import get_gateway_paths
from hummingbot.connector.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_dict_display, search_configs
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


class GatewayCommand(GatewayChainApiManager):
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
    def gateway_allowance(self, network: Optional[str] = None, connector: Optional[str] = None,
                          tokens: Optional[str] = None):
        """
        Command to check token allowances for Ethereum-based connectors
        Usage: gateway allowance [network] [connector] [tokens]
        """
        safe_ensure_future(self._get_allowances(network, connector, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_approve(self, network: Optional[str] = None, connector: Optional[str] = None,
                        tokens: Optional[str] = None):
        """
        Command to approve tokens for spending on a connector
        Usage: gateway approve [network] [connector] [tokens]
        """
        if all([network, connector, tokens]):
            safe_ensure_future(self._approve_tokens(network, connector, tokens), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify all required parameters: network, connector, and tokens.\n"
                "Usage: gateway approve <network> <connector> <tokens>\n"
                "Example: gateway approve mainnet uniswap USDC,USDT\n")

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_ping(self):
        safe_ensure_future(self._gateway_ping(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_list(self):
        safe_ensure_future(self._gateway_list(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_config(self,
                       key: Optional[str] = None,
                       value: str = None):
        if value:
            safe_ensure_future(self._update_gateway_configuration(
                key, value), loop=self.ev_loop)
        else:
            safe_ensure_future(
                self._show_gateway_configuration(key), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_wallet(self, action: str = None, chain: str = None, address: str = None):
        """
        Manage wallets in gateway.
        Usage:
            gateway wallet list [chain]     - List all wallets or filter by chain
            gateway wallet add <chain>      - Add a new wallet for a chain
            gateway wallet remove <chain> <address> - Remove a wallet
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway wallet list [chain]     - List all wallets or filter by chain")
            self.notify("  gateway wallet add <chain>      - Add a new wallet for a chain")
            self.notify("  gateway wallet remove <chain> <address> - Remove a wallet")
            return

        if action == "list":
            safe_ensure_future(self._gateway_wallet_list(chain), loop=self.ev_loop)
        elif action == "add":
            if chain is None:
                self.notify("Error: chain parameter is required for 'add' action")
                return
            safe_ensure_future(self._gateway_wallet_add(chain), loop=self.ev_loop)
        elif action == "remove":
            if chain is None or address is None:
                self.notify("Error: both chain and address parameters are required for 'remove' action")
                return
            safe_ensure_future(self._gateway_wallet_remove(chain, address), loop=self.ev_loop)
        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'add', or 'remove'.")

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

    async def _gateway_ping(self):
        """Test gateway connectivity and check default network latency for each chain (Ethereum and Solana)."""
        try:
            # First check if gateway is running
            gateway_status = await self._get_gateway_instance().ping_gateway()
            if not gateway_status:
                self.notify("\nUnable to connect to gateway.")
                return

            self.notify("\nGateway Status: Online")

            # Get all chains from gateway
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

                # Use the first network as default
                default_network = networks[0]

                self.notify(f"\nChain: {chain_name}")
                self.notify(f"Default Network: {default_network}")

                # Get node URL from config
                try:
                    # Get config for this chain/network
                    config_params = {
                        "chainOrConnector": chain_name,
                        "network": default_network
                    }
                    config_resp = await self._get_gateway_instance().api_request(
                        "get", "config", params=config_params, fail_silently=True
                    )

                    # Extract node URL based on chain type
                    node_url = None
                    if chain_name.lower() == "ethereum":
                        node_url = config_resp.get("rpcUrl")
                    elif chain_name.lower() == "solana":
                        node_url = config_resp.get("rpcUrl")

                    if node_url:
                        self.notify(f"Node URL: {node_url}")
                except Exception:
                    # If we can't get node URL, continue without it
                    pass

                # Ping the network by making a simple request
                start_time = time.time()
                try:
                    # Try to get native currency info as a ping test
                    native_currency = await self._get_native_currency_symbol(chain_name, default_network)

                    # Calculate latency
                    latency = (time.time() - start_time) * 1000  # Convert to milliseconds

                    if native_currency:
                        self.notify("Status: Connected")
                        self.notify(f"Native Token: {native_currency}")
                        self.notify(f"Latency: {latency:.1f} ms")
                    else:
                        self.notify("Status: Connected (no native token info)")
                        self.notify(f"Latency: {latency:.1f} ms")

                except asyncio.TimeoutError:
                    self.notify("Status: Timeout")
                except Exception as e:
                    self.notify(f"Status: Error - {str(e)}")

        except Exception as e:
            self.notify(f"\nError pinging gateway: {str(e)}")

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

    async def _update_gateway_configuration(self, key: str, value: Any):
        try:
            response = await self._get_gateway_instance().update_config(key, value)
            self.notify(response["message"])
        except Exception:
            self.notify(
                "\nError: Gateway configuration update failed. See log file for more details.")

    async def _show_gateway_configuration(
        self,  # type: HummingbotApplication
        key: Optional[str] = None,
    ):
        host = self.client_config_map.gateway.gateway_api_host
        port = self.client_config_map.gateway.gateway_api_port
        try:
            config_dict: Dict[str, Any] = await self._gateway_monitor._fetch_gateway_configs()
            if key is not None:
                config_dict = search_configs(config_dict, key)
            self.notify(f"\nGateway Configurations ({host}:{port}):")
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

        except asyncio.CancelledError:
            raise
        except Exception:
            remote_host = ':'.join([host, port])
            self.notify(f"\nError: Connection to Gateway {remote_host} failed")

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

            # Build list of chain/network combinations with their default addresses
            chain_network_combos = []
            for wallet_info in all_wallets:
                chain = wallet_info.get("chain", "")
                addresses = wallet_info.get("walletAddresses", [])

                if not addresses:
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
                    matching_addresses = [addr for addr in addresses if addr.lower() == address_filter.lower()]
                    if not matching_addresses:
                        continue
                    use_addresses = matching_addresses
                else:
                    use_addresses = addresses[:1]  # Just use first (default) address

                for address in use_addresses:
                    chain_network_combos.append((chain, default_network, address))

            if not chain_network_combos:
                self.notify("No matching wallets found for the specified filters.")
                return

            # Process each chain/network/address combination
            for chain, network, address in chain_network_combos:
                try:
                    # Determine tokens to check
                    if tokens_filter:
                        if tokens_filter.lower() == "all":
                            # User wants all tokens - pass empty list to get all balances
                            self.notify("Fetching all available token balances (this may take a while)...")
                            tokens_to_check = []
                        else:
                            # User specified tokens (comma-separated)
                            tokens_to_check = [token.strip() for token in tokens_filter.split(",")]
                    else:
                        # For performance, only check native token and a few common tokens
                        native_token = await self._get_native_currency_symbol(chain, network)
                        if native_token:
                            # Only check native token and top stablecoins by default
                            common_tokens = ["USDC", "USDT", "DAI", "WETH"]
                            tokens_to_check = [native_token]

                            # Add common tokens that aren't the native token
                            for token in common_tokens:
                                if token.upper() != native_token.upper() and token not in tokens_to_check:
                                    tokens_to_check.append(token)
                        else:
                            # Fallback to just common tokens
                            tokens_to_check = ["ETH", "USDC", "USDT", "DAI", "WETH"]

                        self.notify(f"Checking common tokens: {', '.join(tokens_to_check)}")
                        self.notify("(Use 'gateway balance ethereum base all' to check all available tokens)")

                    # Skip if user specified tokens but the list is empty (after filtering out empty strings)
                    if tokens_filter and tokens_filter.lower() != "all" and not tokens_to_check:
                        self.notify(f"\nNo valid tokens specified for {chain}:{network}")
                        continue

                    # Get balances from gateway
                    try:
                        self.notify(f"Fetching balances for {chain}:{network} address {address[:8]}... tokens: {tokens_to_check}")
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

                    # Filter out zero balances unless user specified specific tokens or we're showing native token
                    if tokens_filter and tokens_filter.lower() != "all":
                        # Show all requested tokens even if zero
                        display_balances = balances
                    else:
                        # For default tokens or "all" mode, show non-zero balances and always show native token
                        display_balances = {}
                        native_token = await self._get_native_currency_symbol(chain, network)

                        for token, bal in balances.items():
                            balance_val = float(bal) if bal else 0
                            # Always include native token (even if zero), include others only if non-zero
                            if (native_token and token.upper() == native_token.upper()) or balance_val > 0:
                                display_balances[token] = bal

                        # If using "all" mode, show a summary
                        if tokens_filter and tokens_filter.lower() == "all":
                            total_tokens = len(balances)
                            shown_tokens = len(display_balances)
                            if shown_tokens < total_tokens:
                                self.notify(f"Showing {shown_tokens} tokens with balances out of {total_tokens} total tokens")

                    # Display results
                    self.notify(f"\nChain: {chain.lower()}")
                    self.notify(f"Network: {network}")
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
            # Try to get from gateway configuration first
            config = await self._get_gateway_instance().get_configuration(chain)
            if config and "networks" in config and network in config["networks"]:
                network_config = config["networks"][network]
                if "nativeCurrency" in network_config:
                    return network_config["nativeCurrency"].get("symbol")

            # Fallback to common native tokens by chain
            native_token_map = {
                "ethereum": "ETH",
                "polygon": "MATIC",
                "avalanche": "AVAX",
                "bsc": "BNB",
                "arbitrum": "ETH",
                "optimism": "ETH",
                "base": "ETH",
                "solana": "SOL",
                "celo": "CELO"
            }
            return native_token_map.get(chain.lower())
        except Exception:
            return None

    async def _gateway_list(
        self           # type: HummingbotApplication
    ):
        connector_list: List[Dict[str, Any]] = await self._get_gateway_instance().get_connectors()
        connectors_tiers: List[Dict[str, Any]] = []

        for connector in connector_list["connectors"]:
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

    async def _approve_tokens(self, network: str, connector: str, tokens: str):
        """
        Approve tokens for spending on a connector.
        """
        try:
            self.logger().info(
                f"Approving tokens {tokens} for {connector} on {network} network")

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
                self.notify(f"Approving {token} for {connector}...")

                try:
                    resp = await self._get_gateway_instance().approve_token(network, wallet_address, token, connector)
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
                            self.notify(f"✓ Token {token} is approved for spending on {connector}")
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
                transaction_hash: Optional[str] = resp.get(
                    "approval", {}).get("hash")
                displayed_pending: bool = False
                while True:
                    pollResp: Dict[str, Any] = await self._get_gateway_instance().get_transaction_status(chain, network, transaction_hash)
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
    ) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(
            self.client_config_map)
        return gateway_instance

    async def _get_allowances(self, network: Optional[str] = None, connector: Optional[str] = None,
                              tokens: Optional[str] = None):
        """Get token allowances for Ethereum-based connectors"""
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Checking token allowances, please wait...")
        try:
            # Validate parameters
            if not all([network, connector]):
                self.notify("\nPlease specify both network and connector.")
                self.notify("Usage: gateway allowance <network> <connector> [tokens]")
                self.notify("Example: gateway allowance mainnet uniswap")
                return

            # Get ethereum wallet
            wallets_resp = await self._get_gateway_instance().get_wallets("ethereum")
            if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                self.notify("No wallet found for ethereum. Please add one with 'gateway wallet add ethereum'")
                return

            wallet_address = wallets_resp[0]["walletAddresses"][0]

            # Determine tokens to check
            if tokens:
                if tokens.lower() == "all":
                    # User wants all tokens - fetch from gateway
                    self.notify("Fetching all available token allowances (this may take a while)...")
                    try:
                        all_tokens = await self._get_gateway_instance().get_tokens("ethereum", network)
                        # Filter out native token for allowances
                        native_token = await self._get_native_currency_symbol("ethereum", network)
                        tokens_to_check = []
                        for token_info in all_tokens:
                            symbol = token_info.get("symbol", "")
                            if symbol and symbol.upper() != native_token.upper():
                                tokens_to_check.append(symbol)
                    except Exception as e:
                        self.notify(f"Warning: Could not fetch tokens: {str(e)}")
                        tokens_to_check = []
                else:
                    # User specified tokens
                    tokens_to_check = [token.strip() for token in tokens.split(",")]
            else:
                # Default: check common tokens
                native_token = await self._get_native_currency_symbol("ethereum", network)
                common_tokens = ["USDC", "USDT", "DAI", "WETH"]
                tokens_to_check = [token for token in common_tokens if token.upper() != native_token.upper()]
                self.notify(f"Checking common tokens: {', '.join(tokens_to_check)}")
                self.notify("(Use 'gateway allowance <network> <connector> all' to check all available tokens)")

            if not tokens_to_check:
                self.notify("No tokens to check allowances for.")
                return

            try:
                # Get allowances from gateway
                allowances_resp = await asyncio.wait_for(
                    self._get_gateway_instance().get_allowances(
                        "ethereum", network, wallet_address, tokens_to_check, connector, fail_silently=True
                    ),
                    network_timeout
                )

                allowances = allowances_resp.get("approvals", {}) if allowances_resp else {}

                # Display results
                self.notify(f"\nNetwork: {network}")
                self.notify(f"Wallet: {wallet_address}")
                self.notify(f"Connector: {connector}")

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
                self.notify(f"\nTimeout checking allowances for {connector} on {network}")
            except Exception as e:
                self.notify(f"\nError checking allowances: {str(e)}")

        except Exception as e:
            self.notify(f"Error: {str(e)}")

    async def _gateway_wallet_list(self, chain: Optional[str] = None):
        """List wallets from gateway, optionally filtered by chain."""
        try:
            wallets = await self._get_gateway_instance().get_wallets(chain)

            if not wallets:
                if chain:
                    self.notify(f"No wallets found for chain '{chain}'")
                else:
                    self.notify("No wallets found in gateway")
                return

            # Show header with information about defaults
            self.notify("\nGateway Wallets (first wallet is default for each chain):")

            # Display wallets grouped by chain
            for wallet_info in wallets:
                chain_name = wallet_info.get("chain", "unknown")
                addresses = wallet_info.get("walletAddresses", [])

                self.notify(f"\nChain: {chain_name.lower()}")
                if not addresses:
                    self.notify("  No wallets")
                else:
                    # Get native token for balance display
                    try:
                        # Get default network for this chain (first available network)
                        default_network = await self._get_default_network_for_chain(chain_name)
                        if default_network:
                            native_token = await self._get_native_currency_symbol(chain_name, default_network)
                            # Get balance for each wallet
                            for i, address in enumerate(addresses):
                                try:
                                    balance_resp = await self._get_gateway_instance().get_balances(
                                        chain_name, default_network, address, [native_token]
                                    )
                                    balance = balance_resp.get("balances", {}).get(native_token, "0")
                                    # Mark first wallet as default
                                    default_indicator = " (default)" if i == 0 else ""
                                    self.notify(f"  {address} - Balance: {balance} {native_token}{default_indicator}")
                                except Exception:
                                    # Mark first wallet as default even if balance fetch fails
                                    default_indicator = " (default)" if i == 0 else ""
                                    self.notify(f"  {address}{default_indicator}")
                        else:
                            # If we can't get default network, just show addresses
                            for i, address in enumerate(addresses):
                                default_indicator = " (default)" if i == 0 else ""
                                self.notify(f"  {address}{default_indicator}")
                    except Exception:
                        # If we can't get balances, just show addresses
                        for i, address in enumerate(addresses):
                            default_indicator = " (default)" if i == 0 else ""
                            self.notify(f"  {address}{default_indicator}")

        except Exception as e:
            self.notify(f"Error fetching wallets: {str(e)}")

    async def _gateway_wallet_add(self, chain: str):
        """Add a new wallet to gateway."""
        with begin_placeholder_mode(self):
            try:
                # Prompt for private key
                private_key = await self.app.prompt(
                    prompt=f"Enter the private key for your {chain} wallet >>> ",
                    is_password=True
                )

                if self.app.to_stop_config:
                    return

                if not private_key:
                    self.notify("Error: Private key cannot be empty")
                    return

                # Add wallet to gateway
                self.notify(f"Adding wallet to {chain}...")
                response = await self._get_gateway_instance().add_wallet(chain, private_key)

                wallet_address = response.get("address")
                if wallet_address:
                    self.notify(f"Successfully added wallet: {wallet_address}")

                    # Show balance
                    try:
                        default_network = await self._get_default_network_for_chain(chain)
                        if default_network:
                            native_token = await self._get_native_currency_symbol(chain, default_network)
                            balance_resp = await self._get_gateway_instance().get_balances(
                                chain, default_network, wallet_address, [native_token]
                            )
                            balance = balance_resp.get("balances", {}).get(native_token, "0")
                            self.notify(f"Balance: {balance} {native_token}")
                    except Exception:
                        pass
                else:
                    self.notify("Error: Failed to add wallet")

            except Exception as e:
                self.notify(f"Error adding wallet: {str(e)}")

    async def _gateway_wallet_remove(self, chain: str, address: str):
        """Remove a wallet from gateway."""
        try:
            # Confirm removal
            with begin_placeholder_mode(self):
                confirm = await self.app.prompt(
                    prompt=f"Are you sure you want to remove wallet {address} from {chain}? (Yes/No) >>> "
                )

                if self.app.to_stop_config:
                    return

                if confirm.lower() not in ["y", "yes"]:
                    self.notify("Wallet removal cancelled")
                    return

            # Remove wallet
            self.notify(f"Removing wallet {address} from {chain}...")
            await self._get_gateway_instance().remove_wallet(chain, address)
            self.notify(f"Successfully removed wallet: {address}")

        except Exception as e:
            self.notify(f"Error removing wallet: {str(e)}")

    async def _get_default_network_for_chain(self, chain: str) -> Optional[str]:
        """Get the default (first) network for a given chain."""
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
