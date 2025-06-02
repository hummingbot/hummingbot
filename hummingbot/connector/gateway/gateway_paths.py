import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aioprocessing

from hummingbot import root_path

if TYPE_CHECKING:
    from hummingbot import ClientConfigAdapter

_default_paths: Optional["GatewayPaths"] = None
_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

S_DECIMAL_0: Decimal = Decimal(0)


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

    external_certs_path: Optional[Path] = os.getenv("CERTS_FOLDER") and Path(os.getenv("CERTS_FOLDER"))
    external_conf_path: Optional[Path] = os.getenv("GATEWAY_CONF_FOLDER") and Path(os.getenv("GATEWAY_CONF_FOLDER"))
    external_logs_path: Optional[Path] = os.getenv("GATEWAY_LOGS_FOLDER") and Path(os.getenv("GATEWAY_LOGS_FOLDER"))
    local_certs_path: Path = client_config_map.certs_path
    local_conf_path: Path = root_path().joinpath("gateway/conf")
    local_logs_path: Path = root_path().joinpath("gateway/logs")
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
