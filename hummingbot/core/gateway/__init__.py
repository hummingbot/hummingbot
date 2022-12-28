import os
import platform
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

import aioprocessing

from hummingbot.connector.gateway.clob import clob_constants
from hummingbot.connector.gateway.common_types import Chain
from hummingbot.core.event.events import TradeType
from hummingbot.core.utils import detect_available_port

if TYPE_CHECKING:
    from hummingbot import ClientConfigAdapter


_default_paths: Optional["GatewayPaths"] = None
_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

GATEWAY_DOCKER_REPO: str = "hummingbot/gateway-v2"
GATEWAY_DOCKER_TAG: str = "gateway-v2-master-arm" if platform.machine() in {"arm64", "aarch64"} else "gateway-v2-master"
S_DECIMAL_0: Decimal = Decimal(0)


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


def get_gateway_container_name(client_config_map: "ClientConfigAdapter") -> str:
    """
    Calculates the name for the gateway container, for this Hummingbot instance.

    :return: Gateway container name
    """
    instance_id_suffix = client_config_map.instance_id[:8]
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


def get_gateway_paths(client_config_map: "ClientConfigAdapter") -> GatewayPaths:
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

    gateway_container_name: str = get_gateway_container_name(client_config_map)
    external_certs_path: Optional[Path] = os.getenv("CERTS_FOLDER") and Path(os.getenv("CERTS_FOLDER"))
    external_conf_path: Optional[Path] = os.getenv("GATEWAY_CONF_FOLDER") and Path(os.getenv("GATEWAY_CONF_FOLDER"))
    external_logs_path: Optional[Path] = os.getenv("GATEWAY_LOGS_FOLDER") and Path(os.getenv("GATEWAY_LOGS_FOLDER"))

    if inside_docker and not (external_certs_path and external_conf_path and external_logs_path):
        raise EnvironmentError("CERTS_FOLDER, GATEWAY_CONF_FOLDER and GATEWAY_LOGS_FOLDER must be defined when "
                               "running as container.")

    base_path: Path = (
        Path.home().joinpath(".hummingbot-gateway")
        if inside_docker
        else Path.home().joinpath(f".hummingbot-gateway/{gateway_container_name}")
    )
    conf_path: Path = (
        Path.home().joinpath("hummingbot-files")
        if inside_docker
        else Path.home().joinpath(f"hummingbot-files/{gateway_container_name}")

    )
    local_certs_path: Path = base_path.joinpath("certs")
    local_conf_path: Path = conf_path.joinpath("gateway-conf")
    local_logs_path: Path = conf_path.joinpath("gateway-logs")
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


def get_default_gateway_port(client_config_map: "ClientConfigAdapter") -> int:
    instance_id_portion = client_config_map.instance_id[:4]
    return detect_available_port(16000 + int(instance_id_portion, 16) % 16000)


def set_hummingbot_pipe(conn: aioprocessing.AioConnection):
    global _hummingbot_pipe
    _hummingbot_pipe = conn


async def detect_existing_gateway_container(client_config_map: "ClientConfigAdapter") -> Optional[Dict[str, Any]]:
    try:
        results: List[Dict[str, Any]] = await docker_ipc(
            "containers",
            all=True,
            filters={
                "name": get_gateway_container_name(client_config_map),
            })
        if len(results) > 0:
            return results[0]
        return
    except Exception:
        return


async def start_existing_gateway_container(client_config_map: "ClientConfigAdapter"):
    container_info: Optional[Dict[str, Any]] = await detect_existing_gateway_container(client_config_map)
    if container_info is not None and container_info["State"] != "running":
        from hummingbot.client.hummingbot_application import HummingbotApplication
        HummingbotApplication.main_application().logger().info("Starting existing Gateway container...")
        await docker_ipc("start", get_gateway_container_name(client_config_map))


async def docker_ipc(method_name: str, *args, **kwargs) -> Any:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    global _hummingbot_pipe

    if _hummingbot_pipe is None:
        raise RuntimeError("Not in the main process, or hummingbot wasn't started via `fork_and_start()`.")
    try:
        _hummingbot_pipe.send((method_name, args, kwargs))
        data = await _hummingbot_pipe.coro_recv()
        if isinstance(data, Exception):
            raise data
        return data

    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "Notice: Hummingbot is unable to communicate with Docker. If you need gateway for DeFi,"
            "\nmake sure Docker is on, then restart Hummingbot. Otherwise, ignore this message.")
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
            if isinstance(data, Exception):
                raise data
            yield data
    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "Notice: Hummingbot is unable to communicate with Docker. If you need gateway for DeFi,"
            "\nmake sure Docker is on, then restart Hummingbot. Otherwise, ignore this message.")
        raise e


def check_transaction_exceptions(
        allowances: Dict[str, Decimal],
        balances: Dict[str, Decimal],
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: TradeType,
        gas_limit: int,
        gas_cost: Decimal,
        gas_asset: str,
        swaps_count: int,
        chain: Chain = Chain.ETHEREUM
) -> List[str]:
    """
    Check trade data for Ethereum decentralized exchanges
    """
    exception_list = []
    swaps_message: str = f"Total swaps: {swaps_count}"
    gas_asset_balance: Decimal = balances.get(gas_asset, S_DECIMAL_0)

    # check for sufficient gas
    if gas_asset_balance < gas_cost:
        exception_list.append(f"Insufficient {gas_asset} balance to cover gas:"
                              f" Balance: {gas_asset_balance}. Est. gas cost: {gas_cost}. {swaps_message}")

    asset_out: str = quote_asset if side is TradeType.BUY else base_asset
    asset_out_allowance: Decimal = allowances.get(asset_out, S_DECIMAL_0)

    # check for gas limit set to low
    if chain == Chain.ETHEREUM:
        gas_limit_threshold: int = 21000
    elif chain == Chain.SOLANA:
        gas_limit_threshold: int = clob_constants.FIVE_THOUSAND_LAMPORTS
    else:
        raise ValueError(f"Unsupported chain: {chain}")
    if gas_limit < gas_limit_threshold:
        exception_list.append(f"Gas limit {gas_limit} below recommended {gas_limit_threshold} threshold.")

    # check for insufficient token allowance
    if allowances[asset_out] < amount:
        exception_list.append(f"Insufficient {asset_out} allowance {asset_out_allowance}. Amount to trade: {amount}")

    return exception_list


async def start_gateway(client_config_map: "ClientConfigAdapter"):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    try:
        response = await docker_ipc(
            "containers",
            all=True,
            filters={"name": get_gateway_container_name(client_config_map)}
        )
        if len(response) == 0:
            raise ValueError(f"Gateway container {get_gateway_container_name(client_config_map)} not found. ")

        container_info = response[0]
        if container_info["State"] == "running":
            HummingbotApplication.main_application().notify(f"Gateway container {container_info['Id']} already running.")
            return

        await docker_ipc(
            "start",
            container=container_info["Id"]
        )
        HummingbotApplication.main_application().notify(f"Gateway container {container_info['Id']} has started.")
    except Exception as e:
        HummingbotApplication.main_application().notify(f"Error occurred starting Gateway container. {e}")


async def stop_gateway(client_config_map: "ClientConfigAdapter"):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    try:
        response = await docker_ipc(
            "containers",
            all=True,
            filters={"name": get_gateway_container_name(client_config_map)}
        )
        if len(response) == 0:
            raise ValueError(f"Gateway container {get_gateway_container_name(client_config_map)} not found.")

        container_info = response[0]
        if container_info["State"] != "running":
            HummingbotApplication.main_application().notify(f"Gateway container {container_info['Id']} not running.")
            return

        await docker_ipc(
            "stop",
            container=container_info["Id"],
        )
        HummingbotApplication.main_application().notify(f"Gateway container {container_info['Id']} successfully stopped.")
    except Exception as e:
        HummingbotApplication.main_application().notify(f"Error occurred stopping Gateway container. {e}")


async def restart_gateway(client_config_map: "ClientConfigAdapter"):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    await stop_gateway(client_config_map)
    await start_gateway(client_config_map)
    HummingbotApplication.main_application().notify("Gateway will be ready momentarily.")
