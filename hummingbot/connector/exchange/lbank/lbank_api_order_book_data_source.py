import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import dateutil.parser as date_parser

from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from .lbank_exchange import LbankExchange


class LbankAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, trading_pairs: List[str], connector: "LbankExchange", api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_reponse: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)

        if snapshot_reponse["error_code"] > 0:
            err_code: int = snapshot_reponse["error_code"]
            err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}"
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}. {err_msg}")
            raise ValueError(err_msg)

        snapshot_data: Dict[str, Any] = snapshot_reponse["data"]
        update_id: int = snapshot_data["timestamp"]
        snapshot_timestamp: float = snapshot_data["timestamp"] * 1e-3

        parsed_data = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid[0], bid[1]) for bid in snapshot_data["bids"]],
            "asks": [(ask[0], ask[1]) for ask in snapshot_data["asks"]],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT, parsed_data, snapshot_timestamp
        )
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the order book from the exchange, for the specified trading pair.

        :param trading_pair: The trading pair for which the order book will be retrieved.
        :type trading_pair: str
        :return : The response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "size": CONSTANTS.LBANK_ORDER_BOOK_SNAPSHOT_DEPTH,
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            method=RESTMethod.GET,
            url=web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL),
            params=params,
            throttler_limit_id=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL
        )
        return data

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # The incrdepth channel in LBank is not sending updates consistently. The support team suggested to not use it
        # Instead the current implementation will register and use  the full updates channel

        raise NotImplementedError

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair: str = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["pair"])
        timestamp: float = date_parser.parse(raw_message["TS"]).timestamp()
        update: Dict[str, Any] = raw_message[CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL]
        update_id: int = int(timestamp * 1e3)

        depth_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid[0], bid[1]) for bid in update["bids"]],
            "asks": [(ask[0], ask[1]) for ask in update["asks"]],
        }
        message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            depth_message_content,
            timestamp
        )
        message_queue.put_nowait(message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair: str = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["pair"])

        trade_updates: Dict[str, Any] = raw_message["trade"]

        timestamp: float = date_parser.parse(trade_updates["TS"]).timestamp()
        trade_message_content = {
            "trade_id": int(timestamp * 1e3),
            "trading_pair": trading_pair,
            "trade_type": float(TradeType.BUY.value) if trade_updates["direction"] == "buy" else float(TradeType.SELL.value),
            "amount": trade_updates["amount"],
            "price": trade_updates["price"]
        }
        trade_message: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=trade_message_content,
            timestamp=timestamp
        )
        message_queue.put_nowait(trade_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol: str = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                payload = {
                    "action": "subscribe",
                    "subscribe": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL,
                    "depth": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL_DEPTH,
                    "pair": symbol
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "action": "subscribe",
                    "subscribe": CONSTANTS.LBANK_ORDER_BOOK_TRADE_CHANNEL,
                    "pair": symbol
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trade_request)
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True,
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "ping" in event_message:
            channel = CONSTANTS.LBANK_PING_RESPONSE
        if "type" in event_message:
            event_channel = event_message["type"]
            if event_channel == CONSTANTS.LBANK_ORDER_BOOK_TRADE_CHANNEL:
                channel = self._trade_messages_queue_key
            if event_channel == CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL:
                channel = self._snapshot_messages_queue_key

        return channel

    async def _handle_ping_message(self, event_message: Dict[str, Any], ws_assistant: WSAssistant):
        try:
            pong_payload = {"action": "pong", "pong": event_message["ping"]}
            pong_request: WSJSONRequest = WSJSONRequest(payload=pong_payload)
            await ws_assistant.send(pong_request)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(
                f"Unexpected error occurred sending pong response to public stream connection... Error: {str(e)}"
            )

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                        timeout=self._ping_request_interval())
                except asyncio.TimeoutError:
                    payload = {
                        "action": "ping",
                        "ping": str(uuid.uuid4())
                    }
                    ping_request: WSJSONRequest = WSJSONRequest(payload=payload)
                    await websocket_assistant.send(ping_request)
        except ConnectionError as e:
            if "Close code = 1000" in str(e):  # WS closed by server
                self.logger().warning(str(e))
            else:
                raise

    async def _process_message_for_unknown_channel(
            self,
            event_message: Dict[str, Any],
            websocket_assistant: WSAssistant):
        if "ping" in event_message:
            await self._handle_ping_message(event_message=event_message, ws_assistant=websocket_assistant)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.LBANK_WSS_URL)
        return ws

    def _ping_request_interval(self):
        return CONSTANTS.LBANK_WS_PING_REQUEST_INTERVAL
