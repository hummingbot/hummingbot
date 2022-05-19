#!/usr/bin/env python
import aiohttp
import asyncio
from contextlib import contextmanager
import docker
import itertools
import json
import pandas as pd
from typing import (
    Dict,
    Any,
    TYPE_CHECKING,
    List,
    Generator,
)

from hummingbot.client.settings import (
    GATEWAY_CONNECTORS,
    GLOBAL_CONFIG_PATH,
    GatewayConnectionSetting
)
from hummingbot.core.gateway import (
    docker_ipc,
    docker_ipc_with_generator,
    get_gateway_container_name,
    get_gateway_paths,
    GATEWAY_DOCKER_REPO,
    GATEWAY_DOCKER_TAG,
    GatewayPaths,
    get_default_gateway_port,
    start_gateway,
    stop_gateway
)
from hummingbot.core.gateway.status_monitor import Status
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import (
    search_configs,
    build_config_dict_display,
    build_connector_display,
    build_wallet_display,
    native_tokens,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot.client.config.config_helpers import (
    save_to_yml,
    refresh_trade_fees_config,
)
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.ui.completer import load_completer

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


@contextmanager
def begin_placeholder_mode(hb: "HummingbotApplication") -> Generator["HummingbotApplication", None, None]:
    hb.app.clear_input()
    hb.placeholder_mode = True
    hb.app.hide_input = True
    try:
        yield hb
    finally:
        hb.app.to_stop_config = False
        hb.placeholder_mode = False
        hb.app.hide_input = False
        hb.app.change_prompt(prompt=">>> ")


class GatewayCommand:
    def create_gateway(self):
        safe_ensure_future(self._create_gateway(), loop=self.ev_loop)

    def gateway_connect(self, connector: str = None):
        safe_ensure_future(self._gateway_connect(connector), loop=self.ev_loop)

    def gateway_start(self):
        safe_ensure_future(start_gateway(), loop=self.ev_loop)

    def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    def gateway_stop(self):
        safe_ensure_future(stop_gateway(), loop=self.ev_loop)

    def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    def test_connection(self):
        safe_ensure_future(self._test_connection(), loop=self.ev_loop)

    def gateway_config(self,
                       key: List[str],
                       value: str = None):
        if value:
            safe_ensure_future(self._update_gateway_configuration(key[0], value), loop=self.ev_loop)
        else:
            safe_ensure_future(self._show_gateway_configuration(key[0]), loop=self.ev_loop)

    @staticmethod
    async def check_gateway_image(docker_repo: str, docker_tag: str) -> bool:
        image_list: List = await docker_ipc("images", name=f"{docker_repo}:{docker_tag}", quiet=True)
        return len(image_list) > 0

    async def _test_connection(self):
        # test that the gateway is running
        if await GatewayHttpClient.get_instance().ping_gateway():
            self.notify("\nSuccesfully pinged gateway.")
        else:
            self.notify("\nUnable to ping gateway.")

    async def _generate_certs(
            self,       # type: HummingbotApplication
            from_client_password: bool = False
    ):
        cert_path: str = get_gateway_paths().local_certs_path.as_posix()
        if not from_client_password:
            if certs_files_exist():
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
            pass_phase = Security.password
        create_self_sign_certs(pass_phase)
        self.notify(f"Gateway SSL certification files are created in {cert_path}.")
        GatewayHttpClient.get_instance().reload_certs()

    async def _generate_gateway_confs(
            self,       # type: HummingbotApplication
            container_id: str, conf_path: str = "/usr/src/app/conf"
    ):
        with begin_placeholder_mode(self):
            while True:
                node_api_key: str = await self.app.prompt(prompt="Enter Infura API Key (required for Ethereum node, "
                                                          "if you do not have one, make an account at infura.io):  >>> ")
                self.app.clear_input()
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                try:
                    # Verifies that the Infura API Key/Project ID is valid by sending a request
                    async with aiohttp.ClientSession() as tmp_client:
                        headers = {"Content-Type": "application/json"}
                        data = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_blockNumber",
                            "params": []
                        }
                        try:
                            resp = await tmp_client.post(url=f"https://mainnet.infura.io/v3/{node_api_key}",
                                                         data=json.dumps(data),
                                                         headers=headers)
                            if resp.status != 200:
                                self.notify("Error occured verifying Infura Node API Key. Please check your API Key and try again.")
                                continue
                        except Exception:
                            raise

                    exec_info = await docker_ipc(method_name="exec_create",
                                                 container=container_id,
                                                 cmd=f"./setup/generate_conf.sh {conf_path} {node_api_key}",
                                                 user="hummingbot")

                    await docker_ipc(method_name="exec_start",
                                     exec_id=exec_info["Id"],
                                     detach=True)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception:
                    raise

    async def _create_gateway(self):
        gateway_paths: GatewayPaths = get_gateway_paths()
        gateway_container_name: str = get_gateway_container_name()
        gateway_conf_mount_path: str = gateway_paths.mount_conf_path.as_posix()
        certificate_mount_path: str = gateway_paths.mount_certs_path.as_posix()
        logs_mount_path: str = gateway_paths.mount_logs_path.as_posix()
        gateway_port: int = get_default_gateway_port()

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

        await self._generate_certs(from_client_password=True)  # create cert

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
            port_bindings={5000: gateway_port},
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
            ports=[5000],
            volumes=[
                gateway_conf_mount_path,
                certificate_mount_path,
                logs_mount_path
            ],
            host_config=host_config,
            environment=[f"GATEWAY_PASSPHRASE={Security.password}"]
        )

        self.notify(f"New Gateway docker container id is {container_info['Id']}.")

        # Save the gateway port number, if it's not already there.
        if global_config_map.get("gateway_api_port").value != gateway_port:
            global_config_map["gateway_api_port"].value = gateway_port
            global_config_map["gateway_api_host"].value = "localhost"
            save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)

        GatewayHttpClient.get_instance().base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                                                    f"{global_config_map['gateway_api_port'].value}"
        await start_gateway()

        # create Gateway configs
        await self._generate_gateway_confs(container_id=container_info["Id"])

        # Restarts the Gateway container to ensure that Gateway server reloads new configs
        try:
            await docker_ipc(method_name="restart",
                             container=container_info["Id"])
        except docker.errors.APIError as e:
            self.notify(f"Error restarting Gateway container. Error: {e}")

        self.notify(f"Loaded new configs into Gateway container {container_info['Id']}")

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

        if self._gateway_monitor.current_status == Status.ONLINE:
            try:
                status = await GatewayHttpClient.get_instance().get_gateway_status()
                self.notify(pd.DataFrame(status))
            except Exception:
                self.notify("\nError: Unable to fetch status of connected Gateway server.")
        else:
            self.notify("\nNo connection to Gateway server exists. Ensure Gateway server is running.")

    async def _update_gateway_configuration(self, key: str, value: Any):
        try:
            response = await GatewayHttpClient.get_instance().update_config(key, value)
            self.notify(response["message"])
            await self._gateway_monitor.update_gateway_config_key_list()
        except Exception:
            self.notify("\nError: Gateway configuration update failed. See log file for more details.")

    async def _show_gateway_configuration(self, key: str):
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value
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
            gateway_connections_conf: List[Dict[str, str]] = GatewayConnectionSetting.load()
            if connector is None:
                if len(gateway_connections_conf) < 1:
                    self.notify("No existing connection.\n")
                else:
                    connector_df: pd.DataFrame = build_connector_display(gateway_connections_conf)
                    self.notify(connector_df.to_string(index=False))
            else:
                # get available networks
                connector_configs: Dict[str, Any] = await GatewayHttpClient.get_instance().get_connectors()
                connector_config: List[Dict[str, Any]] = [
                    d for d in connector_configs["connectors"] if d["name"] == connector
                ]
                if len(connector_config) < 1:
                    self.notify(f"No available blockchain networks available for the connector '{connector}'.")
                    return
                available_networks: List[Dict[str, Any]] = connector_config[0]["available_networks"]
                trading_type: str = connector_config[0]["trading_type"][0]

                # ask user to select a chain. Automatically select if there is only one.
                chains: List[str] = [d['chain'] for d in available_networks]
                chain: str
                if len(chains) == 1:
                    chain = chains[0]
                else:
                    # chains as options
                    while True:
                        chain = await self.app.prompt(
                            prompt=f"Which chain do you want {connector} to connect to?({', '.join(chains)}) >>> "
                        )
                        if self.app.to_stop_config:
                            self.app.to_stop_config = False
                            return

                        if chain in GATEWAY_CONNECTORS:
                            break
                        self.notify(f"{chain} chain not supported.\n")

                # ask user to select a network. Automatically select if there is only one.
                networks: List[str] = list(
                    itertools.chain.from_iterable([d['networks'] for d in available_networks if d['chain'] == chain])
                )
                network: str

                if len(networks) == 1:
                    network = networks[0]
                else:
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

                # get wallets for the selected chain
                wallets_response: List[Dict[str, Any]] = await GatewayHttpClient.get_instance().get_wallets()
                matching_wallets: List[Dict[str, Any]] = [w for w in wallets_response if w["chain"] == chain]
                wallets: List[str]
                if len(matching_wallets) < 1:
                    wallets = []
                else:
                    wallets = matching_wallets[0]['walletAddresses']

                # if the user has no wallet, ask them to select one
                if len(wallets) < 1:
                    self.app.clear_input()
                    self.placeholder_mode = True
                    wallet_private_key = await self.app.prompt(
                        prompt=f"Enter your {chain}-{network} wallet private key >>> ",
                        is_password=True
                    )
                    self.app.clear_input()
                    if self.app.to_stop_config:
                        return
                    response: Dict[str, Any] = await GatewayHttpClient.get_instance().add_wallet(
                        chain, network, wallet_private_key
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
                            balances: Dict[str, Any] = await GatewayHttpClient.get_instance().get_balances(
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
                                self.notify(f"You have selected {wallet_address}")
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

                                response: Dict[str, Any] = await GatewayHttpClient.get_instance().add_wallet(
                                    chain, network, wallet_private_key
                                )
                                wallet_address = response["address"]
                                break
                            except Exception:
                                self.notify("Error adding wallet. Check private key.\n")

                self.app.clear_input()

                # write wallets to Gateway connectors settings.
                GatewayConnectionSetting.upsert_connector_spec(connector, chain, network, trading_type, wallet_address)
                self.notify(f"The {connector} connector now uses wallet {wallet_address} on {chain}-{network}")

                # update AllConnectorSettings and fee overrides.
                AllConnectorSettings.create_connector_settings()
                AllConnectorSettings.initialize_paper_trade_settings(global_config_map.get("paper_trade_exchanges").value)
                await refresh_trade_fees_config()

                # Reload completer here to include newly added gateway connectors
                self.app.input_field.completer = load_completer(self)
