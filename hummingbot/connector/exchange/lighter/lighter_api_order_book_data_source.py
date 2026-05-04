import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange


class LighterAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LighterExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._market_id_to_trading_pair: Dict[int, str] = {}
        self._ping_task: Optional[asyncio.Task] = None
        self._last_listen_error_log_ts: float = 0.0

    async def listen_for_subscriptions(self):
        """Override base loop to throttle repeated reconnect exception logs."""
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                self._ws_assistant = ws
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                close_message = str(connection_exception)
                if "close code = 1000" in close_message.lower():
                    self.logger().debug(f"The websocket connection was closed ({connection_exception})")
                else:
                    self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception as ex:
                now = time.time()
                if now - self._last_listen_error_log_ts >= 30.0:
                    self._last_listen_error_log_ts = now
                    self.logger().exception(
                        "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    )
                else:
                    self.logger().debug(
                        "Suppressing repeated order book listener error during reconnect storm: %s",
                        ex,
                    )
                await self._sleep(2.0)
            finally:
                self._ws_assistant = None
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    def _get_headers(self) -> Dict[str, str]:
        headers = {}
        if self._connector.rest_api_key:
            headers["X-Api-Key"] = self._connector.rest_api_key
        return headers

    def _get_public_headers(self) -> Dict[str, str]:
        return {}

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
        params = {"market_id": market_id, "limit": 250}

        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL,
            headers=self._get_public_headers(),
        )

        code = response.get("code")
        is_success = response.get("success") is True
        try:
            is_success = is_success or int(code) == 200
        except Exception:
            pass

        if not is_success:
            raise ValueError(f"Failed to fetch order book snapshot for {trading_pair}: {response}")

        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        order_book_snapshot_data = await self._request_order_book_snapshot(trading_pair)
        timestamp = time.time()
        return LighterOrderBook.snapshot_message_from_exchange(
            msg={
                "update_id": int(timestamp * 1000),
                "bids": [(bid["price"], bid["remaining_base_amount"]) for bid in order_book_snapshot_data.get("bids", [])],
                "asks": [(ask["price"], ask["remaining_base_amount"]) for ask in order_book_snapshot_data.get("asks", [])],
            },
            metadata={"trading_pair": trading_pair},
            timestamp=timestamp,
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain), ws_headers=self._get_headers())
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        await super()._on_order_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        while True:
            try:
                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
                await ws.send(WSJSONRequest(payload={"method": "ping"}))
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().warning("Error sending ping to Lighter WebSocket", exc_info=True)
                await asyncio.sleep(5.0)

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
            self._market_id_to_trading_pair[market_id] = trading_pair
            await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"order_book/{market_id}"}))
            await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"trade/{market_id}"}))

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False

        market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
        self._market_id_to_trading_pair[market_id] = trading_pair
        self.add_trading_pair(trading_pair)

        await self._ws_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"order_book/{market_id}"}))
        await self._ws_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"trade/{market_id}"}))
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False

        market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
        await self._ws_assistant.send(WSJSONRequest(payload={"type": "unsubscribe", "channel": f"order_book/{market_id}"}))
        await self._ws_assistant.send(WSJSONRequest(payload={"type": "unsubscribe", "channel": f"trade/{market_id}"}))
        self._market_id_to_trading_pair.pop(market_id, None)
        self.remove_trading_pair(trading_pair)
        return True

    @staticmethod
    def _extract_market_id_from_channel(channel: str) -> Optional[int]:
        """Accept both 'prefix:123' and 'prefix/123' channel formats."""
        if not channel:
            return None
        try:
            if ":" in channel:
                return int(channel.rsplit(":", 1)[1])
            if "/" in channel:
                return int(channel.rsplit("/", 1)[1])
        except Exception:
            return None
        return None

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._extract_market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        order_book = raw_message.get("order_book") or {}
        snapshot_timestamp = float(raw_message.get("timestamp") or raw_message.get("last_updated_at") or 0) / 1000
        update_id = int(order_book.get("nonce") or raw_message.get("nonce") or 0)
        if update_id == 0:
            update_id = int(raw_message.get("offset") or order_book.get("offset") or raw_message.get("last_updated_at") or 0)

        snapshot_msg = LighterOrderBook.snapshot_message_from_exchange(
            msg={
                "update_id": update_id,
                "bids": [(bid["price"], bid["size"]) for bid in order_book.get("bids", [])],
                "asks": [(ask["price"], ask["size"]) for ask in order_book.get("asks", [])],
            },
            metadata={"trading_pair": trading_pair},
            timestamp=snapshot_timestamp,
        )
        message_queue.put_nowait(snapshot_msg)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._extract_market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        for trade_data in raw_message.get("trades", []):
            trade_message = LighterOrderBook.trade_message_from_exchange(
                msg={
                    **trade_data,
                    "nonce": trade_data.get("nonce") or raw_message.get("nonce"),
                },
                metadata={"trading_pair": trading_pair},
                timestamp=float(raw_message.get("timestamp") or 0) / 1000,
            )
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._extract_market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        order_book = raw_message.get("order_book") or {}
        update_id = int(order_book.get("nonce") or raw_message.get("nonce") or 0)
        if update_id == 0:
            update_id = int(raw_message.get("offset") or order_book.get("offset") or 0)

        diff_message = LighterOrderBook.diff_message_from_exchange(
            msg={
                "update_id": update_id,
                "first_update_id": int(order_book.get("begin_nonce") or update_id),
                "bids": [(bid["price"], bid["size"]) for bid in order_book.get("bids", [])],
                "asks": [(ask["price"], ask["size"]) for ask in order_book.get("asks", [])],
            },
            metadata={"trading_pair": trading_pair},
            timestamp=float(raw_message.get("timestamp") or 0) / 1000,
        )
        message_queue.put_nowait(diff_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if "channel" not in event_message:
            return ""
        event_channel = str(event_message.get("channel"))
        event_type = str(event_message.get("type", ""))
        if (
            event_channel.startswith(f"{CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_CHANNEL}:")
            or event_channel.startswith(f"{CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_CHANNEL}/")
        ):
            if event_type in {"subscribed/order_book", "snapshot/order_book"}:
                return self._snapshot_messages_queue_key
            if event_type in {"update/order_book"}:
                return self._diff_messages_queue_key
            return self._snapshot_messages_queue_key
        if (
            event_channel.startswith(f"{CONSTANTS.WS_TRADES_CHANNEL}:")
            or event_channel.startswith(f"{CONSTANTS.WS_TRADES_CHANNEL}/")
        ):
            return self._trade_messages_queue_key
        return ""
