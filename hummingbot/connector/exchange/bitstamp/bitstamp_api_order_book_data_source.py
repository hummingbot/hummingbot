import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitstamp import bitstamp_constants as CONSTANTS, bitstamp_web_utils as web_utils
from hummingbot.connector.exchange.bitstamp.bitstamp_order_book import BitstampOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitstamp.bitstamp_exchange import BitstampExchange


class BitstampAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'BitstampExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory
        self._channel_associated_to_tradingpair = {}

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
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        order_book_data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL.format(symbol), domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_URL_LIMIT_ID,
        )

        return order_book_data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            self._channel_associated_to_tradingpair.clear()
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                channel = CONSTANTS.WS_PUBLIC_LIVE_TRADES.format(symbol)
                payload = {
                    "event": "bts:subscribe",
                    "data": {
                        "channel": channel
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)
                self._channel_associated_to_tradingpair[channel] = trading_pair

                channel = CONSTANTS.WS_PUBLIC_DIFF_ORDER_BOOK.format(symbol)
                payload = {
                    "event": "bts:subscribe",
                    "data": {
                        "channel": channel
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                self._channel_associated_to_tradingpair[channel] = trading_pair

                await ws.send(subscribe_trade_request)
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
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_msg: OrderBookMessage = BitstampOrderBook.snapshot_message_from_exchange(
            snapshot,
            time.time(),
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = self._channel_associated_to_tradingpair.get(raw_message["channel"])

        trade_message = BitstampOrderBook.trade_message_from_exchange(
            raw_message, {"trading_pair": trading_pair})

        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = self._channel_associated_to_tradingpair.get(raw_message["channel"])

        order_book_message: OrderBookMessage = BitstampOrderBook.diff_message_from_exchange(
            raw_message, time.time(), {"trading_pair": trading_pair})

        message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return event_message.get("event", "")

    async def _process_message_for_unknown_channel(self, event_message: Dict[str, Any], websocket_assistant: WSAssistant):
        event = event_message.get("event", "")
        channel = event_message.get("channel")
        if event == "bts:subscription_succeeded":
            self.logger().info(f"Subscription succeeded for channel '{channel}'")
        elif event == "bts:request_reconnect":
            raise ConnectionError("Received request to reconnect. Reconnecting...")
        else:
            self.logger().debug(f"Received message from unknown channel: {event_message}")
