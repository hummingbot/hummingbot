#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import get_connector_class  # noqa: F401
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings, gateway_connector_trading_pairs  # noqa: F401
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.gateway import get_gateway_paths
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
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
        super().__init__(client_config_map)
        self.client_config_map = client_config_map

    def gateway(self):
        """Show gateway help when no subcommand is provided."""
        self.notify("""
Gateway Commands:
  gateway allowance <connector> [tokens]                    - Check token allowances
  gateway approve <connector> <tokens>                      - Approve tokens for spending
  gateway balance [chain] [tokens]                          - Check token balances
  gateway config [namespace]                                - Show configuration
  gateway config <namespace> update                         - Update configuration (interactive)
  gateway config <namespace> update <path> <value>          - Update configuration (direct)
  gateway connect <chain>                                   - View and add wallets for a chain
  gateway generate-certs                                    - Generate SSL certificates
  gateway list                                              - List available connectors
  gateway lp <connector> <action>                           - Manage liquidity positions
  gateway ping [chain]                                      - Test node and chain/network status
  gateway pool <connector> <pair>                           - View pool information
  gateway pool <connector> <pair> update                    - Add/update pool information (interactive)
  gateway pool <connector> <pair> update <address>          - Add/update pool information (direct)
  gateway swap <connector> [pair] [side] [amount]           - Swap tokens
  gateway token <symbol_or_address>                         - View token information
  gateway token <symbol> update                             - Update token information

Use 'gateway <command> --help' for more information about a command.""")

    @ensure_gateway_online
    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_balance(self, chain: Optional[str] = None, tokens: Optional[str] = None):
        safe_ensure_future(self._get_balances(chain, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_allowance(self, connector: Optional[str] = None):
        """
        Command to check token allowances for Ethereum-based connectors
        Usage: gateway allowance [connector]
        """
        safe_ensure_future(self._get_allowances(connector), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_approve(self, connector: Optional[str], tokens: Optional[str]):
        # Delegate to GatewayApproveCommand
        from hummingbot.client.command.gateway_approve_command import GatewayApproveCommand
        GatewayApproveCommand.gateway_approve(self, connector, tokens)

    @ensure_gateway_online
    def gateway_connect(self, chain: Optional[str]):
        """
        View and add wallets for a chain.
        Usage: gateway connect <chain>
        """
        if not chain:
            self.notify("\nError: Chain is required")
            self.notify("Usage: gateway connect <chain>")
            self.notify("Example: gateway connect ethereum")
            return

        safe_ensure_future(self._gateway_connect(chain), loop=self.ev_loop)

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_ping(self, chain: str = None):
        safe_ensure_future(self._gateway_ping(chain), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_token(self, symbol_or_address: Optional[str], action: Optional[str]):
        # Delegate to GatewayTokenCommand
        from hummingbot.client.command.gateway_token_command import GatewayTokenCommand
        GatewayTokenCommand.gateway_token(self, symbol_or_address, action)

    @ensure_gateway_online
    def gateway_pool(self, connector: Optional[str], trading_pair: Optional[str], action: Optional[str], args: List[str] = None):
        # Delegate to GatewayPoolCommand
        from hummingbot.client.command.gateway_pool_command import GatewayPoolCommand
        GatewayPoolCommand.gateway_pool(self, connector, trading_pair, action, args)

    @ensure_gateway_online
    def gateway_list(self):
        safe_ensure_future(self._gateway_list(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_config(self, namespace: str = None, action: str = None, args: List[str] = None):
        # Delegate to GatewayConfigCommand
        from hummingbot.client.command.gateway_config_command import GatewayConfigCommand
        GatewayConfigCommand.gateway_config(self, namespace, action, args)

    async def _gateway_ping(self, chain: str = None):
        """Test gateway connectivity and network status"""
        gateway = self._get_gateway_instance()

        # First test basic gateway connectivity
        if not await gateway.ping_gateway():
            self.notify("\nUnable to ping gateway - gateway service is offline.")
            return

        self.notify("\nGateway service is online.")

        # Get available chains if no specific chain is provided
        if chain is None:
            try:
                chains_resp = await gateway.get_chains()
                if not chains_resp or "chains" not in chains_resp:
                    self.notify("No chains available on gateway.")
                    return

                chains_data = chains_resp["chains"]
                self.notify(f"\nTesting network status for {len(chains_data)} chains...\n")

                # Test each chain with its default network
                for chain_info in chains_data:
                    chain_name = chain_info.get("chain")
                    # Get default network for this chain
                    default_network = await gateway.get_default_network_for_chain(chain_name)
                    if default_network:
                        await self._test_network_status(chain_name, default_network)
                    else:
                        self.notify(f"{chain_name}: No default network configured\n")
            except Exception as e:
                self.notify(f"Error getting chains: {str(e)}")
        else:
            # Test specific chain with its default network
            try:
                # Get default network for the specified chain
                default_network = await gateway.get_default_network_for_chain(chain)
                if default_network:
                    await self._test_network_status(chain, default_network)
                else:
                    self.notify(f"No default network configured for chain: {chain}")
            except Exception as e:
                self.notify(f"Error testing chain {chain}: {str(e)}")

    async def _test_network_status(self, chain: str, network: str):
        """Test network status for a specific chain/network combination"""
        try:
            gateway = self._get_gateway_instance()
            status = await gateway.get_network_status(chain=chain, network=network)

            if status:
                self.notify(f"{chain} ({network}):")
                self.notify(f"  - RPC URL: {status.get('rpcUrl', 'N/A')}")
                self.notify(f"  - Current Block: {status.get('currentBlockNumber', 'N/A')}")
                self.notify(f"  - Native Currency: {status.get('nativeCurrency', 'N/A')}")
                self.notify("  - Status: ✓ Connected\n")
            else:
                self.notify(f"{chain} ({network}): ✗ Unable to get network status\n")
        except Exception as e:
            self.notify(f"{chain} ({network}): ✗ Error - {str(e)}\n")

    async def _gateway_connect(
        self,  # type: HummingbotApplication
        chain: str
    ):
        """View and add wallets for a chain."""
        try:
            # Get default network for the chain
            default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
            if not default_network:
                self.notify(f"\nError: Could not determine default network for chain '{chain}'")
                self.notify("Please check that the chain name is correct.")
                return

            self.notify(f"\n=== {chain} wallets ===")
            self.notify(f"Network: {default_network}")

            # Get existing wallets to show
            wallets_response = await self._get_gateway_instance().get_wallets(show_hardware=True)

            # Find wallets for this chain
            chain_wallets = None
            for wallet_info in wallets_response:
                if wallet_info.get("chain") == chain:
                    chain_wallets = wallet_info
                    break

            if chain_wallets:
                # Get current default wallet
                default_wallet = await self._get_gateway_instance().get_default_wallet_for_chain(chain)

                # Display existing wallets
                self.notify("\nExisting wallets:")

                # Regular wallets
                wallet_addresses = chain_wallets.get("walletAddresses", [])
                for address in wallet_addresses:
                    if address == default_wallet:
                        self.notify(f"  • {address} (default)")
                    else:
                        self.notify(f"  • {address}")

                    # Check for placeholder wallet
                    if GatewayCommandUtils.is_placeholder_wallet(address):
                        self.notify("    ⚠️  This is a placeholder wallet - please replace it")

                # Hardware wallets
                hardware_addresses = chain_wallets.get("hardwareWalletAddresses", [])
                for address in hardware_addresses:
                    if address == default_wallet:
                        self.notify(f"  • {address} (hardware, default)")
                    else:
                        self.notify(f"  • {address} (hardware)")
            else:
                self.notify("\nNo existing wallets found for this chain.")

            # Enter interactive mode
            with begin_placeholder_mode(self):
                # Ask for wallet type
                wallet_type = await self.app.prompt(
                    prompt="Select Option (1) Add Regular Wallet, (2) Add Hardware Wallet, (3) Exit [default: 3]: "
                )

                if self.app.to_stop_config:
                    self.notify("No wallet added.")
                    return

                # Default to exit if empty input
                if not wallet_type or wallet_type == "3":
                    self.notify("No wallet added.")
                    return

                # Check for valid wallet type
                if wallet_type not in ["1", "2"]:
                    self.notify("Invalid option. No wallet added.")
                    return

                is_hardware = wallet_type == "2"
                wallet_type_str = "hardware" if is_hardware else "regular"

                # For hardware wallets, we need the address instead of private key
                if is_hardware:
                    wallet_input = await self.app.prompt(
                        prompt=f"Enter your {chain} wallet address: "
                    )
                else:
                    wallet_input = await self.app.prompt(
                        prompt=f"Enter your {chain} wallet private key: ",
                        is_password=True
                    )

                if self.app.to_stop_config or not wallet_input:
                    self.notify("Wallet addition cancelled")
                    return

                # Add wallet based on type
                self.notify(f"\nAdding {wallet_type_str} wallet...")

                if is_hardware:
                    # For hardware wallets, pass the address parameter
                    response = await self._get_gateway_instance().add_hardware_wallet(
                        chain=chain,
                        address=wallet_input,  # Hardware wallets use address parameter
                        set_default=True
                    )
                else:
                    # For regular wallets, pass the private key
                    response = await self._get_gateway_instance().add_wallet(
                        chain=chain,
                        private_key=wallet_input,
                        set_default=True
                    )

                # Check response
                if response and "address" in response:
                    self.notify(f"\n✓ Successfully added {wallet_type_str} wallet!")
                    self.notify(f"Address: {response['address']}")
                    self.notify(f"Set as default wallet for {chain}")
                else:
                    error_msg = response.get("error", "Unknown error") if response else "No response"
                    self.notify(f"\n✗ Failed to add wallet: {error_msg}")

        except Exception as e:
            self.notify(f"\nError adding wallet: {str(e)}")
            self.logger().error(f"Error in gateway connect: {e}", exc_info=True)

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

    async def _prompt_for_wallet_address(
        self,           # type: HummingbotApplication
        chain: str,
        network: str,
    ) -> Tuple[Optional[str], Dict[str, str]]:
        self.app.clear_input()
        self.placeholder_mode = True
        wallet_private_key = await self.app.prompt(
            prompt=f"Enter your {chain}-{network} wallet private key >>> ",
            is_password=True
        )
        self.app.clear_input()
        if self.app.to_stop_config:
            return

        response: Dict[str, Any] = await self._get_gateway_instance().add_wallet(
            chain, network, wallet_private_key
        )
        wallet_address: str = response["address"]
        return wallet_address

    async def _get_balances(self, chain_filter: Optional[str] = None, tokens_filter: Optional[str] = None):
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Updating gateway balances, please wait...")

        # Determine which chains to check
        chains_to_check = []
        if chain_filter:
            # Check specific chain
            chains_to_check = [chain_filter]
        else:
            # Get all available chains from the Chain enum
            from hummingbot.connector.gateway.common_types import Chain
            chains_to_check = [chain.chain for chain in Chain]

        # Process each chain
        for chain in chains_to_check:
            # Get default network for this chain
            default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
            if not default_network:
                self.notify(f"Could not determine default network for {chain}")
                continue

            # Get default wallet for this chain
            default_wallet = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not default_wallet:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway connect {chain}'")
                continue

            # Check if wallet address is a placeholder
            if GatewayCommandUtils.is_placeholder_wallet(default_wallet):
                self.notify(f"\n⚠️  {chain} wallet not configured (found placeholder: {default_wallet})")
                self.notify(f"Please add a real wallet with: gateway connect {chain}")
                continue

            try:
                # Determine tokens to check
                if tokens_filter:
                    # User specified tokens (comma-separated)
                    tokens_to_check = [token.strip() for token in tokens_filter.split(",")]

                    # Validate tokens
                    valid_tokens, invalid_tokens = await self._get_gateway_instance().validate_tokens(
                        chain, default_network, tokens_to_check
                    )

                    if invalid_tokens:
                        self.notify(f"\n❌ Unknown tokens for {chain}: {', '.join(invalid_tokens)}")
                        self.notify("Please check the token symbol(s) and try again.")
                        continue

                    # Use validated tokens
                    tokens_to_check = valid_tokens
                else:
                    # No filter specified - fetch all tokens
                    tokens_to_check = []

                # Get balances from gateway
                tokens_display = "all" if not tokens_to_check else ", ".join(tokens_to_check)
                self.notify(f"\nFetching balances for {chain}:{default_network} for tokens: {tokens_display}")
                balances_resp = await asyncio.wait_for(
                    self._get_gateway_instance().get_balances(chain, default_network, default_wallet, tokens_to_check),
                    network_timeout
                )
                balances = balances_resp.get("balances", {})

                # Show all balances including zero balances
                display_balances = balances

                # Display results
                self.notify(f"\nChain: {chain.lower()}")
                self.notify(f"Network: {default_network}")
                self.notify(f"Address: {default_wallet}")

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

            except asyncio.TimeoutError:
                self.notify(f"\nError getting balance for {chain}:{default_network}: Request timed out")

    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            await market._update_balances()
        except Exception as e:
            logging.getLogger().debug(
                f"Failed to update balances for {market}", exc_info=True)
            return str(e)
        return None

    def all_balance(self, exchange) -> Dict[str, Decimal]:
        if exchange not in self._market:
            return {}
        return self._market[exchange].get_all_balances()

    async def update_exchange(
        self,
        client_config_map: ClientConfigMap,
        reconnect: bool = False,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, Optional[str]]:
        """
        Simple gateway balance update for compatibility.
        Returns empty dict (no errors) since gateway balances are fetched on-demand.
        """
        # Gateway balances are fetched directly from the gateway when needed
        # No need to maintain cached balances like CEX connectors
        return {}

    async def balance(self, exchange, client_config_map: ClientConfigMap, *symbols) -> Dict[str, Decimal]:
        """
        Get balances for specified tokens from a gateway connector.

        Args:
            exchange: The gateway connector name (e.g., "uniswap_ethereum_mainnet")
            client_config_map: Client configuration
            *symbols: Token symbols to get balances for

        Returns:
            Dict mapping token symbols to their balances
        """
        try:
            # Parse exchange name to get connector format
            # Exchange names like "uniswap_ethereum_mainnet" need to be converted to "uniswap/amm" format
            parts = exchange.split("_")
            if len(parts) < 1:
                self.logger().warning(f"Invalid gateway exchange format: {exchange}")
                return {}

            # The connector name is the first part
            connector_name = parts[0]

            # Determine connector type - this is a simplified mapping
            # In practice, this should be determined from the connector settings
            connector_type = "amm"  # Default to AMM for now
            connector = f"{connector_name}/{connector_type}"

            # Get chain and network from the connector
            gateway = self._get_gateway_instance()
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )

            if error:
                self.logger().warning(f"Error getting chain/network for {exchange}: {error}")
                return {}

            # Get default wallet for the chain
            default_wallet = await gateway.get_default_wallet_for_chain(chain)
            if not default_wallet:
                self.logger().warning(f"No default wallet for chain {chain}")
                return {}

            # Fetch balances directly from gateway
            tokens_list = list(symbols) if symbols else []
            balances_resp = await gateway.get_balances(chain, network, default_wallet, tokens_list)
            balances = balances_resp.get("balances", {})

            # Convert to Decimal and match requested symbols
            results = {}
            for token, balance in balances.items():
                for symbol in symbols:
                    if token.lower() == symbol.lower():
                        results[symbol] = Decimal(str(balance))
                        break

            return results

        except Exception as e:
            self.logger().error(f"Error getting gateway balances: {e}", exc_info=True)
            return {}

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

    def _get_gateway_instance(
        self  # type: HummingbotApplication
    ) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(
            self.client_config_map)
        return gateway_instance

    async def _get_allowances(self, connector: Optional[str] = None):
        """Get token allowances for Ethereum-based connectors"""
        gateway_instance = self._get_gateway_instance()
        self.notify("Checking token allowances, please wait...")

        try:
            # If specific connector requested
            if connector is not None:
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

                if chain.lower() != "ethereum":
                    self.notify(f"Allowances are only applicable for Ethereum chains. {connector} uses {chain}.")
                    return

                # Get default wallet
                wallet_address, error = await gateway_instance.get_default_wallet(chain)
                if error:
                    self.notify(error)
                    return

                # Get all available tokens for this chain/network
                token_list = await self._get_gateway_instance().get_available_tokens(chain, network)
                if not token_list:
                    self.notify(f"No tokens found for {chain}:{network}")
                    return

                # Create a dict of token symbol to token info
                token_data = {token["symbol"]: token for token in token_list}
                token_symbols = [token["symbol"] for token in token_list]

                # Get allowances using connector including trading type (spender in Gateway)
                allowance_resp = await gateway_instance.get_allowances(
                    chain, network, wallet_address, token_symbols, connector, fail_silently=True
                )

                # Format allowances using the helper
                if allowance_resp.get("approvals") is not None:
                    rows = GatewayCommandUtils.format_allowance_display(
                        allowance_resp["approvals"],
                        token_data=token_data
                    )
                else:
                    rows = []

                if rows:
                    # We always have address data now
                    columns = ["Symbol", "Address", "Allowance"]
                    df = pd.DataFrame(data=rows, columns=columns)
                    df.sort_values(by=["Symbol"], inplace=True)
                else:
                    df = pd.DataFrame()

                self.notify(f"\nConnector: {connector}")
                self.notify(f"Chain: {chain}")
                self.notify(f"Network: {network}")
                self.notify(f"Wallet: {wallet_address}")

                if df.empty:
                    self.notify("No token allowances found.")
                else:
                    lines = [
                        "    " + line for line in df.to_string(index=False).split("\n")
                    ]
                    self.notify("\n".join(lines))
            else:
                # Show allowances for all Ethereum connectors
                self.notify("Checking allowances for all Ethereum-based connectors...")

                # Get all connectors
                connectors_resp = await gateway_instance.get_connectors()
                if "error" in connectors_resp:
                    self.notify(f"Error getting connectors: {connectors_resp['error']}")
                    return

                ethereum_connectors = []
                for conn in connectors_resp.get("connectors", []):
                    if conn.get("chain", "").lower() == "ethereum":
                        # Get trading types for this connector
                        trading_types = conn.get("trading_types", [])
                        for trading_type in trading_types:
                            ethereum_connectors.append(f"{conn['name']}/{trading_type}")

                if not ethereum_connectors:
                    self.notify("No Ethereum-based connectors found.")
                    return

                # Get allowances for each ethereum connector
                for connector_name in ethereum_connectors:
                    await self._get_allowances(connector_name)

        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the allowances from updating. See logs for more details.")
            raise
        except Exception as e:
            self.notify(f"\nError getting allowances: {str(e)}")
            self.logger().error(f"Error getting allowances: {e}", exc_info=True)
