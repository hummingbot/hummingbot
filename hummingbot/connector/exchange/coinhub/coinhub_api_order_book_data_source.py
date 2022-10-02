import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.coinhub import coinhub_constants as CONSTANTS, coinhub_web_utils as web_utils
from hummingbot.connector.exchange.coinhub.coinhub_order_book import CoinhubOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinhub.coinhub_exchange import CoinhubExchange


class CoinhubAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CoinhubExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = "trade"
        self._diff_messages_queue_key = "order_book_diff"
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "market": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "100",
            "interval": "0.001",
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )
        return data["data"]

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            symbols = [await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                       for trading_pair in self._trading_pairs]
            payload = {
                "id": 1,
                "method": CONSTANTS.TRADE_EVENT_TYPE,
                "params": symbols
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await ws.send(subscribe_trade_request)

            trading_rules = self._connector.trading_rules
            if trading_rules:
                depth_params = []
                for index, trading_pair in enumerate(self._trading_pairs):
                    if trading_pair not in trading_rules:
                        self.logger().warn(f"Trading rules: {trading_rules}")
                        raise Exception(f"{trading_pair} trading rule not found")
                    depth_params.append(symbols[index])
                    depth_params.append(50)
                    depth_params.append(str(trading_rules[trading_pair].min_price_increment))
                if depth_params:
                    payload = {
                        "id": 2,
                        "method": CONSTANTS.DIFF_EVENT_TYPE,
                        "params": depth_params
                    }
                    self.logger().info(payload)
                    subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                    await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL,
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CoinhubOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["params"][0])
            for trade in raw_message["params"][1]:
                trade_message = CoinhubOrderBook.trade_message_from_exchange(
                    trade, {"trading_pair": trading_pair})
                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            # clean = raw_message["params"][0]
            data = raw_message["params"][1]
            symbol = raw_message["params"][2]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            order_book_message: OrderBookMessage = CoinhubOrderBook.diff_message_from_exchange(
                data, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError(f"Error event received from the server ({err_msg})")
        if "result" not in event_message:
            event_type = event_message.get("method")
            if event_type == "deals.update":
                channel = self._trade_messages_queue_key
            if event_type == "depth.update":
                channel = self._diff_messages_queue_key
        return channel
