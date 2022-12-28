#!/usr/bin/env python
import asyncio
import itertools
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager, begin_placeholder_mode
from hummingbot.client.config.config_helpers import refresh_trade_fees_config, save_to_yml
from hummingbot.client.config.security import Security
from hummingbot.client.settings import (
    CLIENT_CONFIG_PATH,
    GATEWAY_SSL_CONF_FILE,
    AllConnectorSettings,
    GatewayConnectionSetting,
)
from hummingbot.client.ui.completer import load_completer
from hummingbot.core.gateway import (
    GATEWAY_DOCKER_REPO,
    GATEWAY_DOCKER_TAG,
    GatewayPaths,
    docker_ipc,
    docker_ipc_with_generator,
    get_default_gateway_port,
    get_gateway_container_name,
    get_gateway_paths,
    is_inside_docker,
    start_gateway,
    stop_gateway,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import (
    build_config_dict_display,
    build_connector_display,
    build_connector_tokens_display,
    build_wallet_display,
    native_tokens,
    search_configs,
)
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayCommand(GatewayChainApiManager):
    def create_gateway(self):
        safe_ensure_future(self._create_gateway(), loop=self.ev_loop)

    def gateway_connect(self, connector: str = None):
        safe_ensure_future(self._gateway_connect(connector), loop=self.ev_loop)

    def gateway_start(
        self  # type: HummingbotApplication
    ):
        safe_ensure_future(start_gateway(self.client_config_map), loop=self.ev_loop)

    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    def gateway_stop(
        self  # type: HummingbotApplication
    ):
        safe_ensure_future(stop_gateway(self.client_config_map), loop=self.ev_loop)

    def gateway_connector_tokens(self, connector_chain_network: Optional[str], new_tokens: Optional[str]):
        if connector_chain_network is not None and new_tokens is not None:
            safe_ensure_future(self._update_gateway_connector_tokens(connector_chain_network, new_tokens), loop=self.ev_loop)
        else:
            safe_ensure_future(self._show_gateway_connector_tokens(connector_chain_network), loop=self.ev_loop)

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    def test_connection(self):
        safe_ensure_future(self._test_connection(), loop=self.ev_loop)

    def gateway_config(self,
                       key: Optional[str] = None,
                       value: str = None):
        if value:
            safe_ensure_future(self._update_gateway_configuration(key, value), loop=self.ev_loop)
        else:
            safe_ensure_future(self._show_gateway_configuration(key), loop=self.ev_loop)

    @staticmethod
    async def check_gateway_image(docker_repo: str, docker_tag: str) -> bool:
        image_list: List = await docker_ipc("images", name=f"{docker_repo}:{docker_tag}", quiet=True)
        return len(image_list) > 0

    async def _test_connection(self):
        # test that the gateway is running
        if await self._get_gateway_instance().ping_gateway():
            self.notify("\nSuccessfully pinged gateway.")
        else:
            self.notify("\nUnable to ping gateway.")

    async def _generate_certs(
            self,       # type: HummingbotApplication
            from_client_password: bool = False,
            bypass_source_check: bool = False
    ):

        if not is_inside_docker and not bypass_source_check:
            with begin_placeholder_mode(self):
                while True:
                    docker_check = await self.app.prompt(
                        prompt="This command is designed to generate Gateway certificates. "
                        "When you have installed Hummingbot from source, "
                        "Do you want to continue? (Yes/No) >>> ",
                    )
                    if self.app.to_stop_config:
                        return
                    if docker_check in ["Y", "y", "Yes", "yes"]:
                        break
                    if docker_check in ["N", "n", "No", "no"]:
                        return
                    self.notify("Invalid input. Please try again or exit config [CTRL + x].\n")

        cert_path: str = get_gateway_paths(self.client_config_map).local_certs_path.as_posix()
        current_path: str = self.client_config_map.certs.path
        if not GATEWAY_SSL_CONF_FILE.exists() and not bypass_source_check:
            self.notify("\nSSL configuration file not found. Please use `gateway/setup/generate_conf.sh` to generate it.")
        elif GATEWAY_SSL_CONF_FILE.exists():
            self.ssl_config_map.caCertificatePath = cert_path + "/ca_cert.pem"
            self.ssl_config_map.certificatePath = cert_path + "/server_cert.pem"
            self.ssl_config_map.keyPath = cert_path + "/server_key.pem"
            save_to_yml(GATEWAY_SSL_CONF_FILE, self.ssl_config_map)  # Update SSL config file

        if current_path != cert_path:
            self.client_config_map.certs.path = cert_path
            save_to_yml(CLIENT_CONFIG_PATH, self.client_config_map)  # Update config file

        if not from_client_password:
            if certs_files_exist(self.client_config_map):
                self.notify(f"Gateway SSL certification files exist in {cert_path}.")
                self.notify("To create new certification files, please first manually delete those files.")
                return

            with begin_placeholder_mode(self):
                while True:
                    pass_phase = await self.app.prompt(
                        prompt='Enter pass phase to generate Gateway SSL certifications  >>> ',
                        is_password=True
                    )
                    if pass_phase is not None and len(pass_phase) > 0:
                        break
                    self.notify("Error: Invalid pass phase")
        else:
            pass_phase = Security.secrets_manager.password.get_secret_value()
        create_self_sign_certs(pass_phase, self.client_config_map)
        self.notify(f"Gateway SSL certification files are created in {cert_path}.")
        self._get_gateway_instance().reload_certs(self.client_config_map)

    async def _generate_gateway_confs(
            self,       # type: HummingbotApplication
            container_id: str, conf_path: str = "/usr/src/app/conf"
    ):
        try:
            cmd: str = f"./setup/generate_conf.sh {conf_path}"
            exec_info = await docker_ipc(method_name="exec_create",
                                         container=container_id,
                                         cmd=cmd,
                                         user="hummingbot")

            await docker_ipc(method_name="exec_start",
                             exec_id=exec_info["Id"],
                             detach=True)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def _create_gateway(
        self  # type: HummingbotApplication
    ):
        if is_inside_docker:
            with begin_placeholder_mode(self):
                while True:
                    docker_check = await self.app.prompt(
                        prompt="This command is designed to automate Gateway setup when you have installed Hummingbot using Docker,"
                        " Do you want to continue?” (Yes/No) >>>"
                    )
                    if self.app.to_stop_config:
                        return
                    if docker_check in ["Y", "y", "Yes", "yes"]:
                        break
                    if docker_check in ["N", "n", "No", "no"]:
                        return
                    self.notify("Invalid input. Please try again or exit config [CTRL + x].\n")

        gateway_paths: GatewayPaths = get_gateway_paths(self.client_config_map)
        gateway_container_name: str = get_gateway_container_name(self.client_config_map)
        gateway_conf_mount_path: str = gateway_paths.mount_conf_path.as_posix()
        certificate_mount_path: str = gateway_paths.mount_certs_path.as_posix()
        logs_mount_path: str = gateway_paths.mount_logs_path.as_posix()
        gateway_port: int = get_default_gateway_port(self.client_config_map)

        # remove existing container(s)
        try:
            old_container = await docker_ipc(
                "containers",
                all=True,
                filters={"name": gateway_container_name}
            )
            for container in old_container:
                self.notify(f"Removing existing gateway container with id {container['Id']}...")
                await docker_ipc(
                    "remove_container",
                    container["Id"],
                    force=True
                )
        except Exception:
            pass  # silently ignore exception

        await self._generate_certs(from_client_password = True, bypass_source_check = True)  # create cert

        if await self.check_gateway_image(GATEWAY_DOCKER_REPO, GATEWAY_DOCKER_TAG):
            self.notify("Found Gateway docker image. No image pull needed.")
        else:
            self.notify("Pulling Gateway docker image...")
            try:
                await self.pull_gateway_docker(GATEWAY_DOCKER_REPO, GATEWAY_DOCKER_TAG)
                self.logger().info("Done pulling Gateway docker image.")
            except Exception as e:
                self.notify("Error pulling Gateway docker image. Try again.")
                self.logger().network("Error pulling Gateway docker image. Try again.",
                                      exc_info=True,
                                      app_warning_msg=str(e))
                return
        self.notify("Creating new Gateway docker container...")
        host_config: Dict[str, Any] = await docker_ipc(
            "create_host_config",
            port_bindings={15888: gateway_port},
            binds={
                gateway_conf_mount_path: {
                    "bind": "/usr/src/app/conf/",
                    "mode": "rw"
                },
                certificate_mount_path: {
                    "bind": "/usr/src/app/certs/",
                    "mode": "rw"
                },
                logs_mount_path: {
                    "bind": "/usr/src/app/logs/",
                    "mode": "rw"
                },
            }
        )
        container_info: Dict[str, str] = await docker_ipc(
            "create_container",
            image=f"{GATEWAY_DOCKER_REPO}:{GATEWAY_DOCKER_TAG}",
            name=gateway_container_name,
            ports=[15888],
            volumes=[
                gateway_conf_mount_path,
                certificate_mount_path,
                logs_mount_path
            ],
            host_config=host_config,
            environment=[f"GATEWAY_PASSPHRASE={Security.secrets_manager.password.get_secret_value()}"]
        )

        self.notify(f"New Gateway docker container id is {container_info['Id']}.")

        # Save the gateway port number, if it's not already there.
        gateway_config_map = self.client_config_map.gateway
        if gateway_config_map.gateway_api_port != gateway_port:
            gateway_config_map.gateway_api_port = gateway_port
            gateway_config_map.gateway_api_host = "localhost"
            save_to_yml(CLIENT_CONFIG_PATH, self.client_config_map)

        self._get_gateway_instance().base_url = (
            f"https://{gateway_config_map.gateway_api_host}:{gateway_config_map.gateway_api_port}"
        )
        await start_gateway(self.client_config_map)

        # create Gateway configs
        await self._generate_gateway_confs(container_id=container_info["Id"])

        self.notify("Gateway is starting, please wait a moment.")
        # wait about 30 seconds for the gateway to start
        docker_and_gateway_live = await self.ping_gateway_docker_and_api(30)
        if docker_and_gateway_live:
            self.notify("Gateway has started succesfully.")
        else:
            self.notify("Error starting Gateway container.")

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

    async def ping_gateway_docker_and_api(self, max_wait: int) -> bool:
        """
        Try to reach the docker and then the gateway API for up to max_wait seconds
        """
        now = int(time.time())
        docker_live = await self.ping_gateway_docker()
        while not docker_live:
            later = int(time.time())
            if later - now > max_wait:
                return False
            await asyncio.sleep(0.5)
            docker_live = await self.ping_gateway_docker()

        return await self.ping_gateway_api(max_wait)

    async def ping_gateway_docker(self) -> bool:
        try:
            await docker_ipc("version")
            return True
        except Exception:
            return False

    async def pull_gateway_docker(self, docker_repo: str, docker_tag: str):
        last_id = ""
        async for pull_log in docker_ipc_with_generator("pull", docker_repo, tag=docker_tag, stream=True, decode=True):
            new_id = pull_log["id"] if pull_log.get("id") else last_id
            if last_id != new_id:
                self.logger().info(f"Pull Id: {new_id}, Status: {pull_log['status']}")
                last_id = new_id

    async def _gateway_status(self):
        can_reach_docker = await self.ping_gateway_docker()
        if not can_reach_docker:
            self.notify("\nError: It looks like you do not have Docker installed or running. Gateway commands will not "
                        "work without it. Please install or start Docker and restart Hummingbot.")
            return

        if self._gateway_monitor.gateway_status is GatewayStatus.ONLINE:
            try:
                status = await self._get_gateway_instance().get_gateway_status()
                if status is None or status == []:
                    self.notify("There are currently no connectors online.")
                else:
                    self.notify(pd.DataFrame(status))
            except Exception:
                self.notify("\nError: Unable to fetch status of connected Gateway server.")
        else:
            self.notify("\nNo connection to Gateway server exists. Ensure Gateway server is running.")

    async def _update_gateway_configuration(self, key: str, value: Any):
        try:
            response = await self._get_gateway_instance().update_config(key, value)
            self.notify(response["message"])
        except Exception:
            self.notify("\nError: Gateway configuration update failed. See log file for more details.")

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
        wallet_account_id: Optional[str] = None

        with begin_placeholder_mode(self):
            gateway_connections_conf: List[Dict[str, str]] = GatewayConnectionSetting.load()
            if connector is None:
                if len(gateway_connections_conf) < 1:
                    self.notify("No existing connection.\n")
                else:
                    connector_df: pd.DataFrame = build_connector_display(gateway_connections_conf)
                    self.notify(connector_df.to_string(index=False))
            else:
                # get available networks
                connector_configs: Dict[str, Any] = await self._get_gateway_instance().get_connectors()
                connector_config: List[Dict[str, Any]] = [
                    d for d in connector_configs["connectors"] if d["name"] == connector
                ]
                if len(connector_config) < 1:
                    self.notify(f"No available blockchain networks available for the connector '{connector}'.")
                    return
                available_networks: List[Dict[str, Any]] = connector_config[0]["available_networks"]
                trading_type: str = connector_config[0]["trading_type"][0]
                additional_spenders: List[str] = connector_config[0].get("additional_spenders", [])

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
                    itertools.chain.from_iterable([d['networks'] for d in available_networks if d['chain'] == chain])
                )

                network: str
                while True:
                    self.app.input_field.completer.set_gateway_networks(networks)
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
                matching_wallets: List[Dict[str, Any]] = [w for w in wallets_response if w["chain"] == chain]
                wallets: List[str]
                if len(matching_wallets) < 1:
                    wallets = []
                else:
                    wallets = matching_wallets[0]['walletAddresses']

                # if the user has no wallet, ask them to select one
                if len(wallets) < 1 or chain == "near":
                    self.app.clear_input()
                    self.placeholder_mode = True
                    wallet_private_key = await self.app.prompt(
                        prompt=f"Enter your {chain}-{network} wallet private key >>> ",
                        is_password=True
                    )
                    self.app.clear_input()
                    if self.app.to_stop_config:
                        return

                    if chain == "near":
                        wallet_account_id: str = await self.app.prompt(
                            prompt=f"Enter your {chain}-{network} account Id >>> ",
                        )
                        self.app.clear_input()
                        if self.app.to_stop_config:
                            return

                    response: Dict[str, Any] = await self._get_gateway_instance().add_wallet(
                        chain, network, wallet_private_key, id=wallet_account_id
                    )
                    wallet_address: str = response["address"]

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
                        self.notify("Invalid input. Please try again or exit config [CTRL + x].\n")

                    self.app.clear_input()
                    # they use an existing wallet
                    if use_existing_wallet is not None and use_existing_wallet in ["Y", "y", "Yes", "yes"]:
                        native_token: str = native_tokens[chain]
                        wallet_table: List[Dict[str, Any]] = []
                        for w in wallets:
                            balances: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                                chain, network, w, [native_token]
                            )
                            wallet_table.append({"balance": balances['balances'][native_token], "address": w})

                        wallet_df: pd.DataFrame = build_wallet_display(native_token, wallet_table)
                        self.notify(wallet_df.to_string(index=False))
                        self.app.input_field.completer.set_list_gateway_wallets_parameters(wallets_response, chain)

                        while True:
                            wallet_address: str = await self.app.prompt(prompt="Select a gateway wallet >>> ")
                            if self.app.to_stop_config:
                                return
                            if wallet_address in wallets:
                                self.notify(f"You have selected {wallet_address}.")
                                break
                            self.notify("Error: Invalid wallet address")

                    # they want to create a new wallet even though they have other ones
                    else:
                        while True:
                            try:
                                wallet_private_key: str = await self.app.prompt(
                                    prompt=f"Enter your {chain}-{network} wallet private key >>> ",
                                    is_password=True
                                )
                                self.app.clear_input()
                                if self.app.to_stop_config:
                                    return

                                if chain == "near":
                                    wallet_account_id: str = await self.app.prompt(
                                        prompt=f"Enter your {chain}-{network} account Id >>> ",
                                    )
                                    self.app.clear_input()
                                    if self.app.to_stop_config:
                                        return

                                response: Dict[str, Any] = await self._get_gateway_instance().add_wallet(
                                    chain, network, wallet_private_key, id=wallet_account_id
                                )
                                wallet_address = response["address"]

                                break
                            except Exception:
                                self.notify("Error adding wallet. Check private key.\n")

                        # display wallet balance
                        native_token: str = native_tokens[chain]
                        balances: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                            chain, network, wallet_address, [native_token]
                        )
                        wallet_table: List[Dict[str, Any]] = [{"balance": balances['balances'][native_token], "address": wallet_address}]
                        wallet_df: pd.DataFrame = build_wallet_display(native_token, wallet_table)
                        self.notify(wallet_df.to_string(index=False))

                self.app.clear_input()

                # write wallets to Gateway connectors settings.
                GatewayConnectionSetting.upsert_connector_spec(connector, chain, network, trading_type, wallet_address, additional_spenders)
                self.notify(f"The {connector} connector now uses wallet {wallet_address} on {chain}-{network}")

                # update AllConnectorSettings and fee overrides.
                AllConnectorSettings.create_connector_settings()
                AllConnectorSettings.initialize_paper_trade_settings(
                    self.client_config_map.paper_trade.paper_trade_exchanges
                )
                await refresh_trade_fees_config(self.client_config_map)

                # Reload completer here to include newly added gateway connectors
                self.app.input_field.completer = load_completer(self)

    async def _show_gateway_connector_tokens(
            self,           # type: HummingbotApplication
            connector_chain_network: str = None
    ):
        """
        Display connector tokens that hummingbot will report balances for
        """
        if connector_chain_network is None:
            gateway_connections_conf: List[Dict[str, str]] = GatewayConnectionSetting.load()
            if len(gateway_connections_conf) < 1:
                self.notify("No existing connection.\n")
            else:
                connector_df: pd.DataFrame = build_connector_tokens_display(gateway_connections_conf)
                self.notify(connector_df.to_string(index=False))
        else:
            conf: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(connector_chain_network)
            if conf is not None:
                connector_df: pd.DataFrame = build_connector_tokens_display([conf])
                self.notify(connector_df.to_string(index=False))
            else:
                self.notify(f"There is no gateway connection for {connector_chain_network}.\n")

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
        conf: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(connector_chain_network)

        if conf is None:
            self.notify(f"'{connector_chain_network}' is not available. You can add and review available gateway connectors with the command 'gateway connect'.")
        else:
            GatewayConnectionSetting.upsert_connector_spec_tokens(connector_chain_network, new_tokens)
            self.notify(f"The 'balance' command will now report token balances {new_tokens} for '{connector_chain_network}'.")

    def _get_gateway_instance(
        self  # type: HummingbotApplication
    ) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        return gateway_instance
