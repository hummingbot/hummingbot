import asyncio
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.client.settings import GATEWAY_CONNECTORS
from hummingbot.client.ui.completer import load_completer
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_namespace_keys

POLL_INTERVAL = 2.0
POLL_TIMEOUT = 1.0

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayStatus(Enum):
    ONLINE = 1
    OFFLINE = 2


class GatewayStatusMonitor:
    _monitor_task: Optional[asyncio.Task]
    _gateway_status: GatewayStatus
    _sm_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._sm_logger is None:
            cls._sm_logger = logging.getLogger(__name__)
        return cls._sm_logger

    def __init__(self, app: "HummingbotApplication"):
        self._app = app
        self._gateway_status = GatewayStatus.OFFLINE
        self._monitor_task = None
        self._gateway_config_keys: List[str] = []
        self._gateway_ready_event: asyncio.Event = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self.gateway_status is GatewayStatus.ONLINE

    @property
    def ready_event(self) -> asyncio.Event:
        return self._gateway_ready_event

    @property
    def gateway_status(self) -> GatewayStatus:
        return self._gateway_status

    @property
    def gateway_config_keys(self) -> List[str]:
        return self._gateway_config_keys

    @gateway_config_keys.setter
    def gateway_config_keys(self, new_config: List[str]):
        self._gateway_config_keys = new_config

    def start(self):
        self._monitor_task = safe_ensure_future(self._monitor_loop())

    def stop(self):
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def wait_for_online_status(self, max_tries: int = 30):
        """
        Wait for gateway status to go online with a max number of tries. If it
        is online before time is up, it returns early, otherwise it returns the
        current status after the max number of tries.

        :param max_tries: maximum number of retries (default is 30)
        """
        while True:
            if self.ready or max_tries <= 0:
                return self.ready
            await asyncio.sleep(POLL_INTERVAL)
            max_tries = max_tries - 1

    async def _monitor_loop(self):
        while True:
            try:
                gateway_http_client = self._get_gateway_instance()
                if await asyncio.wait_for(gateway_http_client.ping_gateway(), timeout=POLL_TIMEOUT):
                    if self.gateway_status is GatewayStatus.OFFLINE:
                        gateway_connectors = await gateway_http_client.get_connectors(fail_silently=True)
                        GATEWAY_CONNECTORS.clear()
                        GATEWAY_CONNECTORS.extend([connector["name"] for connector in gateway_connectors.get("connectors", [])])
                        await self.update_gateway_config_key_list()

                    self._gateway_status = GatewayStatus.ONLINE
                else:
                    if self._gateway_status is GatewayStatus.ONLINE:
                        self.logger().info("Connection to Gateway container lost...")
                        self._gateway_status = GatewayStatus.OFFLINE

            except asyncio.CancelledError:
                raise
            except Exception:
                """
                We wouldn't be changing any status here because whatever error happens here would have been a result of manipulation data from
                the try block. They wouldn't be as a result of http related error because they're expected to fail silently.
                """
                pass
            finally:
                if self.gateway_status is GatewayStatus.ONLINE:
                    if not self._gateway_ready_event.is_set():
                        self.logger().info("Gateway Service is ONLINE.")
                    self._gateway_ready_event.set()
                else:
                    self._gateway_ready_event.clear()
                await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_gateway_configs(self) -> Dict[str, Any]:
        return await self._get_gateway_instance().get_configuration(fail_silently=True)

    async def update_gateway_config_key_list(self):
        try:
            config_list: List[str] = []
            config_dict: Dict[str, Any] = await self._fetch_gateway_configs()
            build_config_namespace_keys(config_list, config_dict)

            self.gateway_config_keys = config_list
            self._app.app.input_field.completer = load_completer(self._app)
        except Exception:
            self.logger().error("Error fetching gateway configs. Please check that Gateway service is online. ",
                                exc_info=True)

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._app.client_config_map)
        return gateway_instance
