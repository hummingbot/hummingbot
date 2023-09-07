import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.woo_x import woo_x_constants as CONSTANTS, woo_x_web_utils as web_utils
from hummingbot.connector.exchange.woo_x.woo_x_order_book import WooXOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.woo_x.woo_x_exchange import WooXExchange


class WooXAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'WooXExchange',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """

        rest_assistant = await self._api_factory.get_rest_assistant()

        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                path_url=f"{CONSTANTS.ORDERBOOK_SNAPSHOT_PATH_URL}/{await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}",
                domain=self._domain
            ),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            channels = ['trade', 'orderbookupdate']

            topics = []

            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                for channel in channels:
                    topics.append(f"{symbol}@{channel}")

            payloads = [
                {
                    "id": str(i),
                    "topic": topic,
                    "event": "subscribe"
                }
                for i, topic in enumerate(topics)
            ]

            await asyncio.gather(*[
                ws.send(WSJSONRequest(payload=payload)) for payload in payloads
            ])

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )

            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async def ping():
            await websocket_assistant.send(WSJSONRequest(payload={'event': 'ping'}))

        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data

            if data.get('event') == 'ping':
                asyncio.ensure_future(ping())

            if data is not None:  # data will be None when the websocket is disconnected
                channel: str = self._channel_originating_message(event_message=data)
                valid_channels = self._get_messages_queue_keys()
                if channel in valid_channels:
                    self._message_queue[channel].put_nowait(data)
                else:
                    await self._process_message_for_unknown_channel(
                        event_message=data, websocket_assistant=websocket_assistant
                    )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()

        await ws.connect(
            ws_url=web_utils.wss_public_url(self._domain).format(self._connector.application_id),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)

        snapshot_timestamp: int = snapshot['timestamp']

        snapshot_msg: OrderBookMessage = WooXOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )

        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            symbol=raw_message['topic'].split('@')[0]
        )

        trade_message = WooXOrderBook.trade_message_from_exchange(
            raw_message,
            {"trading_pair": trading_pair}
        )

        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            symbol=raw_message['topic'].split('@')[0]
        )

        order_book_message: OrderBookMessage = WooXOrderBook.diff_message_from_exchange(
            raw_message,
            raw_message['ts'],
            {"trading_pair": trading_pair}
        )

        message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""

        if "topic" in event_message:
            channel = event_message.get("topic").split('@')[1]

            relations = {
                CONSTANTS.DIFF_EVENT_TYPE: self._diff_messages_queue_key,
                CONSTANTS.TRADE_EVENT_TYPE: self._trade_messages_queue_key
            }

            channel = relations.get(channel, "")

        return channel
