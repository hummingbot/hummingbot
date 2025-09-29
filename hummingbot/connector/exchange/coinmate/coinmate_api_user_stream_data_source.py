import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.coinmate import coinmate_constants as CONSTANTS
from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import (
    UserStreamTrackerDataSource,
)
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinmate.coinmate_exchange import (
        CoinmateExchange,
    )


class CoinmateAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None
    HEARTBEAT_TIME_INTERVAL = 30.0
    MAX_RETRIES = 3

    def __init__(
        self,
        auth: CoinmateAuth,
        connector: "CoinmateExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            client_id = self._auth.client_id

            # Subscribe to user data channels
            channels = [
                "private-user_balances",
                "private-open_orders",
                "private-user-trades",
            ]

            for channel in channels:
                auth_data = self._auth.get_ws_auth_data()
                payload = {
                    "event": "subscribe",
                    "data": {"channel": f"{channel}-{client_id}", **auth_data},
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await asyncio.sleep(0.1)
                await websocket_assistant.send(subscribe_request)

            self.logger().info(
                "Subscribed to private user channels (orders, balances, trades)"
            )

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to user streams", exc_info=True
            )
            raise

    async def _process_websocket_messages(
        self, websocket_assistant: WSAssistant, queue: asyncio.Queue
    ):
        async for ws_response in websocket_assistant.iter_messages():
            try:
                message = ws_response.data
                if isinstance(message, dict):
                    # Route message to appropriate handler
                    await self._route_message(message, queue, websocket_assistant)
                else:
                    self.logger().debug(
                        f"Received non-dict WebSocket message: {type(message)} - {message}"
                    )
            except Exception as e:
                self.logger().error(
                    f"Error processing WebSocket message: {e}", exc_info=True
                )

    async def _route_message(
        self,
        message: Dict[str, Any],
        queue: asyncio.Queue,
        websocket_assistant: WSAssistant,
    ):
        try:
            event_type = message.get("event")
            if event_type == "data":
                channel = message.get("channel", "")
                data = message.get("payload", message.get("data", {}))

                if "private-open_orders" in channel:
                    await self._process_order_message(data, queue)
                elif "private-user_balances" in channel:
                    await self._process_balance_message(data, queue)
                elif "private-user-trades" in channel:
                    await self._process_trade_message(data, queue)
                else:
                    self.logger().debug(f"Unknown channel type: {channel}")
            elif event_type == "subscribe_success":
                channel = message.get("data", {}).get("channel", "unknown")
                self.logger().info(f"Successfully subscribed to: {channel}")
            elif event_type == "unsubscribe_success":
                channel = message.get("data", {}).get("channel", "unknown")
                self.logger().info(f"Successfully unsubscribed from channel: {channel}")
            elif event_type == "ping":
                try:
                    pong_payload = {"event": "pong"}
                    pong_request = WSJSONRequest(payload=pong_payload)
                    await websocket_assistant.send(pong_request)
                except Exception as e:
                    self.logger().error(f"Failed to send pong: {e}")
            elif event_type == "pong":
                self.logger().debug("Received pong from server")
            elif event_type == "error":
                error_msg = message.get("message", "Unknown error")
                self.logger().error(f"WebSocket error: {error_msg}")
            else:
                self.logger().debug(f"Unhandled message type: {event_type}")

        except Exception as e:
            self.logger().error(f"Error routing message: {e}", exc_info=True)

    async def _process_order_message(self, data: Dict[str, Any], queue: asyncio.Queue):
        try:
            order_message = {"type": "order", "data": data, "timestamp": time.time()}
            queue.put_nowait(order_message)
        except Exception as e:
            self.logger().error(f"Error processing order message: {e}", exc_info=True)

    async def _process_balance_message(
        self, data: Dict[str, Any], queue: asyncio.Queue
    ):
        try:
            balance_message = {
                "type": "balance",
                "data": data,
                "timestamp": time.time(),
            }
            queue.put_nowait(balance_message)
        except Exception as e:
            self.logger().error(f"Error processing balance message: {e}", exc_info=True)

    async def _process_trade_message(self, data: Dict[str, Any], queue: asyncio.Queue):
        try:
            trade_message = {"type": "trade", "data": data, "timestamp": time.time()}
            queue.put_nowait(trade_message)
        except Exception as e:
            self.logger().error(f"Error processing trade message: {e}", exc_info=True)

    async def _on_user_stream_interruption(
        self, websocket_assistant: Optional[WSAssistant]
    ):
        self.logger().info("User stream interrupted. Cleaning up...")
        if websocket_assistant:
            await websocket_assistant.disconnect()
        await super()._on_user_stream_interruption(websocket_assistant)

    async def _send_ping(self, websocket_assistant: WSAssistant):
        pass

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger
