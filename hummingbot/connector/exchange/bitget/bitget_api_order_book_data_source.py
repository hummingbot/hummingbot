import asyncio
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS, bitget_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange


class BitgetAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Data source for retrieving order book data from the Bitget exchange via REST and WebSocket APIs.
    """

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'BitgetExchange',
        api_factory: WebAssistantsFactory,
    ) -> None:
        super().__init__(trading_pairs)
        self._connector: 'BitgetExchange' = connector
        self._api_factory: WebAssistantsFactory = api_factory
        self._pong_response_event: Optional[asyncio.Event] = None
        self._pong_received_event: asyncio.Event = asyncio.Event()
        self._exchange_ping_task: Optional[asyncio.Task] = None
        self.ready: bool = False

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _process_message_for_unknown_channel(
        self,
        event_message: Dict[str, Any],
        websocket_assistant: WSAssistant,
    ) -> None:
        if event_message == CONSTANTS.PUBLIC_WS_PONG:
            self._pong_received_event.set()

        self.logger().info(f"Message for unknown channel received: {event_message}")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> Optional[str]:
        channel: Optional[str] = None

        if "event" in event_message:
            if event_message["event"] == "error":
                raise IOError(f"Failed to subscribe to public channels: {event_message}")

        if "arg" in event_message:
            arg: Dict[str, Any] = event_message["arg"]
            response_channel: Optional[str] = arg.get("channel")

            if response_channel == CONSTANTS.PUBLIC_WS_PONG:
                self.logger().info("PONG is received")
                if self._pong_response_event:
                    self.logger().info("PONG is set")
                    self._pong_response_event.set()

            if response_channel == CONSTANTS.PUBLIC_WS_BOOKS:
                action: Optional[str] = event_message.get("action")
                if action == "snapshot":
                    channel = self._snapshot_messages_queue_key
                else:
                    channel = self._diff_messages_queue_key
            elif response_channel == CONSTANTS.PUBLIC_WS_TRADE:
                channel = self._trade_messages_queue_key

        return channel

    async def _parse_any_order_book_message(
        self,
        data: Dict[str, Any],
        symbol: str,
        message_type: OrderBookMessageType,
    ) -> OrderBookMessage:
        """
        Parse a WebSocket message into an OrderBookMessage for snapshots or diffs.

        :param raw_message (Dict[str, Any]): The raw WebSocket message.
        :param message_type (OrderBookMessageType): The type of order book message (SNAPSHOT or DIFF).

        :return: OrderBookMessage: The parsed order book message.
        """
        trading_pair: str = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        update_id: int = int(data["ts"])
        timestamp: float = update_id * 1e-3

        order_book_message_content: Dict[str, Any] = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": data["bids"],
            "asks": data["asks"],
        }

        return OrderBookMessage(
            message_type=message_type,
            content=order_book_message_content,
            timestamp=timestamp
        )

    async def _parse_order_book_diff_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue
    ) -> None:
        diffs_data: Dict[str, Any] = raw_message["data"]

        for diff in diffs_data:
            diff_message: OrderBookMessage = await self._parse_any_order_book_message(
                data=diff,
                symbol=raw_message["arg"]["instId"],
                message_type=OrderBookMessageType.DIFF
            )

            message_queue.put_nowait(diff_message)

    async def _parse_order_book_snapshot_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue
    ) -> None:
        snapshot_data: Dict[str, Any] = raw_message["data"]

        for snapshot in snapshot_data:
            snapshot_message: OrderBookMessage = await self._parse_any_order_book_message(
                data=snapshot,
                symbol=raw_message["arg"]["instId"],
                message_type=OrderBookMessageType.SNAPSHOT
            )

            message_queue.put_nowait(snapshot_message)

    async def _parse_trade_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue
    ) -> None:
        data: List[Dict[str, Any]] = raw_message.get("data", [])
        symbol: str = raw_message["arg"]["instId"]
        trading_pair: str = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        for trade_data in data:
            trade_type: float = float(TradeType.BUY.value) if trade_data['side'] == "buy" else float(TradeType.SELL.value)
            message_content: Dict[str, Any] = {
                "trade_id": int(trade_data["tradeId"]),
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "amount": trade_data["size"],
                "price": trade_data["price"],
            }
            trade_message = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=int(trade_data["ts"]) * 1e-3,
            )
            message_queue.put_nowait(trade_message)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(
            ws_url=CONSTANTS.WSS_PUBLIC_URL,
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE,
        )

        return websocket_assistant

    async def _subscribe_channels(self, ws: WSAssistant) -> None:
        try:
            subscription_topics: List[Dict[str, str]] = []

            for trading_pair in self._trading_pairs:
                symbol: str = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair
                )
                for channel in [CONSTANTS.PUBLIC_WS_BOOKS, CONSTANTS.PUBLIC_WS_TRADE]:
                    subscription_topics.append({
                        "instType": "SPOT",
                        "channel": channel,
                        "instId": symbol
                    })

            await ws.send(
                WSJSONRequest({
                    "op": "subscribe",
                    "args": subscription_topics,
                })
            )

            self.logger().info("Subscribed to public channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to public channels...")
            raise

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol: str = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()

        data: Dict[str, Any] = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT),
            params={
                "symbol": symbol,
                "limit": "100",
            },
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT,
        )

        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response["data"][0]
        update_id: int = int(snapshot_data["ts"])
        timestamp: float = update_id * 1e-3

        order_book_message_content: Dict[str, Any] = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": snapshot_data.get("bids", []),
            "asks": snapshot_data.get("asks", []),
        }

        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            timestamp
        )

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]) -> None:
        if websocket_assistant and not websocket_assistant.done():
            await websocket_assistant.disconnect()
            sys.exit()

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        ping_request = WSPlainTextRequest(CONSTANTS.PUBLIC_WS_PING)

        await websocket_assistant.send(ping_request)
        self.logger().info("Ping heartbeat Sent OB")

    def _max_heartbeat_response_delay(self) -> int:
        return 30

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant) -> None:
        while True:
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                    timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
                )
            except asyncio.TimeoutError:
                if self._pong_response_event and not self._pong_response_event.is_set():
                    raise IOError("The user stream channel is unresponsive (pong response not received)")
                self._pong_response_event = asyncio.Event()
                await self._send_ping(websocket_assistant=websocket_assistant)
