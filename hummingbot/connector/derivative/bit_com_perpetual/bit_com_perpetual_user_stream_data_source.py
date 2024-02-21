import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_derivative import BitComPerpetualDerivative


class BitComPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AuthBase,
            trading_pairs: List[str],
            connector: 'BitComPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):

        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_listen_key_ping_ts = None
        self._trading_pairs: List[str] = trading_pairs

        self.token = None

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def get_token(self):
        data = None
        try:
            data = await self._connector._api_get(path_url=CONSTANTS.USERSTREAM_AUTH_URL, params={},
                                                  is_auth_required=True)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(
                f"Error fetching BitCom Perpetual user stream token. "
                f"The response was {data}. Error: {exception}"
            )
        return data['data']['token']

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
               Subscribes to order events.

               :param websocket_assistant: the websocket assistant used to connect to the exchange
               """
        try:
            self.token = await self.get_token()

            symbols = [await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                       for trading_pair in self._trading_pairs]
            pairs = self._trading_pairs
            payload = {
                "type": "subscribe",
                "instruments": symbols,
                "channels": [CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                             CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
                             CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                             CONSTANTS.USER_BALANCES_ENDPOINT_NAME,
                             ],
                "pairs": pairs,
                "categories": ["future"],
                "interval": "raw",
                "token": self.token,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(
                payload=payload)
            await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private order changes channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        websocket_assistant and await websocket_assistant.disconnect()
        self.token = None
        await self._sleep(5)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("channel") == 'subscription' and event_message['data']['code'] != 0:
            err_msg = event_message
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}."
            })
        elif event_message.get("channel") in [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCES_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)
