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
        self._auth: FoxbitAuth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
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
        try:
            ws: WSAssistant = await self._api_factory.get_ws_assistant()
            await ws.connect(ws_url=web_utils.websocket_url(), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

            header = utils.get_ws_message_frame(
                endpoint=CONSTANTS.WS_AUTHENTICATE_USER,
                msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Request"],
                payload=self._auth.get_ws_authenticate_payload(),
            )
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header), is_auth_required=True)

            await ws.send(subscribe_request)

            ret_value = await ws.receive()
            is_authenticated = False
            if ret_value.data.get('o'):
                is_authenticated = utils.ws_data_to_dict(ret_value.data.get('o'))["Authenticated"]

            await ws.ping()  # to update

            if is_authenticated:
                return ws
            else:
                self.logger().info("Some issue happens when try to subscribe at Foxbit User Stream Data, check your credentials.")
                raise

        except Exception as ex:
            self.logger().error(
                f"Unexpected error occurred subscribing to account events stream...{ex}",
                exc_info=True
            )
            raise

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
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header))
            await websocket_assistant.send(subscribe_request)

            ws_response = await websocket_assistant.receive()
            data = ws_response.data

            if data.get("n") == CONSTANTS.WS_SUBSCRIBE_ACCOUNT:
                is_subscrebed = utils.ws_data_to_dict(data.get('o'))["Subscribed"]

                if is_subscrebed:
                    self._user_stream_data_source_initialized = is_subscrebed
                    self.logger().info("Subscribed to a private account events, like Position, Orders and Trades events...")
                else:
                    self.logger().info("Some issue happens when try to subscribe at Foxbit User Stream Data, check your credentials.")
                    raise

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(
                f"Unexpected error occurred subscribing to account events stream...{ex}",
                exc_info=True
            )
            raise

    async def _on_user_stream_interruption(self,
                                           websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)
