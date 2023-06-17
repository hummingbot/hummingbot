import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.woo_x import woo_x_constants as CONSTANTS, woo_x_web_utils as web_utils
from hummingbot.connector.exchange.woo_x.woo_x_auth import WooXAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.woo_x.woo_x_exchange import WooXExchange


class WooXAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive

    HEARTBEAT_TIME_INTERVAL = 30

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: WooXAuth,
            trading_pairs: List[str],
            connector: 'WooXExchange',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__()

        self._auth: WooXAuth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        websocket_assistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(
            ws_url=web_utils.wss_private_url(self._domain).format(self._connector.application_id),
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )

        timestamp = int(time.time() * 1e3)

        await websocket_assistant.send(WSJSONRequest(payload={
            'id': 'auth',
            'event': 'auth',
            'params': {
                'apikey': self._connector.api_key,
                'sign': self._auth.signature(timestamp),
                'timestamp': timestamp
            }
        }))

        response = await websocket_assistant.receive()

        if not response.data['success']:
            self.logger().error(f"Error authenticating the private websocket connection: {json.dumps(response.data)}")

            raise IOError("Private websocket connection authentication failed")

        return websocket_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """

        channels = ['executionreport', 'balance']

        for channel in channels:
            await websocket_assistant.send(WSJSONRequest(payload={
                "id": channel,
                "topic": channel,
                "event": "subscribe"
            }))

            response = await websocket_assistant.receive()

            if not response.data['success']:
                raise IOError(f"Error subscribing to the {channel} channel: {json.dumps(response)}")

        self.logger().info("Subscribed to private account and orders channels...")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async def ping():
            await websocket_assistant.send(WSJSONRequest(payload={'event': 'ping'}))

        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data

            if data.get('event') == 'ping':
                asyncio.ensure_future(ping())

            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            queue.put_nowait(event_message)
