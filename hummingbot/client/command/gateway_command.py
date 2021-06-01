#!/usr/bin/env python
import asyncio
import aiohttp
import ssl
import json
import pandas as pd
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot import cert_path
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
        if option == "list-configs":
            safe_ensure_future(self.show_gateway_connections())
        elif option == "update":
            safe_ensure_future(self.update_gateway(key, value))
        elif option == "generate_certs":
            safe_ensure_future(self._generate_certs(key, value), loop=self.ev_loop)

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
        if key is None:
            self._notify("Specify a parameter to update.")
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
            settings = {key: value}
            await self._api_request("post", "api/update", settings)
            self._notify(f"\nGateway api has restarted to update {key} to {value}.")

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

    async def _show_gateway_connections(self):
        self.placeholder_mode = True
        self.app.hide_input = True
        self._shared_client = None
        to_configure = True
        resp = None
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value

        if to_configure:
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            try:
                resp = await self._api_request("get", "api", {})
                status = resp["status"]
                if status:
                    config = resp["config"]
                    self._notify(f"\nGateway Configurations ({host}:{port}):")
                    self._notify("\nCore parameters:")
                    columns = ["Parameter", "  Value"]
                    core_data = data = [[key, config['CORE'][key]] for key in sorted(config['CORE'])]
                    core_df = pd.DataFrame(data=core_data, columns=columns)
                    lines = ["    " + line for line in core_df.to_string(index=False, max_colwidth=50).split("\n")]
                    self._notify("\n".join(lines))
                    self._notify("\nOther parameters:")
                    data = [[key, config[key]] for key in sorted(config) if key not in ['CORE']]
                    df = pd.DataFrame(data=data, columns=columns)
                    lines = ["    " + line for line in df.to_string(index=False, max_colwidth=50).split("\n")]
                    self._notify("\n".join(lines))
                else:
                    self._notify("\nError: Invalid return result")
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

        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
