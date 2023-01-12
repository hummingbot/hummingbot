import asyncio
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from bxsolana import Provider
from bxsolana_trader_proto import GetOrderbookResponse, GetOrderbooksStreamResponse

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import BloxrouteOpenbookOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_exchange import BloxrouteOpenbookExchange

class BloxrouteOpenbookAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, provider: Provider, trading_pairs: List[str], connector: 'BloxrouteOpenbookExchange'):
        super().__init__(trading_pairs)

        self._provider = provider
        self._connector = connector
        self._orderbook_stream: Optional[AsyncGenerator[GetOrderbooksStreamResponse, None]] = None

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        raise Exception("""this function is not needed for bloxroute_openbook data source
                           the request is handled in the _order_book_snapshot func""")

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        orderbook: GetOrderbookResponse = await self._provider.get_orderbook(market=trading_pair,
                                                                             limit=1,
                                                                             project=OPENBOOK_PROJECT)

        snapshot_timestamp: float = time.time()

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(time.time()),
            "bids": [(bid.price, bid.size) for bid in orderbook.bids],
            "asks": [(ask.price, ask.size) for ask in orderbook.asks]
        }
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        await self._provider.connect()
        return WSAssistant()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            self._orderbook_stream = self._provider.get_orderbooks_stream(markets=self._trading_pairs,
                                                                             project=OPENBOOK_PROJECT)
            self.logger().info("Subscribed to orderbook channel")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        raise Exception("Bloxroute Openbook does not use `_channel_originating_message`")

    async def _process_websocket_messages(self, _: WSAssistant):
        orderbook_queue = self._message_queue[self._snapshot_messages_queue_key]
        async for orderbook_event in self._orderbook_stream:
            orderbook_queue.put_nowait(orderbook_event.to_dict(include_default_values=True))

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        order_book_message: OrderBookMessage = BloxrouteOpenbookOrderBook.snapshot_message_from_exchange(
            raw_message,
            time.time(),
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise Exception("Bloxroute Openbook does not use orderbook diffs")

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise Exception("Bloxroute Openbook does not use trade updates")

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        pass
    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        raise
