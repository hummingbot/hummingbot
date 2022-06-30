import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitmart import bitmart_constants as CONSTANTS, bitmart_utils as utils
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitmart.bitmart_exchange import BitmartExchange


class BitmartAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitmartAuth,
        trading_pairs: List[str],
        connector: 'BitmartExchange',
        api_factory: WebAssistantsFactory
    ):
        super().__init__()
        self._auth: BitmartAuth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_PRIVATE_URL,
            ping_timeout=CONSTANTS.WS_PING_TIMEOUT)

        payload = {
            "op": "login",
            "args": self._auth.websocket_login_parameters()
        }

        login_request: WSJSONRequest = WSJSONRequest(payload=payload)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIBE):
            await ws.send(login_request)

        response: WSResponse = await ws.receive()
        message = response.data
        if "errorCode" in message or "error_code" in message or message.get("event") != "login":
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError(f"Private websocket connection authentication failed ({message})")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            symbols = [await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                       for trading_pair in self._trading_pairs]

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME}:{symbol}" for symbol in symbols]
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIBE):
                await websocket_assistant.send(subscribe_request)
            self.logger().info("Subscribed to private account and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            decompressed_data = utils.decompress_ws_message(data)
            try:
                if type(decompressed_data) == str:
                    json_data = json.loads(decompressed_data)
                else:
                    json_data = decompressed_data
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(f"Invalid event message received through the order book data source "
                                      f"connection ({decompressed_data})")
                continue

            if "errorCode" in json_data or "errorMessage" in json_data:
                raise ValueError(f"Error message received in the order book data source: {json_data}")

            await self._process_event_message(event_message=json_data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0 and "table" in event_message and "data" in event_message:
            queue.put_nowait(event_message)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
