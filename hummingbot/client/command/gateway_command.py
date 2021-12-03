#!/usr/bin/env python
import asyncio
import aiohttp
import ssl
import json
import shutil
import ruamel.yaml
import pandas as pd
from os import listdir, path
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot import cert_path, root_path
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.client.config.global_config_map import global_config_map
from typing import Dict, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayCommand:

    def gateway(self,
                option: str = None,
                key: str = None,
                value: str = None):
        if option == "create":
            safe_ensure_future(self.create_gateway())
        elif option == "list-configs":
            safe_ensure_future(self.show_gateway_connections())
        elif option == "update":
            safe_ensure_future(self.update_gateway(key, value))
        elif option == "generate-certs":
            safe_ensure_future(self._generate_certs())
        elif option == "test-connection":
            safe_ensure_future(self._test_connection())

    async def _test_connection(self):
        # test that the gateway is running
        try:
            resp = await self._api_request("get", "", {})
        except Exception as e:
            self._notify("\nUnable to ping gateway.")
            raise e

        if resp['message'] == 'ok':
            self._notify("\nSuccesfully pinged gateway.")
        else:
            self._notify("\nUnable to ping gateway.")

    async def _generate_certs(self,  # type: HummingbotApplication
                              ):
        if certs_files_exist():
            self._notify(f"Gateway SSL certification files exist in {cert_path()}.")
            self._notify("To create new certification files, please first manually delete those files.")
            return
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        while True:
            pass_phase = await self.app.prompt(prompt='Enter pass phase to generate Gateway SSL certifications  >>> ',
                                               is_password=True)
            if pass_phase is not None and len(pass_phase) > 0:
                break
            self._notify("Error: Invalid pass phase")
        create_self_sign_certs(pass_phase)
        self._notify(f"Gateway SSL certification files are created in {cert_path()}.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def _create_gateway(self):
        gateway_conf_path = path.join(root_path(), "gateway/conf")
        certificate_path = cert_path()
        log_path = path.join(root_path(), "logs")
        gateway_docker_name = "coinalpha/gateway-v2"
        gateway_container_name = "gateway-v2_container"

        if len(listdir(gateway_conf_path)) > 1:
            self.app.clear_input()
            self.placeholder_mode = True
            self.app.hide_input = True
            clear_gateway = await self.app.prompt(prompt="Gateway configurations detected. Would you like to erase? (Yes/No) >>> ")
            if clear_gateway is not None and clear_gateway in ["Y", "y", "Yes", "yes"]:
                self._notify("Erasing existing Gateway configurations...")
                shutil.move(path.join(gateway_conf_path, "samples"), "/tmp")
                shutil.rmtree(gateway_conf_path)
                shutil.move("/tmp/samples", path.join(gateway_conf_path, "samples"))
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

        if len(listdir(gateway_conf_path)) == 1:
            self._notify("Initiating Gateway configurations from sample files...")
            shutil.copytree(path.join(gateway_conf_path, "samples"), gateway_conf_path, dirs_exist_ok=True)
            self.app.clear_input()
            self.placeholder_mode = True
            self.app.hide_input = True
            # prompt for questions about infura key
            use_infura = await self.app.prompt(prompt="Would you like to connect to Ethereum network using Infura? (Yes/No) >>> ")
            yaml_parser = ruamel.yaml.YAML()
            ethereum_conf_path = path.join(gateway_conf_path, "ethereum.yml")
            if use_infura is not None and use_infura in ["Y", "y", "Yes", "yes"]:
                infura_key = await self.app.prompt(prompt="Enter your Infura API key >>> ")
                try:
                    with open(ethereum_conf_path) as stream:
                        data = yaml_parser.load(stream) or {}
                        for key in data["networks"]:
                            data["networks"][key]["nodeApiKey"] = infura_key
                        with open(ethereum_conf_path, "w+") as outfile:
                            yaml_parser.dump(data, outfile)
                except Exception as e:
                    self.logger().error("Error writing configs: %s" % (str(e),), exc_info=True)
            else:
                node_rpc = await self.app.prompt(prompt="Enter node rpc url to use to connect to Ethereum mainnet  >>> ")
                try:
                    with open(ethereum_conf_path) as stream:
                        data = yaml_parser.load(stream) or {}
                        data["networks"]["mainnet"]["nodeURL"] = node_rpc
                        with open(ethereum_conf_path, "w+") as outfile:
                            yaml_parser.dump(data, outfile)
                except Exception:
                    self.logger().error("Error updating Ethereum mainnet rpc url.")
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

        # remove existing container
        try:
            old_container = self._docker_client.containers(all=True,
                                                           filters={"name": gateway_container_name,
                                                                    "ancestor": f"{gateway_docker_name}:latest"})
            if len(old_container) >= 1:
                self._notify("Removing existing gateway container...")
                self._docker_client.remove_container(old_container[0]["Id"], force=True)
        except Exception:
            pass  # silently ignore exception

        await self._generate_certs()  # create cert if not available
        self._notify("Pulling Gateway docker image...")
        await asyncio.sleep(0.5)
        try:
            pull_logs = iter(self._docker_client.pull(gateway_docker_name, stream=True, decode=True))
            while True:
                try:
                    self.logger().info(json.dumps(next(pull_logs), indent=4))
                except StopIteration:
                    self._notify("Done pulling Gateway docker image.")
                    break
        except Exception:
            self._notify("Error pulling Gateway docker image. Try again.")
            return
        self._notify("Creating new Gateway docker container...")
        container_id = self._docker_client.create_container(image = gateway_docker_name,
                                                            name = gateway_container_name,
                                                            ports = [5000],
                                                            volumes=[gateway_conf_path, certificate_path, log_path],
                                                            host_config=self._docker_client.create_host_config(
                                                                port_bindings={5000: 5000},
                                                                binds={gateway_conf_path: {'bind': '/usr/src/app/conf/',
                                                                                           'mode': 'rw'},
                                                                       certificate_path: {'bind': '/usr/src/app/certs/',
                                                                                          'mode': 'rw'},
                                                                       log_path: {'bind': '/usr/src/app/logs/',
                                                                                  'mode': 'rw'}}))
        self._notify(f"New Gateway docker container id is {container_id['Id']}.")

    async def create_gateway(self):
        safe_ensure_future(self._create_gateway(), loop=self.ev_loop)

    async def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    async def update_gateway(self, key, value):
        safe_ensure_future(self._update_gateway(key, value), loop=self.ev_loop)

    async def show_gateway_connections(self):
        self._notify("\nTesting Gateway connections, please wait...")
        safe_ensure_future(self._show_gateway_connections(), loop=self.ev_loop)

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
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
        if method == "get":
            if len(params) > 0:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
        elif method == "post":
            response = await client.post(url, data=params)

        parsed_response = json.loads(await response.text())
        return parsed_response

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def _update_gateway(self, key, value):
        if key is not None:
            key = key.upper()
            all_keys = []

        try:
            config = await self.get_gateway_connections()
            all_keys = sorted(config)

        except Exception:
            self._notify("Gateway-api is not accessible. "
                         "Ensure gateway is up and running on the address and port specified in the global config.")
            return

        if key is None or key not in all_keys:
            self._notify(f"Specify one of {all_keys} config to update.")
            return
        elif value is None:
            self.app.clear_input()
            self.placeholder_mode = True
            self.app.hide_input = True
            while True:
                value = await self.app.prompt(prompt=f'What do you want to set {key} to?  >>> ')
                if value is not None and len(value) > 0:
                    break
                self._notify("Error: Invalid value")
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")
        if key and value:
            settings = {key: value.lower()}
            try:
                await self._api_request("post", "config/update", settings)
            except Exception:
                # silently ignore exception due to gateway restarting
                pass
            self._notify(f"\nGateway api has restarted to update {key} to {value.lower()}.")

            # the following will commented out untill gateway api is refactored to support multichain
            """try:
                settings = { key, value }
                resp = await self._api_request("post", "api/update", settings)
                if 'config' in resp.keys():
                    self._notify("\nGateway's protocol configuratios updated.")
                else:
                    self.logger().network(
                        "Error in update response",
                        exc_info=True,
                        app_warning_msg=str(resp)
                    )
                    remote_host = ':'.join([host, port])
                    self._notify(f"\nError: Updating Gateway {remote_host} configuratios failed")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    "Error updating Gateway's protocol configuratios",
                    exc_info=True,
                    app_warning_msg=str(e)
                )
                self._notify("\nError: Configrations update failed")"""

    async def get_gateway_connections(self):
        return await self._api_request("get", "config", {})

    async def _show_gateway_connections(self):
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value
        try:
            config = await self.get_gateway_connections()
            self._notify(f"\nGateway Configurations ({host}:{port}):")
            self._notify("\nCore parameters:")
            columns = ["Parameter", "  Value"]
            data = [[key, config[key]] for key in sorted(config)]
            df = pd.DataFrame(data=data, columns=columns)
            lines = ["    " + line for line in df.to_string(index=False, max_colwidth=50).split("\n")]
            self._notify("\n".join(lines))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "\nError getting Gateway's protocol settings",
                exc_info=True,
                app_warning_msg=str(e)
            )
            remote_host = ':'.join([host, port])
            self._notify(f"\nError: Connection to Gateway {remote_host} failed")
