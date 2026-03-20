import asyncio
import time
from typing import TYPE_CHECKING, Optional

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bithumb.bithumb_auth import BithumbAuth
    from hummingbot.connector.exchange.bithumb.bithumb_exchange import BithumbExchange


class BithumbAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Bithumb does not provide a private WebSocket API.
    This data source uses a heartbeat loop to satisfy the interface while order
    and balance updates are handled via the exchange's periodic REST polling.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(name=__name__)
        return cls._logger

    def __init__(
        self,
        auth: "BithumbAuth",
        connector: "BithumbExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        raise NotImplementedError("Bithumb does not support a private WebSocket stream.")

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Keeps the user stream tracker alive by emitting periodic heartbeat events.
        Actual order/balance state is refreshed by the exchange's polling loop via
        _update_balances() and _request_order_status().
        """
        while True:
            try:
                await asyncio.sleep(5)
                output.put_nowait({"type": "heartbeat", "timestamp": time.time()})
                self._last_recv_time = time.time()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warning("Bithumb user stream heartbeat error: %s", e)
                await asyncio.sleep(5)
