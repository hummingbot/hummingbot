import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.whitebit import whitebit_constants as CONSTANTS, whitebit_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from .whitebit_exchange import WhitebitExchange


class WhitebitAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "WhitebitExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        WhiteBit connector sends a full order book snapshot as the first message of the depth channel.
        It is not required to request more snapshots apart from that if the channel is not disconnected.

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        pass

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_data: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: int = int(snapshot_data["timestamp"])
        update_id: int = snapshot_timestamp

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid[0], bid[1]) for bid in snapshot_data.get("bids", [])],
            "asks": [(ask[0], ask[1]) for ask in snapshot_data.get("asks", [])],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT, order_book_message_content, snapshot_timestamp
        )

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_BOOK_PATH)
        url = url + f"/{symbol}"

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.WHITEBIT_ORDER_BOOK_PATH,
        )

        return data

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol, trade_updates = raw_message["params"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        for trade_data in trade_updates:
            message_content = {
                "trade_id": trade_data["id"],
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value)
                if trade_data["type"] == "buy"
                else float(TradeType.SELL.value),
                "amount": trade_data["amount"],
                "price": trade_data["price"],
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE, content=message_content, timestamp=float(trade_data["time"])
            )

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        is_full_snapshot, depth_update, symbol = raw_message["params"]
        order_book_message_type = OrderBookMessageType.SNAPSHOT if is_full_snapshot else OrderBookMessageType.DIFF

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        timestamp: float = self._time()
        update_id: int = int(timestamp * 1e6)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid[0], bid[1]) for bid in depth_update.get("bids", [])],
            "asks": [(ask[0], ask[1]) for ask in depth_update.get("asks", [])],
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            order_book_message_type, order_book_message_content, timestamp
        )

        message_queue.put_nowait(diff_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        all_symbols = []
        try:
            for trading_pair_enumeration_number, trading_pair in enumerate(self._trading_pairs):
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                all_symbols.append(symbol)

                payload = {
                    "id": trading_pair_enumeration_number + 1,
                    "method": "depth_subscribe",
                    "params": [symbol, 100, "0", True],
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(subscribe_orderbook_request)

            payload = {"id": len(all_symbols) + 1, "method": "trades_subscribe", "params": all_symbols}
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                await ws.send(subscribe_trade_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        event_channel = event_message.get("method")
        if event_channel == CONSTANTS.WHITEBIT_WS_PUBLIC_TRADES_CHANNEL:
            channel = self._trade_messages_queue_key
        elif event_channel == CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL:
            channel = self._diff_messages_queue_key

        return channel

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
            await ws.connect(ws_url=CONSTANTS.WHITEBIT_WS_URI)
        return ws
