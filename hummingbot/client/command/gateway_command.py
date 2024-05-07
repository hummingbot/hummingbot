#!/usr/bin/env python
import asyncio
import itertools
import logging
import time
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import (
    ReadOnlyClientConfigAdapter,
    get_connector_class,
    refresh_trade_fees_config,
)
from hummingbot.client.config.security import Security
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings, GatewayConnectionSetting, gateway_connector_trading_pairs
from hummingbot.client.ui.completer import load_completer
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.gateway import get_gateway_paths
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.gateway_config_utils import (
    build_config_dict_display,
    build_connector_display,
    build_connector_tokens_display,
    build_list_display,
    build_wallet_display,
    flatten,
    native_tokens,
    search_configs,
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

    @ensure_gateway_online
    def gateway_connect(self, connector: str = None):
        safe_ensure_future(self._gateway_connect(connector), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_balance(self, connector_chain_network: Optional[str] = None):
        if connector_chain_network is not None:
            safe_ensure_future(self._get_balance_for_exchange(
                connector_chain_network), loop=self.ev_loop)
        else:
            safe_ensure_future(self._get_balances(), loop=self.ev_loop)

    @ensure_gateway_online
    def gateway_connector_tokens(self, connector_chain_network: Optional[str], new_tokens: Optional[str]):
        if connector_chain_network is not None and new_tokens is not None:
            safe_ensure_future(self._update_gateway_connector_tokens(
                connector_chain_network, new_tokens), loop=self.ev_loop)
        else:
            safe_ensure_future(self._show_gateway_connector_tokens(
                connector_chain_network), loop=self.ev_loop)

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
    def gateway_config(self,
                       key: Optional[str] = None,
                       value: str = None):
        if value:
            safe_ensure_future(self._update_gateway_configuration(
                key, value), loop=self.ev_loop)
        else:
            safe_ensure_future(
                self._show_gateway_configuration(key), loop=self.ev_loop)

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

    async def _gateway_connect(
            self,           # type: HummingbotApplication
            connector: str = None
    ):
        with begin_placeholder_mode(self):
            gateway_connections_conf: List[Dict[str,
                                                str]] = GatewayConnectionSetting.load()
            if connector is None:
                if len(gateway_connections_conf) < 1:
                    self.notify("No existing connection.\n")
                else:
                    connector_df: pd.DataFrame = build_connector_display(
                        gateway_connections_conf)
                    self.notify(connector_df.to_string(index=False))
            else:
                # get available networks
                connector_configs: Dict[str, Any] = await self._get_gateway_instance().get_connectors()
                connector_config: List[Dict[str, Any]] = [
                    d for d in connector_configs["connectors"] if d["name"] == connector
                ]
                if len(connector_config) < 1:
                    self.notify(
                        f"No available blockchain networks available for the connector '{connector}'.")
                    return
                available_networks: List[Dict[str, Any]
                                         ] = connector_config[0]["available_networks"]
                trading_type: str = connector_config[0]["trading_type"][0]
                chain_type: str = connector_config[0]["chain_type"]
                additional_spenders: List[str] = connector_config[0].get(
                    "additional_spenders", [])
                additional_prompts: Dict[str, str] = connector_config[0].get(  # These will be stored locally.
                    # If Gateway requires additional, prompts with secure info,
                    "additional_add_wallet_prompts",
                    # a new attribute must be added (e.g. additional_secure_add_wallet_prompts)
                    {}
                )

                # ask user to select a chain. Automatically select if there is only one.
                chains: List[str] = [d['chain'] for d in available_networks]
                chain: str

                # chains as options
                while True:
                    self.app.input_field.completer.set_gateway_chains(chains)
                    chain = await self.app.prompt(
                        prompt=f"Which chain do you want {connector} to connect to? ({', '.join(chains)}) >>> "
                    )
                    if self.app.to_stop_config:
                        self.app.to_stop_config = False
                        return

                    if chain in chains:
                        break
                    self.notify(f"{chain} chain not supported.\n")

                # ask user to select a network. Automatically select if there is only one.
                networks: List[str] = list(
                    itertools.chain.from_iterable(
                        [d['networks'] for d in available_networks if d['chain'] == chain])
                )

                network: str
                while True:
                    self.app.input_field.completer.set_gateway_networks(
                        networks)
                    network = await self.app.prompt(
                        prompt=f"Which network do you want {connector} to connect to? ({', '.join(networks)}) >>> "
                    )
                    if self.app.to_stop_config:
                        return
                    if network in networks:
                        break
                    self.notify("Error: Invalid network")

                # test you can connect to the uri, otherwise request the url
                await self._test_node_url_from_gateway_config(chain, network, attempt_connection=False)

                if self.app.to_stop_config:
                    return

                # get wallets for the selected chain
                wallets_response: List[Dict[str, Any]] = await self._get_gateway_instance().get_wallets()
                matching_wallets: List[Dict[str, Any]] = [
                    w for w in wallets_response if w["chain"] == chain]
                wallets: List[str]
                if len(matching_wallets) < 1:
                    wallets = []
                else:
                    wallets = matching_wallets[0]['walletAddresses']

                # if the user has no wallet, ask them to select one
                if len(wallets) < 1 or chain == "near" or len(additional_prompts) != 0:
                    wallet_address, additional_prompt_values = await self._prompt_for_wallet_address(
                        chain=chain, network=network, additional_prompts=additional_prompts
                    )

                # the user has a wallet. Ask if they want to use it or create a new one.
                else:
                    # print table
                    while True:
                        use_existing_wallet: str = await self.app.prompt(
                            prompt=f"Do you want to connect to {chain}-{network} with one of your existing wallets on "
                                   f"Gateway? (Yes/No) >>> "
                        )
                        if self.app.to_stop_config:
                            return
                        if use_existing_wallet in ["Y", "y", "Yes", "yes", "N", "n", "No", "no"]:
                            break
                        self.notify(
                            "Invalid input. Please try again or exit config [CTRL + x].\n")

                    self.app.clear_input()
                    # they use an existing wallet
                    if use_existing_wallet is not None and use_existing_wallet in ["Y", "y", "Yes", "yes"]:
                        native_token: str = native_tokens[chain]
                        wallet_table: List[Dict[str, Any]] = []
                        for w in wallets:
                            balances: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                                chain, network, w, [native_token], connector
                            )
                            balance = (
                                balances['balances'].get(native_token)
                                or balances['balances']['total'].get(native_token)
                            )
                            wallet_table.append(
                                {"balance": balance, "address": w})

                        wallet_df: pd.DataFrame = build_wallet_display(
                            native_token, wallet_table)
                        self.notify(wallet_df.to_string(index=False))
                        self.app.input_field.completer.set_list_gateway_wallets_parameters(
                            wallets_response, chain)
                        additional_prompt_values = {}

                        while True:
                            wallet_address: str = await self.app.prompt(prompt="Select a gateway wallet >>> ")
                            if self.app.to_stop_config:
                                return
                            if wallet_address in wallets:
                                self.notify(
                                    f"You have selected {wallet_address}.")
                                break
                            self.notify("Error: Invalid wallet address")

                    # they want to create a new wallet even though they have other ones
                    else:
                        while True:
                            try:
                                wallet_address, additional_prompt_values = await self._prompt_for_wallet_address(
                                    chain=chain, network=network, additional_prompts=additional_prompts
                                )
                                break
                            except Exception:
                                self.notify(
                                    "Error adding wallet. Check private key.\n")

                        # display wallet balance
                        native_token: str = native_tokens[chain]
                        balances: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                            chain, network, wallet_address, [
                                native_token], connector
                        )
                        wallet_table: List[Dict[str, Any]] = [{"balance": balances['balances'].get(
                            native_token) or balances['balances']['total'].get(native_token), "address": wallet_address}]
                        wallet_df: pd.DataFrame = build_wallet_display(
                            native_token, wallet_table)
                        self.notify(wallet_df.to_string(index=False))

                self.app.clear_input()

                # write wallets to Gateway connectors settings.
                GatewayConnectionSetting.upsert_connector_spec(
                    connector_name=connector,
                    chain=chain,
                    network=network,
                    trading_type=trading_type,
                    chain_type=chain_type,
                    wallet_address=wallet_address,
                    additional_spenders=additional_spenders,
                    additional_prompt_values=additional_prompt_values,
                )
                self.notify(
                    f"The {connector} connector now uses wallet {wallet_address} on {chain}-{network}")

                # update AllConnectorSettings and fee overrides.
                AllConnectorSettings.create_connector_settings()
                AllConnectorSettings.initialize_paper_trade_settings(
                    self.client_config_map.paper_trade.paper_trade_exchanges
                )
                await refresh_trade_fees_config(self.client_config_map)

                # Reload completer here to include newly added gateway connectors
                self.app.input_field.completer = load_completer(self)

    async def _prompt_for_wallet_address(
        self,           # type: HummingbotApplication
        chain: str,
        network: str,
        additional_prompts: Dict[str, str],
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

        additional_prompt_values = {}
        if chain == "near":
            wallet_account_id: str = await self.app.prompt(
                prompt=f"Enter your {chain}-{network} account Id >>> ",
            )
            additional_prompt_values["address"] = wallet_account_id
            self.app.clear_input()
            if self.app.to_stop_config:
                return

        for field, prompt in additional_prompts.items():
            value = await self.app.prompt(prompt=prompt, is_password=True)
            self.app.clear_input()
            if self.app.to_stop_config:
                return
            additional_prompt_values[field] = value

        response: Dict[str, Any] = await self._get_gateway_instance().add_wallet(
            chain, network, wallet_private_key, **additional_prompt_values
        )
        wallet_address: str = response["address"]
        return wallet_address, additional_prompt_values

    async def _get_balance_for_exchange(self, exchange_name: str):
        gateway_connections = GatewayConnectionSetting.load()
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Updating gateway balances, please wait...")
        conf: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(
            exchange_name)
        if conf is None:
            self.notify(
                f"'{exchange_name}' is not available. You can add and review exchange with 'gateway connect'.")
        else:
            chain, network, address = (
                conf["chain"], conf["network"], conf["wallet_address"]
            )
            tokens_str = conf.get("tokens", "")
            tokens = [token.strip() for token in tokens_str.split(',')] if tokens_str else []

            connector_chain_network = [
                w for w in gateway_connections
                if w["chain"] == chain and
                w["network"] == network and
                w["connector"] == conf["connector"] and
                w["trading_type"] == conf["trading_type"]
            ]

            connector = connector_chain_network[0]['connector']
            exchange_key = f"{connector}_{chain}_{network}"

            try:
                single_ex_bal = await asyncio.wait_for(
                    self.single_balance_exc(exchange_name, self.client_config_map), network_timeout
                )

                allowance_resp = await gateway_instance.get_allowances(
                    chain, network, address, tokens, connector_chain_network[0]["connector"], fail_silently=True
                )

                rows = []
                for exchange, bals in single_ex_bal.items():
                    if exchange_key == exchange:
                        rows = []
                        for token, bal in bals.items():
                            # Handle errors in allowance_responses_list
                            if allowance_resp.get("approvals") is None:
                                allowance = Decimal("0")
                            else:
                                allowance = allowance_resp["approvals"].get(token, Decimal("0"))

                            rows.append({
                                "Symbol": token.upper(),
                                "Balance": PerformanceMetrics.smart_round(Decimal(str(bal)), 4),
                                "Allowance": PerformanceMetrics.smart_round(Decimal(str(allowance)), 4) if float(allowance) < 999999 else "999999+",

                            })

                df = pd.DataFrame(data=rows, columns=["Symbol", "Balance", "Allowance"])
                df.sort_values(by=["Symbol"], inplace=True)

                self.notify(f"\nConnector: {exchange_key}")
                self.notify(f"Wallet_Address: {address}")

                if df.empty:
                    self.notify("You have no balance on this exchange.")
                else:
                    lines = [
                        "    " + line for line in df.to_string(index=False).split("\n")
                    ]
                    self.notify("\n".join(lines))

            except asyncio.TimeoutError:
                self.notify("\nA network error prevented the balances from updating. See logs for more details.")
                raise

    async def _get_balances(self):
        network_connections = GatewayConnectionSetting.load()
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        self.notify("Updating gateway balances, please wait...")

        try:
            bal_resp = await asyncio.wait_for(
                self.all_balances_all_exc(self.client_config_map), network_timeout
            )
            allowance_tasks = []

            for conf in network_connections:
                chain, network, address = (
                    conf["chain"], conf["network"], conf["wallet_address"]
                )

                tokens_str = conf.get("tokens", "")
                tokens = [token.strip() for token in tokens_str.split(',')] if tokens_str else []

                connector_chain_network = [
                    w for w in network_connections
                    if w["chain"] == chain and
                    w["network"] == network and
                    w["connector"] == conf["connector"] and
                    w["trading_type"] == conf["trading_type"]
                ]

                allowance_resp = gateway_instance.get_allowances(
                    chain, network, address, tokens, connector_chain_network[0]["connector"], fail_silently=True
                )
                allowance_tasks.append(allowance_resp)

            # Gather balances and allowance responses asynchronously
            allowance_responses_list = await asyncio.gather(*allowance_tasks)

            for conf in network_connections:
                index = network_connections.index(conf)
                chain, network, address, connector = conf["chain"], conf["network"], conf["wallet_address"], conf["connector"]
                exchange_key = f'{connector}_{chain}_{network}'
                exchange_found = False
                for exchange, bals in bal_resp.items():
                    if exchange_key == exchange:
                        exchange_found = True
                        rows = []
                        for token, bal in bals.items():
                            # Handle errors in allowance_responses_list
                            if allowance_responses_list[index].get("approvals") is None:
                                allowance = Decimal("0")
                            else:
                                allowance = allowance_responses_list[index]["approvals"].get(token, Decimal("0"))

                            rows.append({
                                "Symbol": token.upper(),
                                "Balance": PerformanceMetrics.smart_round(Decimal(str(bal)), 4),
                                "Allowance": PerformanceMetrics.smart_round(Decimal(str(allowance)), 4) if float(allowance) < 999999 else "999999+",

                            })

                        df = pd.DataFrame(data=rows, columns=["Symbol", "Balance", "Allowance"])
                        df.sort_values(by=["Symbol"], inplace=True)

                        self.notify(f"\nConnector: {exchange_key}")
                        self.notify(f"Wallet_Address: {address}")

                        if df.empty:
                            self.notify("You have no balance and allowances on this exchange.")
                        else:
                            lines = [
                                "    " + line for line in df.to_string(index=False).split("\n")
                            ]
                            self.notify("\n".join(lines))
                if not exchange_found:
                    self.notify(f"\nConnector: {exchange_key}")
                    self.notify(f"Wallet_Address: {address}")
                    self.notify("You have no balance and allowances on this exchange.")

        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the balances and allowances from updating. See logs for more details.")
            raise

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

    async def update_exchange_balances(self, exchange_name: str, client_config_map: ClientConfigMap) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        is_gateway_markets = self.is_gateway_markets(exchange_name)
        if is_gateway_markets and exchange_name in self._market:
            del self._market[exchange_name]
        if exchange_name in self._market:
            return await self._update_balances(self._market[exchange_name])
        else:
            await Security.wait_til_decryption_done()
            api_keys = Security.api_keys(
                exchange_name) if not is_gateway_markets else {}
            return await self.add_gateway_exchange(exchange_name, client_config_map, **api_keys)

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_markets(exchange_name: str) -> bool:
        return (
            exchange_name in sorted(
                AllConnectorSettings.get_gateway_amm_connector_names().union(
                    AllConnectorSettings.get_gateway_evm_amm_lp_connector_names()
                ).union(
                    AllConnectorSettings.get_gateway_clob_connector_names()
                )
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
            available_networks: List[Dict[str, Any]
                                     ] = connector["available_networks"]
            chains: List[str] = [d['chain'] for d in available_networks]
            connector['chains'] = chains
            connectors_tiers.append(connector)
        connectors_df: pd.DataFrame = build_list_display(connectors_tiers)
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
                resp: Dict[str, Any] = await self._get_gateway_instance().approve_token(conf['chain'], conf['network'], connector_wallet[0]['wallet_address'], tokens, conf['connector'])
                transaction_hash: Optional[str] = resp.get(
                    "approval", {}).get("hash")
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
