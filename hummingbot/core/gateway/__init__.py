import aioprocessing
import os
from os import getenv
from pathlib import Path
from typing import Optional, Any, AsyncIterable, NamedTuple

from hummingbot.client.config.global_config_map import global_config_map

_default_paths: Optional["GatewayPaths"] = None
_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

GATEWAY_DOCKER_REPO: str = "coinalpha/gateway-v2-dev"
GATEWAY_DOCKER_TAG: str = "20220215-test2"


def is_inside_docker() -> bool:
    if os.name != "posix":
        return False
    try:
        with open("/proc/1/cgroup", "r") as fd:
            cgroup_txt: str = fd.read()
            return ("docker" in cgroup_txt) or ("lxc" in cgroup_txt)
    except Exception:
        return False


def get_gateway_container_name() -> str:
    instance_id_suffix: str = global_config_map["instance_id"].value[:8]
    return f"hummingbot-gateway-{instance_id_suffix}"


class GatewayPaths(NamedTuple):
    local_conf_path: Path
    local_certs_path: Path
    local_logs_path: Path
    mount_conf_path: Path
    mount_certs_path: Path
    mount_logs_path: Path


def get_gateway_paths() -> GatewayPaths:
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
        Path("/")
        if inside_docker
        else Path.home().joinpath(f".hummingbot-gateway/{gateway_container_name}")
    )
    local_certs_path: Path = base_path.joinpath("certs")
    local_conf_path: Path = base_path.joinpath("conf")
    local_logs_path: Path = base_path.joinpath("logs")
    local_certs_path.mkdir(mode=0o755, parents=True, exist_ok=True)
    local_conf_path.mkdir(mode=0o755, parents=True, exist_ok=True)
    local_logs_path.mkdir(mode=0o755, parents=True, exist_ok=True)

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
