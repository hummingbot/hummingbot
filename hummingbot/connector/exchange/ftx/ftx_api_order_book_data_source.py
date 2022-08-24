import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS, ftx_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange


class FtxAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'FtxExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._last_ws_message_sent_timestamp = 0

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response["result"]
        snapshot_timestamp: float = self._time()
        update_id: int = int(snapshot_timestamp * 1e3)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(price, amount) for price, amount in snapshot_data.get("bids", [])],
            "asks": [(price, amount) for price, amount in snapshot_data.get("asks", [])],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"depth": "100"}

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.FTX_ORDER_BOOK_PATH.format(symbol)),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.FTX_ORDER_BOOK_LIMIT_ID,
        )

        return data

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["market"])

        for trade_data in trade_updates:
            message_content = {
                "trade_id": trade_data["id"],
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if trade_data["side"] == "buy" else float(
                    TradeType.SELL.value),
                "amount": trade_data["size"],
                "price": trade_data["price"]
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=datetime.fromisoformat(trade_data["time"]).timestamp())

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_message(
            self,
            raw_message: Dict[str, Any],
            message_queue: asyncio.Queue,
            message_type: OrderBookMessageType):
        diff_data: Dict[str, Any] = raw_message["data"]

        timestamp: float = diff_data["time"]
        update_id: int = int(timestamp * 1e3)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["market"])

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(price, amount) for price, amount in diff_data.get("bids", [])],
            "asks": [(price, amount) for price, amount in diff_data.get("asks", [])],
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            message_type,
            order_book_message_content,
            timestamp)

        message_queue.put_nowait(diff_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._parse_order_book_message(
            raw_message=raw_message,
            message_queue=message_queue,
            message_type=OrderBookMessageType.DIFF)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._parse_order_book_message(
            raw_message=raw_message,
            message_queue=message_queue,
            message_type=OrderBookMessageType.SNAPSHOT)

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                payload = {
                    "op": "subscribe",
                    "channel": CONSTANTS.WS_TRADES_CHANNEL,
                    "market": symbol
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "op": "subscribe",
                    "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
                    "market": symbol
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(subscribe_trade_request)
                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(subscribe_orderbook_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        event_type = event_message["type"]
        channel = None
        if event_type == "error":
            raise IOError(f"An error occurred processing an event message in the order book data source "
                          f"(code: {event_message.get('code')}, message: {event_message.get('msg')})")
        elif event_type in ["partial", "update"]:
            event_channel = event_message["channel"]
            if event_channel == CONSTANTS.WS_TRADES_CHANNEL:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_ORDER_BOOK_CHANNEL and event_type == "update":
                channel = self._diff_messages_queue_key
            elif event_channel == CONSTANTS.WS_ORDER_BOOK_CHANNEL and event_type == "partial":
                channel = self._snapshot_messages_queue_key

        return channel

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        # FTX receives the full snapshot as the first orderbook channel event. The full order book should only be
        # refreshed after a reconnection. To ensure that we disable the full order book snapshot through HTTP request
        pass

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                seconds_until_next_ping = (CONSTANTS.WS_PING_INTERVAL
                                           - (self._time() - self._last_ws_message_sent_timestamp))
                await asyncio.wait_for(super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                                       timeout=seconds_until_next_ping)
            except asyncio.TimeoutError:
                payload = {"op": "ping"}
                ping_request = WSJSONRequest(payload=payload)
                self._last_ws_message_sent_timestamp = self._time()
                await websocket_assistant.send(request=ping_request)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
            await ws.connect(
                ws_url=CONSTANTS.FTX_WS_URL,
                message_timeout=CONSTANTS.WS_PING_INTERVAL)
        return ws
