#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd

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
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.gateway_config_utils import build_config_dict_display
from hummingbot.core.utils.ssl_cert import create_self_sign_certs
from hummingbot.user.user_balances import UserBalances

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
        self.notify("\nGateway Commands:")
        self.notify("  gateway ping [chain]                              - Test gateway connectivity and network status")
        self.notify("  gateway list                                      - List available connectors")
        self.notify("  gateway config [namespace]                        - Show configuration")
        self.notify("  gateway config <namespace> update                 - Update configuration (interactive)")
        self.notify("  gateway connect <chain>                           - Add a wallet for a chain")
        # self.notify("  gateway token <action> ...                        - Manage tokens")
        # self.notify("  gateway wallet <action> ...                       - Manage wallets")
        # self.notify("  gateway pool <action> ...                         - Manage liquidity pools")
        self.notify("  gateway balance [chain] [tokens]                  - Check token balances")
        self.notify("  gateway allowance <connector> [tokens]            - Check token allowances")
        self.notify("  gateway approve <connector> <tokens>              - Approve tokens for spending")
        # self.notify("  gateway wrap <amount>                             - Wrap native tokens")
        # self.notify("  gateway unwrap <amount>                           - Unwrap wrapped tokens")
        self.notify("  gateway swap <connector> [pair] [side] [amount]   - Swap tokens")
        self.notify("  gateway lp <connector> <action>                   - Manage liquidity positions")
        self.notify("  gateway generate-certs                            - Generate SSL certificates")
        self.notify("\nUse 'gateway <command> --help' for more information about a command.")

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
        Add a wallet for a specific chain.
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
    def gateway_list(self):
        safe_ensure_future(self._gateway_list(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_config(self, namespace: str = None, action: str = None, args: List[str] = None):
        """
        Gateway configuration management.
        Usage:
            gateway config [namespace]       - Show configuration for namespace
            gateway config <namespace> update - Update configuration (interactive)
        """
        if args is None:
            args = []

        if namespace is None:
            # Show help when no namespace is provided
            self.notify("\nUsage:")
            self.notify("  gateway config [namespace]        - Show configuration")
            self.notify("  gateway config <namespace> update - Update configuration (interactive)")
            self.notify("\nExamples:")
            self.notify("  gateway config ethereum-mainnet")
            self.notify("  gateway config uniswap")
            self.notify("  gateway config ethereum-mainnet update")
        elif action is None:
            # Format: gateway config <namespace>
            # Show configuration for the specified namespace
            safe_ensure_future(self._show_gateway_configuration(namespace=namespace), loop=self.ev_loop)
        elif action == "update":
            # Interactive mode only - prompt for path and value
            safe_ensure_future(self._update_gateway_configuration_interactive(namespace), loop=self.ev_loop)
        else:
            # If action is not "update", it might be a namespace typo
            self.notify(f"\nError: Invalid action '{action}'. Use 'update' to modify configuration.")
            self.notify("\nUsage:")
            self.notify("  gateway config <namespace>        - Show configuration")
            self.notify("  gateway config <namespace> update - Update configuration")

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
        """Add a wallet for a specific chain."""
        try:
            # Get default network for the chain
            default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
            if not default_network:
                self.notify(f"\nError: Could not determine default network for chain '{chain}'")
                self.notify("Please check that the chain name is correct.")
                return

            self.notify(f"\n=== Add Wallet for {chain} ===")
            self.notify(f"Network: {default_network}")

            # Enter interactive mode
            with begin_placeholder_mode(self):
                # Ask for wallet type
                wallet_type = await self.app.prompt(
                    prompt="Wallet type (1: Regular, 2: Hardware) [default: 1]: "
                )

                if self.app.to_stop_config:
                    self.notify("Wallet addition cancelled")
                    return

                # Default to regular wallet if empty or invalid input
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

    async def _update_gateway_configuration(self, namespace: str, key: str, value: Any):
        try:
            response = await self._get_gateway_instance().update_config(namespace=namespace, path=key, value=value)
            self.notify(response["message"])
        except Exception:
            self.notify(
                "\nError: Gateway configuration update failed. See log file for more details.")

    async def _update_gateway_configuration_interactive(self, namespace: str):
        """Interactive mode for gateway config update"""
        from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode

        try:
            # First get the current configuration to show available paths
            config_dict = await self._get_gateway_instance().get_configuration(namespace=namespace)

            if not config_dict:
                self.notify(f"No configuration found for namespace: {namespace}")
                return

            # Display current configuration
            self.notify(f"\nCurrent configuration for {namespace}:")
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

            # Get available config keys
            config_keys = list(config_dict.keys())

            # Enter interactive mode
            with begin_placeholder_mode(self):
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # Update completer's config path options
                    if hasattr(self.app.input_field.completer, '_gateway_config_path_options'):
                        self.app.input_field.completer._gateway_config_path_options = config_keys

                    # Prompt for path
                    self.notify(f"\nAvailable configuration paths: {', '.join(config_keys)}")
                    path = await self.app.prompt(prompt="Enter configuration path: ")

                    if self.app.to_stop_config or not path:
                        self.notify("Configuration update cancelled")
                        return

                    # Show current value
                    current_value = config_dict.get(path, "Not found")
                    self.notify(f"\nCurrent value for '{path}': {current_value}")

                    # Prompt for new value
                    value = await self.app.prompt(prompt="Enter new value: ")

                    if self.app.to_stop_config or not value:
                        self.notify("Configuration update cancelled")
                        return

                    # Update the configuration
                    await self._update_gateway_configuration(namespace, path, value)

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

        except Exception as e:
            self.notify(f"Error in interactive config update: {str(e)}")

    async def _show_gateway_configuration(
        self,  # type: HummingbotApplication
        namespace: Optional[str] = None,
    ):
        host = self.client_config_map.gateway.gateway_api_host
        port = self.client_config_map.gateway.gateway_api_port
        try:
            # config_dict: Dict[str, Any] = await self._gateway_monitor._fetch_gateway_configs()
            config_dict = await self._get_gateway_instance().get_configuration(namespace=namespace)
            # Format the title
            title_parts = ["Gateway Configuration"]
            if namespace:
                title_parts.append(f"namespace: {namespace}")
            title = f"\n{' - '.join(title_parts)}:"

            self.notify(title)
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

        except asyncio.CancelledError:
            raise
        except Exception:
            remote_host = ':'.join([host, port])
            self.notify(f"\nError: Connection to Gateway {remote_host} failed")

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
            # Check both ethereum and solana
            chains_to_check = ["ethereum", "solana"]

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
            if "wallet-address" in default_wallet.lower():
                self.notify(f"\n⚠️  {chain} wallet not configured (found placeholder: {default_wallet})")
                self.notify(f"Please add a real wallet with: gateway connect {chain}")
                continue

            try:
                # Determine tokens to check
                if tokens_filter:
                    # User specified tokens (comma-separated)
                    tokens_to_check = [token.strip() for token in tokens_filter.split(",")]
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

    async def update_exchange_balances(self, exchange, client_config_map: ClientConfigMap) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        is_gateway_markets = UserBalances.is_gateway_market(exchange)
        if is_gateway_markets and exchange in self._market:
            del self._market[exchange]
        if exchange in self._market:
            return await self._update_balances(self._market[exchange])
        else:
            await Security.wait_til_decryption_done()
            api_keys = Security.api_keys(
                exchange) if not UserBalances.is_gateway_market(exchange) else {}
            return await self.add_gateway_exchange(exchange, client_config_map, **api_keys)

    async def update_exchange(
        self,
        client_config_map: ClientConfigMap,
        reconnect: bool = False,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, Optional[str]]:
        exchanges = exchanges or []
        tasks = []
        # Update user balances
        if len(exchanges) == 0:
            exchanges = [
                cs.name for cs in AllConnectorSettings.get_connector_settings().values()]
        exchanges: List[str] = [
            cs.name
            for cs in AllConnectorSettings.get_connector_settings().values()
            if not cs.use_ethereum_wallet
            and cs.name in exchanges
            and not cs.name.endswith("paper_trade")
        ]

        if reconnect:
            self._market.clear()
        for exchange in exchanges:
            tasks.append(self.update_exchange_balances(
                exchange, client_config_map))
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(exchanges, results)}

    async def balance(self, exchange, client_config_map: ClientConfigMap, *symbols) -> Dict[str, Decimal]:
        if await self.update_exchange_balances(exchange, client_config_map) is None:
            results = {}
            for token, bal in self.all_balance(exchange).items():
                matches = [s for s in symbols if s.lower() == token.lower()]
                if matches:
                    results[matches[0]] = bal
            return results

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
        from hummingbot.connector.gateway.command_utils import GatewayCommandUtils

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
                chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                    gateway_instance, connector
                )
                if error:
                    self.notify(error)
                    return

                if chain.lower() != "ethereum":
                    self.notify(f"Allowances are only applicable for Ethereum chains. {connector} uses {chain}.")
                    return

                # Get default wallet
                wallet_address, error = await GatewayCommandUtils.get_default_wallet(gateway_instance, chain)
                if error:
                    self.notify(error)
                    return

                # Get all available tokens for this chain/network
                token_list = await GatewayCommandUtils.get_available_tokens(gateway_instance, chain, network)
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
