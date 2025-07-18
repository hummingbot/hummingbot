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
from hummingbot.client.command.gateway_wrap_command import GatewayWrapCommand
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.gateway.core import GatewayClient, GatewayStatus
from hummingbot.connector.gateway.utils.gateway_utils import get_gateway_paths
from hummingbot.core.data_type.in_flight_order import OrderState
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


class GatewayCommand(GatewayChainApiManager, GatewayTokenCommand, GatewayWalletCommand, GatewayPoolCommand, GatewaySwapCommand, GatewayWrapCommand):
    """Main gateway command handler that inherits from specialized command classes."""

    # Shared utility connector for wrap/unwrap/approve operations
    _utility_connector = None

    def _get_utility_connector(self, chain: str, network: str, wallet_address: str):
        """Get or create a shared utility connector for wrap/unwrap/approve operations."""
        # Create key for this chain/network combination
        connector_key = f"{chain}_{network}"

        # Check if we already have a connector for this chain/network
        if self._utility_connector is None or getattr(self._utility_connector, '_key', None) != connector_key:
            from hummingbot.connector.gateway.core.gateway_connector import GatewayConnector

            self._utility_connector = GatewayConnector(
                connector_name="uniswap/router",  # Use uniswap router for utility operations
                network=network,
                wallet_address=wallet_address,
                trading_required=False
            )

            # Skip initialization - we just need the execute_transaction functionality
            self._utility_connector._ready = True
            self._utility_connector.chain = chain
            self._utility_connector._key = connector_key

        return self._utility_connector

    async def _wait_for_transaction(self, connector, order_id: str, tx_hash: str, tx_type: str,
                                    amount: str, from_token: str, to_token: str) -> None:
        """
        Wait for a transaction to complete. The actual monitoring is done by TransactionMonitor
        inside the GatewayConnector.execute_transaction method.

        :param connector: GatewayConnector instance
        :param order_id: Order ID to monitor
        :param tx_hash: Transaction hash
        :param tx_type: Type of transaction (wrap, unwrap, approve)
        :param amount: Amount being transacted
        :param from_token: Source token
        :param to_token: Destination token (for wrap/unwrap) or spender (for approve)
        """
        self.notify(f"\nMonitoring transaction (Order ID: {order_id})...")
        self.logger().debug(f"_wait_for_transaction called for {tx_type} order {order_id}, tx_hash: {tx_hash}")

        # Give a small delay for the order to be processed
        # Approve transactions often confirm very quickly, so we need a bit more time
        if tx_type == "approve":
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(0.1)

        # Use same timeout as TransactionMonitor.MAX_POLL_TIME
        max_wait_time = 30.0  # seconds
        check_interval = 0.2  # Check very frequently for fast confirmations
        elapsed_time = 0
        displayed_pending = False
        confirmed = False

        while elapsed_time < max_wait_time:
            order = connector.get_order(order_id)
            self.logger().debug(f"Checking order {order_id}: found={order is not None}, is_done={order.is_done if order else 'N/A'}, is_filled={order.is_filled if order else 'N/A'}")
            if order:
                # Check if order is done (either filled or failed)
                if order.is_done:
                    if order.is_filled:
                        if tx_type == "wrap":
                            self.notify(f"\n✓ Successfully wrapped {amount} {from_token} to {to_token}")
                        elif tx_type == "unwrap":
                            self.notify(f"\n✓ Successfully unwrapped {amount} {from_token} to {to_token}")
                        elif tx_type == "approve":
                            self.notify(f"\n✓ Successfully approved {from_token} for {to_token}")
                        self.notify(f"Transaction confirmed: {tx_hash}")
                    elif order.is_failure:
                        self.notify("\n✗ Transaction failed")
                    return  # Exit the function
                # Also check the current_state directly
                elif hasattr(order, 'current_state') and order.current_state in [OrderState.FILLED, OrderState.FAILED]:
                    if order.current_state == OrderState.FILLED:
                        if tx_type == "wrap":
                            self.notify(f"\n✓ Successfully wrapped {amount} {from_token} to {to_token}")
                        elif tx_type == "unwrap":
                            self.notify(f"\n✓ Successfully unwrapped {amount} {from_token} to {to_token}")
                        elif tx_type == "approve":
                            self.notify(f"\n✓ Successfully approved {from_token} for {to_token}")
                        self.notify(f"Transaction confirmed: {tx_hash}")
                    else:
                        self.notify("\n✗ Transaction failed")
                    confirmed = True
                    break  # Exit the loop

            if elapsed_time >= 5 and not displayed_pending:
                self.notify("Transaction pending...")
                displayed_pending = True

            await asyncio.sleep(check_interval)
            elapsed_time += check_interval

        # If we haven't confirmed yet, check one more time
        if not confirmed:
            order = connector.get_order(order_id)
            if order and order.is_filled:
                if tx_type == "wrap":
                    self.notify(f"\n✓ Successfully wrapped {amount} {from_token} to {to_token}")
                elif tx_type == "unwrap":
                    self.notify(f"\n✓ Successfully unwrapped {amount} {from_token} to {to_token}")
                elif tx_type == "approve":
                    self.notify(f"\n✓ Successfully approved {from_token} for {to_token}")
                self.notify(f"Transaction confirmed: {tx_hash}")
            elif order and order.is_failure:
                self.notify("\n✗ Transaction failed")
            else:
                self.notify("\n⚠️  Transaction monitoring timed out.")
                self.notify(f"You can check the transaction manually: {tx_hash}")
    client_config_map: ClientConfigMap
    _market: Dict[str, Any] = {}

    def __init__(self,  # type: HummingbotApplication
                 client_config_map: ClientConfigMap
                 ):
        self.client_config_map = client_config_map

    def gateway(self):
        """Show gateway help when no subcommand is provided."""
        self.notify("\nGateway Commands:")
        self.notify("  gateway ping [chain]                              - Test gateway connection")
        self.notify("  gateway list                                      - List available connectors")
        self.notify("  gateway config show [namespace]                   - Show configuration")
        self.notify("  gateway config update <namespace> [path] [value]  - Update configuration")
        self.notify("  gateway token <action> ...                        - Manage tokens")
        self.notify("  gateway wallet <action> ...                       - Manage wallets")
        self.notify("  gateway pool <action> ...                         - Manage liquidity pools")
        self.notify("  gateway balance [chain] [tokens]                  - Check token balances")
        self.notify("  gateway allowance <spender> [tokens]              - Check token allowances")
        self.notify("  gateway approve <spender> <tokens>                - Approve tokens for spending")
        self.notify("  gateway wrap <amount>                             - Wrap native tokens")
        self.notify("  gateway unwrap <amount>                           - Unwrap wrapped tokens")
        self.notify("  gateway swap <connector> [pair] [side] [amount]   - Swap tokens (shows quote first)")
        self.notify("  gateway generate-certs                            - Generate SSL certificates")
        self.notify("  gateway restart                                   - Restart gateway service")
        self.notify("\nUse 'gateway <command> --help' for more information about a command.")

    @ensure_gateway_online
    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_balance(self, chain: Optional[str] = None, tokens: Optional[str] = None):
        safe_ensure_future(self._get_balances(chain, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_allowance(self, spender: Optional[str] = None, tokens: Optional[str] = None):
        """
        Command to check token allowances for Ethereum-based connectors
        Usage: gateway allowance [spender] [tokens]
        """
        safe_ensure_future(self._get_allowances(spender, tokens), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_approve(self, spender: Optional[str] = None, tokens: Optional[str] = None):
        """
        Command to approve tokens for spending on a connector
        Usage: gateway approve [spender] [tokens]
        """
        if all([spender, tokens]):
            safe_ensure_future(self._approve_tokens(spender, tokens), loop=self.ev_loop)
        else:
            self.notify(
                "\nPlease specify all required parameters: spender and tokens.\n"
                "Usage: gateway approve <spender> <tokens>\n"
                "Example: gateway approve uniswap/amm USDC,USDT\n")

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    def gateway_restart(self):
        safe_ensure_future(self._gateway_restart(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_ping(self, chain: Optional[str] = None):
        """
        Test gateway connectivity and check network status.
        Usage:
            gateway ping              - Check all chains with default networks
            gateway ping [chain]      - Check specific chain with default network
        """
        safe_ensure_future(self._gateway_ping(chain), loop=self.ev_loop)

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
                safe_ensure_future(self._update_gateway_configuration(namespace, path, value), loop=self.ev_loop)
            else:
                # Interactive mode - prompt for path and value
                safe_ensure_future(self._update_gateway_configuration_interactive(namespace), loop=self.ev_loop)
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

    async def _gateway_restart(self):
        """Restart the gateway service."""
        try:
            self.notify("\nRestarting Gateway service...")

            # First check if gateway is running
            is_online = await self._get_gateway_instance().ping_gateway()

            if not is_online:
                self.notify("Gateway is not currently running. Please start it manually.")
                return

            # Call the restart endpoint
            try:
                # Use the dedicated restart method that handles the request properly
                await self._get_gateway_instance().restart_gateway()

                self.notify("✓ Gateway restart initiated.")
                self.notify("Please wait a few seconds for the service to come back online...")

                # Wait a bit for the old process to exit and new one to start
                await asyncio.sleep(3)

                # Check if gateway is back online
                max_attempts = 10
                for attempt in range(max_attempts):
                    if await self._get_gateway_instance().ping_gateway():
                        self.notify("\n✓ Gateway is back online.")
                        # Reinitialize gateway caches
                        await self._get_gateway_instance().initialize_gateway()
                        break
                    await asyncio.sleep(1)
                else:
                    self.notify("\n⚠️  Gateway did not come back online within expected time.")
                    self.notify("Please check the gateway logs and start it manually if needed.")

            except Exception as e:
                self.notify(f"Error restarting gateway: {str(e)}")
                self.notify("\nNote: Some gateway installations may not support automatic restart.")
                self.notify("You may need to restart the gateway service manually.")

        except Exception as e:
            self.notify(f"Error: {str(e)}")

    async def _gateway_ping(self, chain: Optional[str] = None):
        """
        Test gateway connectivity and check network status.
        If chain is specified, check only that chain with its default network.
        Otherwise, check default network for each chain.
        """
        try:
            # First check if gateway is running
            gateway_status = await self._get_gateway_instance().ping_gateway()
            if not gateway_status:
                self.notify("\nUnable to connect to gateway.")
                return

            self.notify("\nGateway Status: Online")

            # If chain is provided, check default network for that chain
            if chain:
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
                    native_currency = await self._get_gateway_instance().get_native_currency_symbol(chain, network)
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

    async def _update_gateway_configuration_interactive(self, namespace: str):
        """Interactive mode for gateway config update"""
        from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode

        try:
            # First get the current configuration to show available paths
            config_dict = await self._get_gateway_instance().get_config(namespace=namespace)

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
            # Use new get_config method with only namespace
            config_dict = await self._get_gateway_instance().get_config(namespace=namespace)

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
        except Exception as e:
            remote_host = ':'.join([host, port])
            self.notify(f"\nError: Connection to Gateway {remote_host} failed: {str(e)}")

    async def _get_balances(self, chain_filter: Optional[str] = None, tokens_filter: Optional[str] = None):
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        # Use longer timeout for balance requests since some networks like Base can be slow
        balance_timeout = max(network_timeout, 10.0)  # At least 10 seconds
        self.notify("Updating gateway balances, please wait...")

        try:
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
                default_network = await self._get_default_network_for_chain(chain)
                if not default_network:
                    self.notify(f"Could not determine default network for {chain}")
                    continue

                # Get default wallet for this chain
                default_wallet = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
                if not default_wallet:
                    self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                    continue

                # Check if this is a hardware wallet
                wallets = await self._get_gateway_instance().get_wallets(chain)
                is_hardware = False
                if wallets:
                    wallet_info = wallets[0]
                    hardware_addresses = wallet_info.get("hardwareWalletAddresses", [])
                    is_hardware = default_wallet in hardware_addresses
                try:
                    # Determine tokens to check
                    if tokens_filter:
                        # User specified tokens (comma-separated)
                        tokens_to_check = [token.strip() for token in tokens_filter.split(",")]
                    else:
                        # No filter specified - fetch all tokens
                        tokens_to_check = []

                    # Get balances from gateway
                    try:
                        tokens_display = "all" if not tokens_to_check else ", ".join(tokens_to_check)
                        self.notify(f"Fetching balances for {chain}:{default_network} address {default_wallet[:8]}... tokens: {tokens_display}")
                        balances_resp = await asyncio.wait_for(
                            self._get_gateway_instance().get_balances(chain, default_network, default_wallet, tokens_to_check),
                            balance_timeout
                        )
                        balances = balances_resp.get("balances", {})
                    except asyncio.TimeoutError:
                        self.notify(f"\nTimeout getting balance for {chain}:{default_network}")
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
                        native_token = await self._get_gateway_instance().get_native_currency_symbol(chain, default_network)

                        for token, bal in balances.items():
                            balance_val = float(bal) if bal else 0
                            # Always include native token (even if zero), include others only if non-zero
                            if (native_token and token.upper() == native_token.upper()) or balance_val > 0:
                                display_balances[token] = bal

                    # Display results
                    self.notify(f"\nChain: {chain.lower()}")
                    self.notify(f"Network: {default_network}")
                    if is_hardware:
                        self.notify(f"Address: {default_wallet} (hardware)")
                    else:
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

                except Exception as e:
                    self.notify(f"\nError getting balance for {chain}:{default_network}: {str(e)}")
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

    async def _approve_tokens(self, spender: str, tokens: str):
        """
        Approve tokens for spending on a connector.
        """
        try:
            # Determine chain from spender (all current approve-capable connectors are on Ethereum)
            chain = "ethereum"

            # Get default network
            network = await self._get_default_network_for_chain(chain)
            if not network:
                self.notify(f"Error: Could not determine default network for {chain}")
                return

            self.logger().info(
                f"Approving tokens {tokens} for {spender} on {network} network")

            # Get default wallet for ethereum
            wallet_address = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not wallet_address:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return

            # Approve each token separately
            token_list = [t.strip() for t in tokens.split(",")]
            for token in token_list:
                self.notify(f"Approving {token} for {spender}...")

                try:
                    # Always use chain-specific approve endpoint
                    # The spender can be a connector name (e.g., "uniswap/router") or an address
                    resp = await self._get_gateway_instance().approve_token(network, wallet_address, token, spender)
                    transaction_hash = resp.get("approval", {}).get("hash") or resp.get("signature")

                    if not transaction_hash:
                        self.notify(f"Failed to get transaction hash for {token} approval")
                        continue

                    # Get shared utility connector
                    connector = self._get_utility_connector(chain, network, wallet_address)

                    # Track the transaction
                    order_id = await connector.execute_transaction(
                        tx_type="approve",
                        chain=chain,
                        network=network,
                        tx_hash=transaction_hash,
                        amount=Decimal("0"),  # Approve doesn't have an amount
                        token=token,
                        spender=spender
                    )

                    # Wait for transaction to complete
                    self.logger().debug(f"Starting _wait_for_transaction for approve order {order_id}")
                    await self._wait_for_transaction(connector, order_id, transaction_hash, "approve",
                                                     "0", token, spender)
                    self.logger().debug(f"Completed _wait_for_transaction for approve order {order_id}")

                except Exception as e:
                    import traceback
                    self.logger().error(f"Error in approve flow: {str(e)}")
                    self.logger().error(f"Traceback: {traceback.format_exc()}")
                    self.notify(f"Error approving {token}: {str(e)}")
                    continue

        except Exception as e:
            self.notify(f"Error in approve tokens: {str(e)}")

    def _get_gateway_instance(
        self  # type: HummingbotApplication
    ) -> GatewayClient:
        # Pass the client config map to GatewayClient
        return GatewayClient.get_instance(self.client_config_map)

    async def _get_allowances(self, spender: Optional[str] = None, tokens: Optional[str] = None):
        """Get token allowances for Ethereum-based connectors"""
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Checking token allowances, please wait...")
        try:
            # Validate parameters
            if not spender:
                self.notify("\nPlease specify spender.")
                self.notify("Usage: gateway allowance <spender> [tokens]")
                self.notify("Example: gateway allowance uniswap/amm")
                return

            # Get default network and wallet for ethereum
            chain = "ethereum"
            network = await self._get_default_network_for_chain(chain)
            if not network:
                self.notify(f"Error: Could not determine default network for {chain}")
                return

            # Get default wallet for ethereum
            default_wallet = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not default_wallet:
                self.notify(f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return

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
                    native_token = await self._get_gateway_instance().get_native_currency_symbol("ethereum", network)
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

            try:
                # Get allowances from gateway
                allowances_resp = await asyncio.wait_for(
                    self._get_gateway_instance().get_allowances(
                        network, default_wallet, spender, tokens_to_check
                    ),
                    network_timeout
                )

                allowances = allowances_resp.get("approvals", {}) if allowances_resp else {}

                # Display results
                self.notify(f"\nNetwork: {network}")
                # Check if this is a hardware wallet
                wallets = await self._get_gateway_instance().get_wallets(chain)
                is_hardware = False
                if wallets:
                    wallet_info = wallets[0]
                    hardware_addresses = wallet_info.get("hardwareWalletAddresses", [])
                    is_hardware = default_wallet in hardware_addresses

                if is_hardware:
                    self.notify(f"Wallet: {default_wallet} (hardware)")
                else:
                    self.notify(f"Wallet: {default_wallet}")
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
        try:
            # First try to get from chain config
            default_network = await self._get_gateway_instance().get_default_network_for_chain(chain)
            if default_network:
                return default_network

            # Fallback to getting the first network from gateway
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
