#!/usr/bin/env python

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.exchange.litebit.litebit_constants as constants
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

from .litebit_auth import LitebitAuth

if TYPE_CHECKING:
    from hummingbot.connector.exchange.litebit.litebit_exchange import LitebitExchange

__all__ = ("LitebitAPIUserStreamDataSource",)


class LitebitAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: LitebitAuth,
                 trading_pairs: Optional[List[str]],
                 connector: 'LitebitExchange',
                 api_factory: WebAssistantsFactory,
                 ):
        self._auth: LitebitAuth = auth
        self._api_factory = api_factory

        super().__init__()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        ws: WSAssistant = await self._get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=constants.WS_CONNECTION):
            await ws.connect(ws_url=constants.WSS_URL)

        payload = {
            "rid": "authenticate",
            "event": "authenticate",
            "data": self._auth.websocket_login_parameters(),
        }

        login_request: WSJSONRequest = WSJSONRequest(payload=payload)

        async with self._api_factory.throttler.execute_task(limit_id=constants.WS_REQUEST_COUNT):
            await ws.send(login_request)

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        await asyncio.sleep(1)

        try:
            payload = {
                "rid": "subscribe",
                "event": "subscribe",
                "data": ["fills", "orders"],
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            async with self._api_factory.throttler.execute_task(limit_id=constants.WS_REQUEST_COUNT):
                await websocket_assistant.send(subscribe_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private fills and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to orders and fills streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        event_type = event_message.get("event")
        event_rid = event_message.get("rid")
        if event_type == "error":
            if event_rid == "authenticate":
                raise IOError(f"Error authenticating the user stream websocket connection: {event_message}")
            else:
                raise IOError(f"Error on the user stream websocket connection: {event_message}")
        elif event_type in ["order", "fill"]:
            queue.put_nowait(event_message)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
