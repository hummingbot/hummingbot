import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.ciex import ciex_constants as CONSTANTS, ciex_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ciex.ciex_exchange import CiexExchange


class CiexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CiexExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_data: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = snapshot_data["time"] or (self._time() * 1e3)
        update_id: int = int(snapshot_timestamp)
        snapshot_timestamp = snapshot_timestamp * 1e-3

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
        params = {"symbol": symbol}

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.CIEX_DEPTH_PATH),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.CIEX_DEPTH_PATH,
        )

        return data

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["tick"]["data"]
        symbol = raw_message["channel"].split("_")[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        for trade_data in trade_updates:
            message_content = {
                "trade_id": trade_data["ts"],
                "trading_pair": trading_pair,
                "trade_type": float(TradeType[trade_data["side"].upper()].value),
                "amount": Decimal(str(trade_data["amount"])),
                "price": Decimal(str(trade_data["price"]))
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=int(trade_data["ts"]) * 1e-3)

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_message(
            self,
            raw_message: Dict[str, Any],
            message_queue: asyncio.Queue,
            message_type: OrderBookMessageType):
        diff_data: Dict[str, Any] = raw_message["tick"]
        symbol = raw_message["channel"].split("_")[1]
        timestamp: float = raw_message["ts"] * 1e-3
        update_id: int = int(raw_message["ts"])

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(price, amount) for price, amount in diff_data.get("buys", [])],
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
                    "event": "sub",
                    "params": {
                        "channel": CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.format(symbol.lower())
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "event": "sub",
                    "params": {
                        "channel": CONSTANTS.WS_FULL_DEPTH_CHANNEL.format(symbol.lower())
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(subscribe_trade_request)
                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        event_channel = event_message.get("channel", "")
        channel = None
        if CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.split("{}")[1] in event_channel:
            channel = self._trade_messages_queue_key
        elif CONSTANTS.WS_FULL_DEPTH_CHANNEL.split("{}")[1] in event_channel:
            channel = self._snapshot_messages_queue_key

        return channel

    async def _process_message_for_unknown_channel(
            self,
            event_message: Dict[str, Any],
            websocket_assistant: WSAssistant):
        """
        Processes a message coming from a not identified channel.
        Does nothing by default but allows subclasses to reimplement

        :param event_message: the event received through the websocket connection
        :param websocket_assistant: the websocket connection to use to interact with the exchange
        """
        if "ping" in event_message:
            pong_payload = {"pong": event_message["ping"]}
            pong_message = WSJSONRequest(payload=pong_payload)
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                await websocket_assistant.send(pong_message)

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        # CIEX receives the full snapshot as the first orderbook channel event. The full order book should only be
        # refreshed after a reconnection. To ensure that we disable the full order book snapshot through HTTP request
        pass

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
            await ws.connect(ws_url=CONSTANTS.CIEX_WS_URL)
        return ws
