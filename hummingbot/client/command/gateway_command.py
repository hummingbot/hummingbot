#!/usr/bin/env python
import asyncio
import aiohttp
import ssl
import json
import pandas as pd
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.client.config.global_config_map import global_config_map
from typing import Dict, Any


class GatewayCommand:

    def gateway(self, option: str):
        if option is None:
            safe_ensure_future(self.show_gateway_connections())
        elif option == "update":
            safe_ensure_future(self.update_gateway())

    async def update_gateway(self):
        safe_ensure_future(self._update_gateway(), loop=self.ev_loop)

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
        if response.status != 200:
            err_msg = ""
            if "error" in parsed_response:
                err_msg = f" Message: {parsed_response['error']}"
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.{err_msg}")
        if "error" in parsed_response:
            raise Exception(f"Error: {parsed_response['error']}")

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

    async def _update_gateway(self):
        self.placeholder_mode = True
        self.app.hide_input = True
        self._shared_client = None
        to_configure = True
        resp = None
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value

        answer = await self.app.prompt(prompt="Would you like to update the Gateway's protocol settings (Yes/No)? >>> ")
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        if answer.lower() not in ("yes", "y"):
            to_configure = False

        if to_configure:
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            try:
                settings = {
                    "ethereum_rpc_url": global_config_map['ethereum_rpc_url'].value,
                    "ethereum_chain_name": global_config_map['ethereum_chain_name'].value,
                    "terra_chain_name": global_config_map['terra_chain_name'].value,
                    "client_id": global_config_map['client_id'].value
                }
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
                self._notify("\nError: Configrations update failed")

        self.app.hide_input = False
        self.placeholder_mode = False
        self.app.change_prompt(prompt=">>> ")

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
                    columns = ["Key", "  Value"]
                    data = [[key, config[key]] for key in sorted(config) if key not in ['UPDATED']]
                    df = pd.DataFrame(data=data, columns=columns)
                    self._notify(f"\nGateway Configurations ({host}:{port}):")
                    lines = ["    " + line for line in df.to_string(index=False).split("\n")]
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
