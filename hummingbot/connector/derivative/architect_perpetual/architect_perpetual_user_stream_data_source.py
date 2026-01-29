import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.architect_perpetual.architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
        ArchitectPerpetualDerivative,
    )


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _bpusds_logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: ArchitectPerpetualAuth,
        trading_pairs: List[str],
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._orderflow_channel = None
        self._orderflow_task: Optional[asyncio.Task] = None

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                client = await self._connector._get_architect_client()
                async for order_update in client.stream_orderflow():
                    self._last_recv_time = time.time()
                    message = self._parse_order_update(order_update)
                    if message:
                        output.put_nowait(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream")
                await self._sleep(5)

    def _parse_order_update(self, order_update: Any) -> Optional[Dict[str, Any]]:
        try:
            update_type = "order"
            if hasattr(order_update, 'fill') and order_update.fill:
                update_type = "fill"
            elif hasattr(order_update, 'ack') and order_update.ack:
                update_type = "ack"
            elif hasattr(order_update, 'out') and order_update.out:
                update_type = "out"
            elif hasattr(order_update, 'reject') and order_update.reject:
                update_type = "reject"

            return {
                "type": update_type,
                "data": order_update,
                "timestamp": time.time(),
            }
        except Exception:
            self.logger().exception(f"Error parsing order update: {order_update}")
            return None

    async def _sleep(self, seconds: float):
        await asyncio.sleep(seconds)
