"""
Polymarket WebSocket data source for market data and user streams.
Uses confirmed working endpoints and subscription formats.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

from .polymarket_constants import WS_MARKET_URL, WS_USER_URL
from .polymarket_sdk_auth import PolymarketSDKAuth


class PolymarketWebSocketDataSource(UserStreamTrackerDataSource):
    """
    WebSocket data source for Polymarket using confirmed working endpoints.
    Handles both public market data and private user streams.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: Optional[PolymarketSDKAuth] = None,
        trading_pairs: Optional[List[str]] = None,
        web_assistants_factory: Optional[WebAssistantsFactory] = None
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs or []
        self._web_assistants_factory = web_assistants_factory
        self._ws_assistant: Optional[WSAssistant] = None
        self._user_ws_assistant: Optional[WSAssistant] = None
        self._last_recv_time = 0

        # Token IDs for subscriptions
        self._token_ids: List[str] = []

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def _get_ws_assistant(self, is_private: bool = False) -> WSAssistant:
        """Get WebSocket assistant for public or private streams."""
        if self._web_assistants_factory is None:
            self._web_assistants_factory = WebAssistantsFactory.get_instance()

        url = WS_USER_URL if is_private else WS_MARKET_URL
        return await self._web_assistants_factory.get_ws_assistant(url)

    def _get_token_ids_from_trading_pairs(self) -> List[str]:
        """Convert trading pairs to token IDs for WebSocket subscription."""
        # This is a placeholder - in reality we'd need to resolve trading pairs to token IDs
        # For now, return empty list as token ID resolution needs market data lookup
        return []

    async def _subscribe_to_market_streams(self, ws_assistant: WSAssistant):
        """Subscribe to public market data streams."""
        try:
            # Get token IDs for subscription
            token_ids = self._get_token_ids_from_trading_pairs()

            if token_ids:
                # Market subscription format from poly-maker
                subscription_msg = {"assets_ids": token_ids}

                await ws_assistant.send(WSJSONRequest(payload=subscription_msg))
                self.logger().info(f"Subscribed to market data for {len(token_ids)} tokens")
            else:
                self.logger().warning("No token IDs available for market subscription")

        except Exception as e:
            self.logger().error(f"Error subscribing to market streams: {e}")
            raise

    async def _subscribe_to_user_streams(self, ws_assistant: WSAssistant):
        """Subscribe to private user data streams."""
        try:
            if not self._auth:
                self.logger().warning("No auth provided for user stream subscription")
                return

            # User subscription format from poly-maker
            auth_payload = self._auth.get_ws_auth_payload()

            await ws_assistant.send(WSJSONRequest(payload=auth_payload))
            self.logger().info("Subscribed to user data stream")

        except Exception as e:
            self.logger().error(f"Error subscribing to user streams: {e}")
            raise

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Listen for order book updates from market WebSocket."""
        ws_assistant = None
        try:
            ws_assistant = await self._get_ws_assistant(is_private=False)
            await ws_assistant.connect()
            await self._subscribe_to_market_streams(ws_assistant)

            async for ws_response in ws_assistant.iter_messages():
                data = ws_response.data
                if isinstance(data, str):
                    data = json.loads(data)

                self._last_recv_time = time.time()

                # Process market data message
                order_book_message = self._parse_order_book_message(data)
                if order_book_message:
                    output.put_nowait(order_book_message)

        except Exception as e:
            self.logger().error(f"Error in order book stream: {e}")
            raise
        finally:
            if ws_assistant:
                await ws_assistant.disconnect()

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Listen for trade updates from market WebSocket."""
        # Trades are typically included in the same market stream as order book updates
        # For now, we'll use the same connection as order book
        await self.listen_for_order_book_diffs(ev_loop, output)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Listen for order book snapshots."""
        # Snapshots are typically sent on initial connection or periodically
        # For now, we'll handle them in the same stream as diffs
        await self.listen_for_order_book_diffs(ev_loop, output)

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Listen for user-specific updates (orders, balances, positions)."""
        ws_assistant = None
        try:
            ws_assistant = await self._get_ws_assistant(is_private=True)
            await ws_assistant.connect()
            await self._subscribe_to_user_streams(ws_assistant)

            async for ws_response in ws_assistant.iter_messages():
                data = ws_response.data
                if isinstance(data, str):
                    data = json.loads(data)

                self._last_recv_time = time.time()

                # Process user data message
                user_message = self._parse_user_stream_message(data)
                if user_message:
                    output.put_nowait(user_message)

        except Exception as e:
            self.logger().error(f"Error in user stream: {e}")
            raise
        finally:
            if ws_assistant:
                await ws_assistant.disconnect()

    def _parse_order_book_message(self, message: Dict[str, Any]) -> Optional[OrderBookMessage]:
        """Parse WebSocket message into OrderBookMessage."""
        try:
            # This is a placeholder implementation
            # Real implementation would parse Polymarket's WebSocket message format

            message_type = message.get("type")

            if message_type == "snapshot":
                return OrderBookMessage(
                    message_type=OrderBookMessageType.SNAPSHOT,
                    content=message,
                    timestamp=time.time()
                )
            elif message_type == "update":
                return OrderBookMessage(
                    message_type=OrderBookMessageType.DIFF,
                    content=message,
                    timestamp=time.time()
                )
            elif message_type == "trade":
                return OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message,
                    timestamp=time.time()
                )

        except Exception as e:
            self.logger().error(f"Error parsing order book message: {e}")

        return None

    def _parse_user_stream_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse user stream message."""
        try:
            # This is a placeholder implementation
            # Real implementation would parse Polymarket's user message format

            message_type = message.get("type")

            if message_type in ["order_update", "fill", "balance_update"]:
                return {
                    "type": message_type,
                    "data": message,
                    "timestamp": time.time()
                }

        except Exception as e:
            self.logger().error(f"Error parsing user stream message: {e}")

        return None

    async def get_last_trade_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """Get last trade prices using REST API fallback."""
        # This would typically be handled by the API data source
        # WebSocket implementation would cache last seen prices
        return {}

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _sleep(self, delay: float):
        """Sleep for specified delay."""
        await asyncio.sleep(delay)
