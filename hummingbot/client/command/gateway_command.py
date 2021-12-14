#!/usr/bin/env python
import asyncio
import aiohttp
import ssl
import json
from copy import deepcopy
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import (
    build_config_namespace_keys,
    search_configs,
    build_config_dict_display
)
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot import cert_path
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.client.config.global_config_map import global_config_map
from typing import Dict, Any, TYPE_CHECKING, List
from hummingbot.client.ui.completer import load_completer
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayCommand:

    def gateway(self,
                option: str = None,
                key: str = None,
                value: str = None):
        if option == "config":
            safe_ensure_future(self._show_gateway_configuration(key), loop=self.ev_loop)
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

    async def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    async def update_gateway(self, key, value):
        safe_ensure_future(self._update_gateway(key, value), loop=self.ev_loop)

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

    async def _http_client(self, new_instance: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if new_instance:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            return aiohttp.ClientSession(connector=conn)
        else:
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
            config = await self.get_gateway_configuration()
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

    async def get_gateway_configuration(self):
        return await self._api_request("get", "config", {})

    async def _show_gateway_configuration(self, key: str):
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value
        try:
            config_dict = await self.get_gateway_configuration()
            if key is not None:
                config_dict = search_configs(config_dict, key, ignore_case=True)
            self._notify(f"\nGateway Configurations ({host}:{port}):")
            lines = []
            build_config_dict_display(lines, config_dict)
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

    def format_config_dict(self, lines: List[str], config_dict: Dict[str, Any], level: int):
        prefix: str = "  " * level
        for k, v in config_dict.items():
            if isinstance(v, Dict):
                lines.append(f"{prefix}{k}:")
                self.format_config_dict(lines, v, level + 1)
            else:
                lines.append(f"{prefix}{k}: {v}")

    async def fetch_gateway_config_key_list(self):
        # pool = concurrent.futures.ThreadPoolExecutor()
        # result = pool.submit(asyncio.run, self._api_request("get", "config", {}, True)).result()
        config = await self.get_gateway_configuration()
        build_config_namespace_keys(self.gateway_config_keys, config)
        self.app.input_field.completer = load_completer(self)

    def _build_gateway_config_key_list(self, keys: List[str], config_dict: Dict[str, Any], prefix: str):
        for k, v in config_dict.items():
            keys.append(f"{prefix}{k}")
            if isinstance(v, Dict):
                self._build_gateway_config_key_list(keys, v, f"{prefix}{k}.")

    def _filter_gateway_configs(self, config_dict: Dict[str, Any], key: str) -> Dict[str, Any]:
        key_parts = key.split(".")
        result: Dict[str, Any] = {}
        if key_parts[0] in config_dict:
            result = {key_parts[0]: config_dict[key_parts[0]]}
        result_val = result[key_parts[0]]
        for key_part in key_parts[1:]:
            if isinstance(result_val, Dict) and key_part in result_val:
                temp = deepcopy(result_val[key_part])
                result_val.clear()
                result_val[key_part] = temp
                result_val = result_val[key_part]
        return result
