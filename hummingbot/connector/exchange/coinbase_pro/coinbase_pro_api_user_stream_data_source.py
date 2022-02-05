#!/usr/bin/env python

import asyncio
import logging
from typing import AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book import CoinbaseProOrderBook
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class CoinbaseProAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _cbpausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpausds_logger is None:
            cls._cbpausds_logger = logging.getLogger(__name__)
        return cls._cbpausds_logger

    def __init__(
        self,
        web_assistants_factory: WebAssistantsFactory,
        trading_pairs: Optional[List[str]] = None,
    ):
        self._trading_pairs = trading_pairs
        self._web_assistants_factory = web_assistants_factory
        self._ws_assistant: Optional[WSAssistant] = None
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        super().__init__()

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return CoinbaseProOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._ws_assistant.last_recv_time if self._ws_assistant is not None else 0

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                self._ws_assistant = await self._web_assistants_factory.get_ws_assistant()
                await self._ws_assistant.connect(CONSTANTS.WS_URL, message_timeout=CONSTANTS.WS_MESSAGE_TIMEOUT)
                subscribe_payload: Dict[str, any] = {
                    "type": "subscribe",
                    "product_ids": self._trading_pairs,
                    "channels": [CONSTANTS.USER_CHANNEL_NAME]
                }
                subscribe_request = WSRequest(payload=subscribe_payload, is_auth_required=True)
                await self._ws_assistant.subscribe(subscribe_request)
                async for msg in self._iter_messages(self._ws_assistant):
                    msg_type: str = msg.get("type", None)
                    if msg_type is None:
                        raise ValueError(f"Coinbase Pro Websocket message does not contain a type - {msg}")
                    elif msg_type == "error":
                        raise ValueError(f"Coinbase Pro Websocket received error message - {msg['message']}")
                    elif msg_type in ["open", "match", "change", "done"]:
                        output.put_nowait(msg)
                    elif msg_type in ["received", "activate", "subscriptions"]:
                        # these messages are not needed to track the order book
                        pass
                    else:
                        raise ValueError(f"Unrecognized Coinbase Pro Websocket message received - {msg}")
            except asyncio.CancelledError:
                self._ws_assistant = None
                raise
            except Exception:
                self._ws_assistant = None
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error with WebSocket connection."
                                    f" Retrying in {CONSTANTS.REST_API_LIMIT_COOLDOWN} seconds."
                                    f" Check network connection."
                )
                await self._sleep(CONSTANTS.REST_API_LIMIT_COOLDOWN)

    async def _iter_messages(self, ws: WSAssistant) -> AsyncIterable[Dict]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            async for response in ws.iter_messages():
                msg = response.data
                yield msg
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
        finally:
            await ws.disconnect()

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
