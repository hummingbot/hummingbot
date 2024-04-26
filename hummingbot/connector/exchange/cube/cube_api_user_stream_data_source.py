import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS
from hummingbot.connector.exchange.cube.cube_auth import CubeAuth
from hummingbot.connector.exchange.cube.cube_ws_protobufs import trade_pb2
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSBinaryRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.cube.cube_exchange import CubeExchange


class CubeAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CubeAuth,
                 trading_pairs: List[str],
                 connector: 'CubeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._api_factory = api_factory
        self._auth: CubeAuth = auth
        self._trading_pairs: List[str] = trading_pairs
        self._connector = connector
        self._domain = domain

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_TRADE_URL.get(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """

        async def handle_heartbeat():
            send_hb = True
            while send_hb:
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                hb = trade_pb2.Heartbeat(
                    request_id=0,
                    timestamp=time.time_ns(),
                )
                hb_request: WSBinaryRequest = WSBinaryRequest(
                    payload=trade_pb2.OrderRequest(heartbeat=hb).SerializeToString())
                try:
                    await websocket_assistant.send(hb_request)
                except asyncio.CancelledError:
                    send_hb = False
                except ConnectionError:
                    send_hb = False
                except RuntimeError:
                    send_hb = False

        # Create a separate task for handle_heartbeat
        heartbeat_task = asyncio.create_task(handle_heartbeat())

        try:
            credentials = self._auth.credential_message_for_authentication()
            credentials_request: WSBinaryRequest = WSBinaryRequest(payload=credentials)
            await websocket_assistant.send(credentials_request)
            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            heartbeat_task.cancel()
            raise
        except Exception:
            heartbeat_task.cancel()
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        queue.put_nowait(event_message)
