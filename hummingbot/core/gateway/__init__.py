import os
import platform

# from dataclasses import dataclass
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


# _default_paths: Optional["GatewayPaths"] = None
_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

GATEWAY_DOCKER_REPO: str = "hummingbot/gateway-v2"
GATEWAY_DOCKER_TAG: str = "gateway-v2-dev" if platform.machine() in {"arm64", "aarch64"} else "gateway-v2-dev"
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


def get_certs_path(client_config_map: "ClientConfigAdapter") -> Path:
    """
    Calculates the default cert paths for a gateway container.
    """
    if is_inside_docker():
        return os.getenv("CERTS_FOLDER") and Path(os.getenv("CERTS_FOLDER"))
    else:
        return Path(client_config_map.certs.path)


def get_default_gateway_port(client_config_map: "ClientConfigAdapter") -> int:
    instance_id_portion = client_config_map.instance_id[:8]
    sum = 0
    for c in instance_id_portion:
        sum += ord(c)
    return detect_available_port(16000 + sum % 16000)


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
