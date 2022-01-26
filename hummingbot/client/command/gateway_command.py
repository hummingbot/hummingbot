#!/usr/bin/env python
import asyncio
import aiohttp
import ssl
import json
import pandas as pd
from os import getenv
from hummingbot.core.network_iterator import NetworkStatus
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
from hummingbot.client.config.security import Security
from typing import Dict, Any, TYPE_CHECKING
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
                              from_client_password: bool = False
                              ):
        if not from_client_password:
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
        else:
            pass_phase = Security.password
        create_self_sign_certs(pass_phase)
        self._notify(f"Gateway SSL certification files are created in {cert_path()}.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def _create_gateway(self):
        external_cert_path: str = getenv("CERTS_FOLDER")
        external_gateway_conf_path: str = getenv("GATEWAY_CONF_FOLDER")
        external_logs_path: str = getenv("LOGS_FOLDER")
        if external_cert_path is None or external_gateway_conf_path is None or external_logs_path is None:
            return

        docker_repo = "coinalpha/hummingbot"
        gateway_container_name = "gateway-v2_container"

        # remove existing container(s)
        try:
            old_container = await self.docker_ipc(("containers", {"all": True, "filters": {"name": gateway_container_name}}))
            for container in old_container:
                self._notify(f"Removing existing gateway container with id {container['Id']}...")
                await self.docker_ipc(("remove_container", [container["Id"], {"force": True}]))
        except Exception:
            pass  # silently ignore exception

        await self._generate_certs(from_client_password=True)  # create cert
        self._notify("Pulling Gateway docker image...")
        try:
            await self.pull_gateway_docker(docker_repo)
            self.logger().info("Done pulling Gateway docker image.")
        except Exception as e:
            self._notify("Error pulling Gateway docker image. Try again.")
            self.logger().network("Error pulling Gateway docker image. Try again.",
                                  exc_info=True,
                                  app_warning_msg=str(e))
            return
        self._notify("Creating new Gateway docker container...")
        host_config = await self.docker_ipc(("create_host_config",
                                             {
                                                 "port_bindings": {5000: 5000},
                                                 "binds": {
                                                     external_gateway_conf_path: {
                                                         "bind": "/usr/src/app/conf/",
                                                         "mode": "rw"
                                                     },
                                                     external_cert_path: {
                                                         "bind": "/usr/src/app/certs/",
                                                         "mode": "rw"
                                                     },
                                                     external_logs_path: {
                                                         "bind": "/usr/src/app/logs/",
                                                         "mode": "rw"
                                                     },
                                                 },
                                             }))
        container_id = await self.docker_ipc(("create_container",
                                              {
                                                  "image": f"{docker_repo}:gateway-v2",
                                                  "name": gateway_container_name,
                                                  "ports": [5000],
                                                  "volumes": [
                                                      external_gateway_conf_path,
                                                      external_cert_path,
                                                      external_logs_path
                                                  ],
                                                  "host_config": host_config
                                              }))
        self._notify(f"New Gateway docker container id is {container_id['Id']}.")

    async def pull_gateway_docker(self, docker_repo):
        last_id = ""
        pull_generator = self.docker_ipc_with_generator(("pull",
                                                         [docker_repo, {"tag": "gateway-v2", "stream": True, "decode": True}]))
        async for pull_log in pull_generator:
            new_id = pull_log["id"] if pull_log.get("id") else last_id
            if last_id != new_id:
                self.logger().info(f"Pull Id: {new_id}, Status: {pull_log['status']}")
                last_id = new_id

    async def _gateway_status(self):
        if self._gateway_monitor.network_status == NetworkStatus.CONNECTED:
            try:
                status = await self._gateway_monitor.get_gateway_status()
                self._notify(pd.DataFrame(status))
            except Exception:
                self._notify("\nError: Unable to fetch status of connected Gateway server.")
        else:
            self._notify("\nNo connection to Gateway server exists. Ensure Gateway server is running.")

    async def create_gateway(self):
        safe_ensure_future(self._create_gateway(), loop=self.ev_loop)

    async def gateway_status(self):
        safe_ensure_future(self._gateway_status(), loop=self.ev_loop)

    async def generate_certs(self):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

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

    async def _update_gateway_configuration(self, key: str, value: Any):
        data = {
            "configPath": key,
            "configValue": value
        }
        try:
            response = await self._api_request("post", "config/update", data)
            self._notify(response["message"])
        except Exception:
            self._notify("\nError: Gateway configuration update failed. See log file for more details.")

    async def get_gateway_configuration(self):
        return await self._api_request("get", "config", {})

    async def _show_gateway_configuration(self, key: str):
        host = global_config_map['gateway_api_host'].value
        port = global_config_map['gateway_api_port'].value
        try:
            config_dict = await self.get_gateway_configuration()
            if key is not None:
                config_dict = search_configs(config_dict, key)
            self._notify(f"\nGateway Configurations ({host}:{port}):")
            lines = []
            build_config_dict_display(lines, config_dict)
            self._notify("\n".join(lines))

        except asyncio.CancelledError:
            raise
        except Exception:
            remote_host = ':'.join([host, port])
            self._notify(f"\nError: Connection to Gateway {remote_host} failed")

    async def fetch_gateway_config_key_list(self):
        config = await self.get_gateway_configuration()
        build_config_namespace_keys(self.gateway_config_keys, config)
        self.app.input_field.completer = load_completer(self)

    def get_ipc_info(self):
        return self._docker_conn, self._docker_pipe_event

    async def docker_ipc(self, data):
        try:
            pipe, event = self.get_ipc_info()
            pipe.send(data)
            return await pipe.coro_recv()
        except Exception as e:  # unable to communicate with docker socket
            self._notify("\nError: Unable to communicate with docker socket. "
                         "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
            raise e

    async def docker_ipc_with_generator(self, data):
        try:
            pipe, event = self.get_ipc_info()
            pipe.send(data)

            while True:
                data = await pipe.coro_recv()
                if not data and not event.is_set():
                    return
                yield data
        except Exception as e:  # unable to communicate with docker socket
            self._notify("\nError: Unable to communicate with docker socket. "
                         "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
            raise e
