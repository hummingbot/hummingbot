import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
    foxbit_utils as utils,
    foxbit_web_utils as web_utils,
)
from hummingbot.connector.exchange.foxbit.foxbit_auth import FoxbitAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.foxbit.foxbit_exchange import FoxbitExchange


class FoxbitAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: FoxbitAuth,
                 trading_pairs: List[str],
                 connector: 'FoxbitExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        super().__init__()
        self._connector = connector
        self._auth: FoxbitAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._user_stream_data_source_initialized = False

    @property
    def ready(self) -> bool:
        return self._user_stream_data_source_initialized

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.websocket_url(), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self,
                                  websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        All received messages from exchange are listened on FoxbitAPIOrderBookDataSource.listen_for_subscriptions()

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            # Subscribe Account, Orders and Trade Events
            header = utils.get_ws_message_frame(
                endpoint=CONSTANTS.WS_SUBSCRIBE_ACCOUNT,
                msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Subscribe"],
                payload={"OMSId": 1, "AccountId": self._connector.user_id},
            )
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header), is_auth_required=True)
            await websocket_assistant.send(subscribe_request)

            self._user_stream_data_source_initialized = True

            self.logger().info("Subscribed to a private account events, like Position, Orders and Traves events...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to account events stream...",
                exc_info=True
            )
            raise

    async def _on_user_stream_interruption(self,
                                           websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)
