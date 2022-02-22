#!/usr/bin/env python
import asyncio
import aiohttp
import itertools
import json
import pandas as pd
import ssl
import subprocess

from os import path
from typing import (
    Dict,
    Any,
    TYPE_CHECKING,
    List,
    Optional,
)

from hummingbot import root_path
from hummingbot.core.gateway import (
    docker_ipc,
    docker_ipc_with_generator,
    get_gateway_container_name,
    get_gateway_paths,
    GATEWAY_DOCKER_REPO,
    GATEWAY_DOCKER_TAG,
    GatewayPaths,
)
from hummingbot.client.config.config_helpers import load_yml_into_dict, save_yml_from_dict
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import (
    build_config_namespace_keys,
    search_configs,
    build_config_dict_display,
    build_connector_display,
    build_wallet_display,
    native_tokens,
    upsert_connection
)
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot.client.settings import (
    CONF_FILE_PATH,
    AllConnectorSettings,
)
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.ui.completer import load_completer

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayCommand:
    def gateway(self,
                option: str = None,
                key: str = None,
                value: str = None):
        if option == "create":
            safe_ensure_future(self.create_gateway())
        elif option == "status":
            safe_ensure_future(self.gateway_status())
        elif option == "config":
            if value:
                safe_ensure_future(self._update_gateway_configuration(key, value), loop=self.ev_loop)
            else:
                safe_ensure_future(self._show_gateway_configuration(key), loop=self.ev_loop)
        elif option == "connect":
            safe_ensure_future(self._connect(key))
        elif option == "test-connection":
            safe_ensure_future(self._test_connection())
        elif option == "start":
            safe_ensure_future(self._start_gateway())
        elif option == "stop":
            safe_ensure_future(self._stop_gateway())
        elif option == "generate-certs":
            safe_ensure_future(self._generate_certs())

    @staticmethod
    async def check_gateway_image(docker_repo: str, docker_tag: str) -> bool:
        image_list: List = await docker_ipc("images", name=f"{docker_repo}:{docker_tag}", quiet=True)
        return len(image_list) > 0

    async def _verify_ssl_conf(self):
        if not certs_files_exist():
            raise ValueError("Please run `gateway generate_certs` to generate the necessary .pem files.")

        gateway_conf_path: str = get_gateway_paths().local_conf_path.as_posix()
        SSL_FILENAME = "ssl.yml"

        ssl_yml_file_path = f"{gateway_conf_path}/{SSL_FILENAME}"

        if path.isfile(ssl_yml_file_path):
            conf_dict = await load_yml_into_dict(yml_path=ssl_yml_file_path)
        else:
            ssl_template_path = f"{path.dirname(__file__)}/../../../gateway/src/templates/{SSL_FILENAME}"
            conf_dict = await load_yml_into_dict(yml_path=ssl_template_path)

        self.placeholder_mode = True
        self.app.hide_input = True

        self.notify(f"=== Please verify configs for {ssl_yml_file_path} file. ===")

        for conf_key, path_value in conf_dict.items():
            ack: str = await self.app.prompt(prompt=f"Is {path_value} the correct path to {conf_key} ? (Yes/No) >>> ")
            if ack.strip().lower() not in ["y", "yes"]:
                new_path: str = await self.app.prompt(prompt=f"Enter the new path to {conf_key} >>> ")
                conf_dict[conf_key] = new_path
                path_value = new_path

        await save_yml_from_dict(yml_path=ssl_yml_file_path, conf_dict=conf_dict)

        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
        return True

    async def _start_gateway(self):
        try:
            response = await docker_ipc(
                "containers",
                all=True,
                filters={"name": get_gateway_container_name()}
            )
            if len(response) == 0:
                raise ValueError(f"Gateway container {get_gateway_container_name()} not found. ")

            container_info = response[0]
            if container_info["State"] == "running":
                self.notify(f"Gateway container {container_info['Id']} already running.")
                return

            await self._verify_ssl_conf()

            await docker_ipc(
                "start",
                container=container_info["Id"]
            )
            self.notify(f"Gateway container {container_info['Id']} has started.")
        except Exception as e:
            self.notify(f"Error occurred starting Gateway container. {e}")

    async def _stop_gateway(self):
        try:
            response = await docker_ipc(
                "containers",
                all=True,
                filters={"name": get_gateway_container_name()}
            )
            if len(response) == 0:
                raise ValueError(f"Gateway container {get_gateway_container_name()} not found.")

            container_info = response[0]
            if container_info["State"] != "running":
                self.notify(f"Gateway container {container_info['Id']} not running.")
                return

            await docker_ipc(
                "stop",
                container=container_info["Id"],
            )
            self.notify(f"Gateway container {container_info['Id']} successfully stopped.")
        except Exception as e:
            self.notify(f"Error occurred stopping Gateway container. {e}")

    async def _test_connection(self):
        # test that the gateway is running
        try:
            resp = await self._api_request("get", "", {}, fail_silently = True)
        except Exception as e:
            self.notify("\nUnable to ping gateway.")
            raise e

        if resp is not None and resp.get('message', None) == 'ok' or resp.get('status', None) == 'ok':
            self.notify("\nSuccesfully pinged gateway.")
        else:
            self.notify("\nUnable to ping gateway.")

    async def _generate_certs(self,  # type: HummingbotApplication
                              from_client_password: bool = False
                              ):
        cert_path: str = get_gateway_paths().local_certs_path.as_posix()
        if not from_client_password:
            if certs_files_exist():
                self.notify(f"Gateway SSL certification files exist in {cert_path}.")
                self.notify("To create new certification files, please first manually delete those files.")
                return
            self.app.clear_input()
            self.placeholder_mode = True
            self.app.hide_input = True
            while True:
                pass_phase = await self.app.prompt(prompt='Enter pass phase to generate Gateway SSL certifications  >>> ',
                                                   is_password=True)
                if pass_phase is not None and len(pass_phase) > 0:
                    break
                self.notify("Error: Invalid pass phase")
        else:
            pass_phase = Security.password
        create_self_sign_certs(pass_phase)
        self.notify(f"Gateway SSL certification files are created in {cert_path}.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def _generate_gateway_confs(self, conf_path: str):

        GENERATE_CONF_SCRIPT = path.join(root_path(), "gateway/setup/generate_conf.sh")

        eth_conf_path = f"{conf_path}/ethereum.yml"

        # Generates all the necessary gateway conf
        subprocess.check_call([GENERATE_CONF_SCRIPT, conf_path],
                              stdout=subprocess.DEVNULL)
        self.notify(f"Gateway Configuration files are create in {conf_path}.")

        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True

        node_api_key: str = await self.app.prompt(prompt="Enter Infura API Key (required for Ethereum node, if you do not have one, make an account at infura.io):  >>> ")

        ethereum_conf = await load_yml_into_dict(yml_path=eth_conf_path)
        ethereum_conf["nodeAPIKey"] = node_api_key
        await save_yml_from_dict(yml_path=eth_conf_path, conf_dict=ethereum_conf)

        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def _create_gateway(self):
        gateway_paths: GatewayPaths = get_gateway_paths()
        gateway_container_name: str = get_gateway_container_name()
        gateway_conf_mount_path: str = gateway_paths.mount_conf_path.as_posix()
        certificate_mount_path: str = gateway_paths.mount_certs_path.as_posix()
        logs_mount_path: str = gateway_paths.mount_logs_path.as_posix()

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
        await self._generate_gateway_confs(conf_path=gateway_conf_mount_path)  # create Gateway configs

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
            port_bindings={5000: 5000},
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

        await self._start_gateway()

    async def pull_gateway_docker(self, docker_repo: str, docker_tag: str):
        last_id = ""
        async for pull_log in docker_ipc_with_generator("pull", docker_repo, tag=docker_tag, stream=True, decode=True):
            new_id = pull_log["id"] if pull_log.get("id") else last_id
            if last_id != new_id:
                self.logger().info(f"Pull Id: {new_id}, Status: {pull_log['status']}")
                last_id = new_id

    async def _gateway_status(self):
        if self._gateway_monitor.network_status == NetworkStatus.CONNECTED:
            try:
                status = await self._gateway_monitor.get_gateway_status()
                self.notify(pd.DataFrame(status))
            except Exception:
                self.notify("\nError: Unable to fetch status of connected Gateway server.")
        else:
            self.notify("\nNo connection to Gateway server exists. Ensure Gateway server is running.")

    async def create_gateway(self):
        safe_ensure_future(self._create_gateway(), loop=self.ev_loop)

    async def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {},
                           fail_silently: bool = False) -> Optional[Dict[str, Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = await self._http_client()

        parsed_response = {}
        try:
            if method == "get":
                if len(params) > 0:
                    response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method == "post":
                response = await client.post(url, json=params)
            parsed_response = json.loads(await response.text())
            if response.status != 200:
                if "error" in parsed_response:
                    err_msg = f"Error on {method.upper()} Error: {parsed_response['error']}"
                else:
                    err_msg = f"Error on {method.upper()} Error: {parsed_response}"
                    self.logger().error(
                        err_msg,
                        exc_info=True
                    )
                    raise Exception(err_msg)
        except Exception as e:
            if not fail_silently:
                raise e

        return parsed_response

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        gateway_paths: GatewayPaths = get_gateway_paths()
        gateway_ca_cert_path = f"{gateway_paths.local_certs_path.as_posix()}/ca_cert.pem"
        gateway_client_cert_path = f"{gateway_paths.local_certs_path.as_posix()}/client_cert.pem"
        gateway_client_key_path = f"{gateway_paths.local_certs_path.as_posix()}/client_key.pem"

        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=gateway_ca_cert_path)
            ssl_ctx.load_cert_chain(gateway_client_cert_path, gateway_client_key_path)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def _update_gateway_configuration(self, key: str, value: Any):
        data = {
            "configPath": key,
            "configValue": value
        }
        try:
            response = await self._api_request("post", "config/update", data)
            self.notify(response["message"])
        except Exception:
            self.notify("\nError: Gateway configuration update failed. See log file for more details.")

    async def get_gateway_configuration(self):
        return await self._api_request("get", "config", {})

    async def _show_gateway_configuration(self, key: str):
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value
        try:
            config_dict = await self.get_gateway_configuration()
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

    async def get_gateway_connectors(self):
        return await self._api_request("get", "connectors", {})

    async def _connect(self, connector: str = None):
        # it is possible that gateway_connections.json does not exist
        connections_fp = path.realpath(path.join(CONF_FILE_PATH, "gateway_connections.json"))
        if path.exists(connections_fp):
            with open(connections_fp) as f:
                connections = json.loads(f.read())
        else:
            connections = []

        if connector is None:
            if connections == []:
                self.notify("No existing connection.\n")
            else:
                connector_df = build_connector_display(connections)
                self.notify(connector_df.to_string(index=False))

        else:
            # get available networks
            connector_configs = await self.get_gateway_connectors()
            available_networks = [d["available_networks"] for d in connector_configs["connectors"] if d["name"] == connector]

            # ask user to select a chain. Automatically select if there is only one.
            chains = [d[0]['chain'] for d in available_networks]
            if len(chains) == 1:
                chain = chains[0]
            else:
                # chains as options
                self.app.clear_input()
                self.placeholder_mode = True
                chain = await self.app.prompt(prompt=f"Which chain do you want {connector} to connect to?({', '.join(chains)}) >>> ")

            # ask user to select a network. Automatically select if there is only one.
            networks = list(itertools.chain.from_iterable([d[0]['networks'] for d in available_networks if d[0]['chain'] == chain]))

            if len(networks) == 1:
                network = networks[0]
            else:
                while True:
                    self.app.clear_input()
                    self.placeholder_mode = True
                    self.app.input_field.completer.set_gateway_networks(networks)
                    network = await self.app.prompt(prompt=f"Which network do you want {connector} to connect to? ({', '.join(networks)}) >>> ")
                    if network in networks:
                        break
                    self.notify("Error: Invalid network")

            # get wallets for the selected chain
            response = await self._api_request("get", "wallet", {})
            wallets = [w for w in response if w["chain"] == chain]
            if len(wallets) < 1:
                wallets = []
            else:
                wallets = wallets[0]['walletAddresses']

            # if the user has no wallet, ask them to select one
            if len(wallets) < 1:
                self.app.clear_input()
                self.placeholder_mode = True
                new_wallet = await self.app.prompt(prompt=f"Enter your {chain}-{network} wallet private key >>> ")
                response = await self._api_request("post" "wallet/add", {"chain": chain, "network": network, "privateKey": new_wallet})

                wallet = response.address

            # the user has a wallet. Ask if they want to use it or create a new one.
            else:
                # print table
                self.app.clear_input()
                self.placeholder_mode = True
                use_existing_wallet = await self.app.prompt(prompt=f"Do you want to connect to {chain}-{network} with one of your existing wallets on Gateway? (Yes/No) >>> ")

                self.app.clear_input()
                # they use an existing wallet
                if use_existing_wallet is not None and use_existing_wallet in ["Y", "y", "Yes", "yes"]:
                    native_token = native_tokens[chain]
                    wallet_table = []
                    for w in wallets:
                        balances = await self._api_request("post", "network/balances", {"chain": chain, "network": network, "address": w, "tokenSymbols": [native_token]})
                        wallet_table.append({"balance": balances['balances'][native_token], "address": w})

                    wallet_df = build_wallet_display(native_token, wallet_table)
                    self.notify(wallet_df.to_string(index=False))
                    self.app.input_field.completer.set_list_gateway_connection_wallets_parameters(connector, chain, network)

                    while True:
                        self.placeholder_mode = True

                        wallet = await self.app.prompt(prompt="Select a gateway wallet >>> ")
                        if wallet in wallets:
                            self.notify(f"You have selected {wallet}")
                            break
                        self.notify("Error: Invalid wallet address")

                # they want to create a new wallet even though they have other ones
                else:
                    self.placeholder_mode = True
                    new_wallet = await self.app.prompt(prompt=f"Enter your {chain}-{network} wallet private key >>> ")
                    response = await self._api_request("post" "wallet/add", {"chain": chain, "network": network, "privateKey": new_wallet})

                    wallet = response.address

            # write wallets to json
            with open(connections_fp, "w+") as outfile:
                upsert_connection(connections, connector, chain, network, wallet)
                json.dump(connections, outfile)
                self.notify(f"The {connector} connector now uses wallet {wallet} on {chain}-{network}")

            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")

            # update AllConnectorSettings
            AllConnectorSettings.create_connector_settings()

            # Reload completer here to include newly added gateway connectors
            self.app.input_field.completer = load_completer(self)

    async def fetch_gateway_config_key_list(self):
        config = await self.get_gateway_configuration()
        build_config_namespace_keys(self.gateway_config_keys, config)
        self.app.input_field.completer = load_completer(self)
