#!/usr/bin/env python
import asyncio
import aiohttp
import json
import pandas as pd
import ssl
from typing import Dict, Any, TYPE_CHECKING, List

from hummingbot.core.gateway import (
    docker_ipc,
    docker_ipc_with_generator,
    get_gateway_container_name,
    get_gateway_paths,
    GATEWAY_DOCKER_REPO,
    GATEWAY_DOCKER_TAG,
    GatewayPaths,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import (
    build_config_namespace_keys,
    search_configs,
    build_config_dict_display
)
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
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
        elif option == "test-connection":
            safe_ensure_future(self._test_connection())

    async def _test_connection(self):
        # test that the gateway is running
        try:
            resp = await self._api_request("get", "", {})
        except Exception as e:
            self.notify("\nUnable to ping gateway.")
            raise e

        if resp.get('message', None) == 'ok' or resp.get('status', None) == 'ok':
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
            host_config=host_config
        )
        await docker_ipc(
            "start",
            container=container_info["Id"]
        )
        self.notify(f"New Gateway docker container id is {container_info['Id']}.")

    @staticmethod
    async def check_gateway_image(docker_repo: str, docker_tag: str) -> bool:
        image_list: List = await docker_ipc("images", name=f"{docker_repo}:{docker_tag}", quiet=True)
        return len(image_list) > 0

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

    async def fetch_gateway_config_key_list(self):
        config = await self.get_gateway_configuration()
        build_config_namespace_keys(self.gateway_config_keys, config)
        self.app.input_field.completer = load_completer(self)
