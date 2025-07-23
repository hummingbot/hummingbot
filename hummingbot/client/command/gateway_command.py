#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ReadOnlyClientConfigAdapter, get_connector_class
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings, GatewayConnectionSetting, gateway_connector_trading_pairs
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.gateway import get_gateway_paths
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.gateway_config_utils import (
    build_config_dict_display,
    build_connector_tokens_display,
    flatten,
)
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
        self.notify("\nGateway Commands:")
        self.notify("  gateway test-connection [chain]                   - Test gateway connection")
        self.notify("  gateway list                                      - List available connectors")
        self.notify("  gateway config show [namespace]                   - Show configuration")
        self.notify("  gateway config update <namespace> [path] [value]  - Update configuration")
        # self.notify("  gateway token <action> ...                        - Manage tokens")
        # self.notify("  gateway wallet <action> ...                       - Manage wallets")
        # self.notify("  gateway pool <action> ...                         - Manage liquidity pools")
        self.notify("  gateway balance [chain] [tokens]                  - Check token balances")
        self.notify("  gateway allowance <connector> [tokens]            - Check token allowances")
        self.notify("  gateway approve <connector> <tokens>              - Approve tokens for spending")
        # self.notify("  gateway wrap <amount>                             - Wrap native tokens")
        # self.notify("  gateway unwrap <amount>                           - Unwrap wrapped tokens")
        self.notify("  gateway swap <connector> [pair] [side] [amount]   - Swap tokens (shows quote first)")
        self.notify("  gateway generate-certs                            - Generate SSL certificates")
        self.notify("\nUse 'gateway <command> --help' for more information about a command.")

    @ensure_gateway_online
    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_balance(self, chain: Optional[str] = None, tokens: Optional[str] = None):
        safe_ensure_future(self._get_balances(chain, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_allowance(self, connector_chain_network: Optional[str] = None):
        """
        Command to check token allowances for Ethereum-based connectors
        Usage: gateway allowances [exchange_name]
        """
        safe_ensure_future(self._get_allowances(connector_chain_network), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_approve_tokens(self, connector_chain_network: Optional[str], tokens: Optional[str]):
        if connector_chain_network is not None and tokens is not None:
            safe_ensure_future(self._update_gateway_approve_tokens(
                connector_chain_network, tokens), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify the connector_chain_network and a token to approve.\n")

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    @ensure_gateway_online
    def test_connection(self):
        safe_ensure_future(self._test_connection(), loop=self.ev_loop)

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
            gateway config update <namespace> (interactive mode)
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
                safe_ensure_future(self._update_gateway_configuration(namespace, path, value), loop=self.ev_loop)
            else:
                # Interactive mode - prompt for path and value
                safe_ensure_future(self._update_gateway_configuration_interactive(namespace), loop=self.ev_loop)
        else:
            # Show help if unrecognized action
            self.notify("\nUsage:")
            self.notify("  gateway config show [namespace]")
            self.notify("  gateway config update <namespace> <path> <value>")

    async def _test_connection(self):
        # test that the gateway is running
        if await self._get_gateway_instance().ping_gateway():
            self.notify("\nSuccessfully pinged gateway.")
        else:
            self.notify("\nUnable to ping gateway.")

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
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
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

    def connect_markets(exchange, client_config_map: ClientConfigMap, **api_details):
        connector = None
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        if api_details or conn_setting.uses_gateway_generic_connector():
            connector_class = get_connector_class(exchange)
            read_only_client_config = ReadOnlyClientConfigAdapter.lock_config(
                client_config_map)
            init_params = conn_setting.conn_init_parameters(
                trading_pairs=gateway_connector_trading_pairs(
                    conn_setting.name),
                api_keys=api_details,
                client_config_map=read_only_client_config,
            )

            # collect trading pairs from the gateway connector settings
            trading_pairs: List[str] = gateway_connector_trading_pairs(
                conn_setting.name)

            # collect unique trading pairs that are for balance reporting only
            if conn_setting.uses_gateway_generic_connector():
                config: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(
                    conn_setting.name)
                if config is not None:
                    existing_pairs = set(
                        flatten([x.split("-") for x in trading_pairs]))

                    other_tokens: Set[str] = set(
                        config.get("tokens", "").split(","))
                    other_tokens.discard("")
                    tokens: List[str] = [
                        t for t in other_tokens if t not in existing_pairs]
                    if tokens != [""]:
                        trading_pairs.append("-".join(tokens))

            connector = connector_class(**init_params)
        return connector

    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            await market._update_balances()
        except Exception as e:
            logging.getLogger().debug(
                f"Failed to update balances for {market}", exc_info=True)
            return str(e)
        return None

    async def add_gateway_exchange(self, exchange, client_config_map: ClientConfigMap, **api_details) -> Optional[str]:
        self._market.pop(exchange, None)
        is_gateway_markets = self.is_gateway_markets(exchange)
        if is_gateway_markets:
            market = GatewayCommand.connect_markets(
                exchange, client_config_map, **api_details)
            if not market:
                return "API keys have not been added."
            err_msg = await GatewayCommand._update_balances(market)
            if err_msg is None:
                self._market[exchange] = market
            return err_msg

    def all_balance(self, exchange) -> Dict[str, Decimal]:
        if exchange not in self._market:
            return {}
        return self._market[exchange].get_all_balances()

    async def update_exchange_balances(self, exchange, client_config_map: ClientConfigMap) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        is_gateway_markets = self.is_gateway_markets(exchange)
        if is_gateway_markets and exchange in self._market:
            del self._market[exchange]
        if exchange in self._market:
            return await self._update_balances(self._market[exchange])
        else:
            await Security.wait_til_decryption_done()
            api_keys = Security.api_keys(
                exchange) if not is_gateway_markets else {}
            return await self.add_gateway_exchange(exchange, client_config_map, **api_keys)

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_markets(exchange_name: str) -> bool:
        return (
            exchange_name in sorted(
                AllConnectorSettings.get_gateway_amm_connector_names()
            )
        )

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

    async def all_balances_all_exc(self, client_config_map: ClientConfigMap) -> Dict[str, Dict[str, Decimal]]:
        # Waits for the update_exchange method to complete with the provided client_config_map
        await self.update_exchange(client_config_map)
        return {k: v.get_all_balances() for k, v in sorted(self._market.items(), key=lambda x: x[0])}

    async def balance(self, exchange, client_config_map: ClientConfigMap, *symbols) -> Dict[str, Decimal]:
        if await self.update_exchange_balances(exchange, client_config_map) is None:
            results = {}
            for token, bal in self.all_balance(exchange).items():
                matches = [s for s in symbols if s.lower() == token.lower()]
                if matches:
                    results[matches[0]] = bal
            return results

    async def update_exch(
        self,
        exchange: str,
        client_config_map: ClientConfigMap,
        reconnect: bool = False,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, Optional[str]]:
        exchanges = exchanges or []
        tasks = []
        if reconnect:
            self._market.clear()
        tasks.append(self.update_exchange_balances(exchange, client_config_map))
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(exchanges, results)}

    async def single_balance_exc(self, exchange, client_config_map: ClientConfigMap) -> Dict[str, Dict[str, Decimal]]:
        # Waits for the update_exchange method to complete with the provided client_config_map
        await self.update_exch(exchange, client_config_map)
        return {k: v.get_all_balances() for k, v in sorted(self._market.items(), key=lambda x: x[0])}

    async def _show_gateway_connector_tokens(
            self,           # type: HummingbotApplication
            connector_chain_network: str = None
    ):
        """
        Display connector tokens that hummingbot will report balances for
        """
        if connector_chain_network is None:
            gateway_connections_conf: Dict[str, List[str]] = GatewayConnectionSetting.load()
            if len(gateway_connections_conf) < 1:
                self.notify("No existing connection.\n")
            else:
                connector_df: pd.DataFrame = build_connector_tokens_display(gateway_connections_conf)
                self.notify(connector_df.to_string(index=False))
        else:
            conf: Optional[Dict[str, List[str]]] = GatewayConnectionSetting.get_connector_spec_from_market_name(connector_chain_network)
            if conf is not None:
                connector_df: pd.DataFrame = build_connector_tokens_display([conf])
                self.notify(connector_df.to_string(index=False))
            else:
                self.notify(
                    f"There is no gateway connection for {connector_chain_network}.\n")

    async def _update_gateway_connector_tokens(
            self,           # type: HummingbotApplication
            connector_chain_network: str,
            new_tokens: str,
    ):
        """
        Allow the user to input tokens whose balances they want to monitor are.
        These are not tied to a strategy, rather to the connector-chain-network
        tuple. This has no influence on what tokens the user can use with a
        connector-chain-network and a particular strategy. This is only for
        report balances.
        """
        conf: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(
            connector_chain_network)

        if conf is None:
            self.notify(
                f"'{connector_chain_network}' is not available. You can add and review available gateway connectors with the command 'gateway connect'.")
        else:
            GatewayConnectionSetting.upsert_connector_spec_tokens(connector_chain_network, new_tokens)
            self.notify(
                f"The 'gateway balance' command will now report token balances {new_tokens} for '{connector_chain_network}'.")

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

    async def _update_gateway_approve_tokens(
            self,           # type: HummingbotApplication
            connector_chain_network: str,
            tokens: str,
    ):
        """
        Allow the user to approve tokens for spending.
        """
        # get connector specs
        conf: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(
            connector_chain_network)
        if conf is None:
            self.notify(
                f"'{connector_chain_network}' is not available. You can add and review available gateway connectors with the command 'gateway connect'.")
        else:
            self.logger().info(
                f"Connector {conf['connector']} Tokens {tokens} will now be approved for spending for '{connector_chain_network}'.")
            # get wallets for the selected chain
            gateway_connections_conf: List[Dict[str,
                                                str]] = GatewayConnectionSetting.load()
            if len(gateway_connections_conf) < 1:
                self.notify("No existing wallet.\n")
                return
            connector_wallet: List[Dict[str, Any]] = [w for w in gateway_connections_conf if w["chain"] ==
                                                      conf['chain'] and w["connector"] == conf['connector'] and w["network"] == conf['network']]
            try:
                resp: Dict[str, Any] = await self._get_gateway_instance().approve_token(conf['network'], connector_wallet[0]['wallet_address'], tokens, conf['connector'])
                transaction_hash: Optional[str] = resp.get("signature")
                if not transaction_hash:
                    self.logger().error(f"No transaction hash returned from approval request. Response: {resp}")
                    self.notify("Error: No transaction hash returned from approval request.")
                    return
                displayed_pending: bool = False
                while True:
                    pollResp: Dict[str, Any] = await self._get_gateway_instance().get_transaction_status(conf['chain'], conf['network'], transaction_hash)
                    transaction_status: Optional[str] = pollResp.get(
                        "txStatus")
                    if transaction_status == 1:
                        self.logger().info(
                            f"Token {tokens} is approved for spending for '{conf['connector']}' for Wallet: {connector_wallet[0]['wallet_address']}.")
                        self.notify(
                            f"Token {tokens} is approved for spending for '{conf['connector']}' for Wallet: {connector_wallet[0]['wallet_address']}.")
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

    def _get_gateway_instance(
        self  # type: HummingbotApplication
    ) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(
            self.client_config_map)
        return gateway_instance

    async def _get_allowances(self, exchange_name: Optional[str] = None):
        """Get token allowances for Ethereum-based connectors"""
        gateway_connections = GatewayConnectionSetting.load()
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        self.notify("Checking token allowances, please wait...")

        # If specific exchange requested, filter for just that one
        if exchange_name is not None:
            conf = GatewayConnectionSetting.get_connector_spec_from_market_name(exchange_name)
            if conf is None:
                self.notify(f"'{exchange_name}' is not available. You can add and review exchange with 'gateway connect'.")
                return

            if conf["chain"].lower() != "ethereum":
                self.notify(f"Allowances are only applicable for Ethereum chains. {exchange_name} uses {conf['chain']}.")
                return

            gateway_connections = [conf]
        else:
            # Filter for only Ethereum chains
            gateway_connections = [conn for conn in gateway_connections if conn["chain"].lower() == "ethereum"]

            if not gateway_connections:
                self.notify("No Ethereum-based connectors found. Allowances are only applicable for Ethereum chains.")
                return

        try:
            allowance_tasks = []

            for conf in gateway_connections:
                chain, network, address = (
                    conf["chain"], conf["network"], conf["wallet_address"]
                )

                # Get configured tokens - don't add native token as it doesn't need allowances
                tokens_str = conf.get("tokens", "")
                tokens = [token.strip() for token in tokens_str.split(',')] if tokens_str else []

                if not tokens:
                    # Skip connectors without configured tokens
                    self.notify(f"\nConnector: {conf['connector']}_{chain}_{network}")
                    self.notify(f"Wallet_Address: {address}")
                    self.notify("No tokens configured for allowance check.")
                    continue

                connector = conf["connector"]
                allowance_resp = gateway_instance.get_allowances(
                    chain, network, address, tokens, connector, fail_silently=True
                )
                allowance_tasks.append((conf, allowance_resp))

            # Check if we have any tasks to process
            if not allowance_tasks:
                if exchange_name is None:
                    self.notify("No Ethereum connectors with configured tokens found.")
                return

            # Process each allowance response
            for conf, allowance_future in allowance_tasks:
                chain, network, address, connector = conf["chain"], conf["network"], conf["wallet_address"], conf["connector"]
                exchange_key = f'{connector}_{chain}_{network}'

                allowance_resp = await allowance_future

                rows = []
                if allowance_resp.get("approvals") is not None:
                    for token, allowance in allowance_resp["approvals"].items():
                        rows.append({
                            "Symbol": token.upper(),
                            "Allowance": PerformanceMetrics.smart_round(Decimal(str(allowance)), 4) if float(allowance) < 999999 else "999999+",
                        })

                df = pd.DataFrame(data=rows, columns=["Symbol", "Allowance"])
                df.sort_values(by=["Symbol"], inplace=True)

                self.notify(f"\nConnector: {exchange_key}")
                self.notify(f"Wallet_Address: {address}")

                if df.empty:
                    self.notify("No token allowances found for this exchange.")
                else:
                    lines = [
                        "    " + line for line in df.to_string(index=False).split("\n")
                    ]
                    self.notify("\n".join(lines))

        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the allowances from updating. See logs for more details.")
            raise
