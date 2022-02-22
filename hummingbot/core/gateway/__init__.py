import aioprocessing
from dataclasses import dataclass
import os
from os import getenv
from pathlib import Path
from typing import Optional, Any, Dict, AsyncIterable
import aiohttp
import ssl
import json

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.logger import HummingbotLogger
import logging


_default_paths: Optional["GatewayPaths"] = None
_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

GATEWAY_DOCKER_REPO: str = "coinalpha/gateway-v2-dev"
GATEWAY_DOCKER_TAG: str = "20220215-test2"


def is_inside_docker() -> bool:
    """
    Checks whether this Hummingbot instance is running inside a container.

    :return: True if running inside container, False otherwise.
    """
    if os.name != "posix":
        return False
    try:
        with open("/proc/1/cmdline", "rb") as fd:
            cmdline_txt: bytes = fd.read()
            return b"quickstart" in cmdline_txt
    except Exception:
        return False


def get_gateway_container_name() -> str:
    """
    Calculates the name for the gateway container, for this Hummingbot instance.

    :return: Gateway container name
    """
    instance_id_suffix: str = global_config_map["instance_id"].value[:8]
    return f"hummingbot-gateway-{instance_id_suffix}"


@dataclass
class GatewayPaths:
    """
    Represents the local paths and Docker mount paths for a gateway container's conf, certs and logs directories.

    Local paths represent where Hummingbot client sees the paths from the perspective of its local environment. If
    Hummingbot is being run from source, then the local environment is the same as the host environment. However, if
    Hummingbot is being run as a container, then the local environment is the container's environment.

    Mount paths represent where the gateway container's paths are located on the host environment. If Hummingbot is
    being run from source, then these should be the same as the local paths. However, if Hummingbot is being run as a
    container - then these must be fed to it from external sources (e.g. environment variables), since containers
    generally only have very restricted access to the host filesystem.
    """

    local_conf_path: Path
    local_certs_path: Path
    local_logs_path: Path
    mount_conf_path: Path
    mount_certs_path: Path
    mount_logs_path: Path

    def __post_init__(self):
        """
        Ensure the local paths are created when a GatewayPaths object is created.
        """
        for path in [self.local_conf_path, self.local_certs_path, self.local_logs_path]:
            path.mkdir(mode=0o755, parents=True, exist_ok=True)


def get_gateway_paths() -> GatewayPaths:
    """
    Calculates the default paths for a gateway container.

    For Hummingbot running from source, the gateway files are to be stored in ~/.hummingbot-gateway/<container name>/

    For Hummingbot running inside container, the gateway files are to be stored in ~/.hummingbot-gateway/ locally;
      and inside the paths pointed to be CERTS_FOLDER, GATEWAY_CONF_FOLDER, GATEWAY_LOGS_FOLDER environment variables
      on the host system.
    """
    global _default_paths
    if _default_paths is not None:
        return _default_paths

    inside_docker: bool = is_inside_docker()

    gateway_container_name: str = get_gateway_container_name()
    external_certs_path: Optional[Path] = getenv("CERTS_FOLDER") and Path(getenv("CERTS_FOLDER"))
    external_conf_path: Optional[Path] = getenv("GATEWAY_CONF_FOLDER") and Path(getenv("GATEWAY_CONF_FOLDER"))
    external_logs_path: Optional[Path] = getenv("GATEWAY_LOGS_FOLDER") and Path(getenv("GATEWAY_LOGS_FOLDER"))

    if inside_docker and not (external_certs_path and external_conf_path and external_logs_path):
        raise EnvironmentError("CERTS_FOLDER, GATEWAY_CONF_FOLDER and GATEWAY_LOGS_FOLDER must be defined when "
                               "running as container.")

    base_path: Path = (
        Path.home().joinpath(".hummingbot-gateway")
        if inside_docker
        else Path.home().joinpath(f".hummingbot-gateway/{gateway_container_name}")
    )
    local_certs_path: Path = base_path.joinpath("certs")
    local_conf_path: Path = base_path.joinpath("conf")
    local_logs_path: Path = base_path.joinpath("logs")
    mount_certs_path: Path = external_certs_path or local_certs_path
    mount_conf_path: Path = external_conf_path or local_conf_path
    mount_logs_path: Path = external_logs_path or local_logs_path

    _default_paths = GatewayPaths(
        local_conf_path=local_conf_path,
        local_certs_path=local_certs_path,
        local_logs_path=local_logs_path,
        mount_conf_path=mount_conf_path,
        mount_certs_path=mount_certs_path,
        mount_logs_path=mount_logs_path
    )
    return _default_paths


def set_hummingbot_pipe(conn: aioprocessing.AioConnection):
    global _hummingbot_pipe
    _hummingbot_pipe = conn


async def docker_ipc(method_name: str, *args, **kwargs) -> Any:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    global _hummingbot_pipe

    if _hummingbot_pipe is None:
        raise RuntimeError("Not in the main process, or hummingbot wasn't started via `fork_and_start()`.")
    try:
        _hummingbot_pipe.send((method_name, args, kwargs))
        return await _hummingbot_pipe.coro_recv()
    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "\nError: Unable to communicate with docker socket. "
            "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
        raise e


async def docker_ipc_with_generator(method_name: str, *args, **kwargs) -> AsyncIterable[str]:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    global _hummingbot_pipe

    if _hummingbot_pipe is None:
        raise RuntimeError("Not in the main process, or hummingbot wasn't started via `fork_and_start()`.")
    try:
        _hummingbot_pipe.send((method_name, args, kwargs))
        while True:
            data = await _hummingbot_pipe.coro_recv()
            if data is None:
                break
            yield data
    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "\nError: Unable to communicate with docker socket. "
            "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
        raise e


class GatewayHttpClient:
    """
    An HTTP client for making requests to the gateway API.
    """

    _ghc_logger: Optional[HummingbotLogger] = None
    _shared_client: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ghc_logger is None:
            cls._ghc_logger = logging.getLogger(__name__)
        return cls._ghc_logger

    def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def api_request(self,
                          method: str,
                          path_url: str,
                          params: Dict[str, Any] = {},
                          fail_silently: bool = False) -> Optional[Dict[str, Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :param fail_silently: used to determine if errors will be raise or silently ignored
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = self._http_client()

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
        except Exception as e:
            if not fail_silently:
                raise e

        return parsed_response


gateway_http_client = GatewayHttpClient()
