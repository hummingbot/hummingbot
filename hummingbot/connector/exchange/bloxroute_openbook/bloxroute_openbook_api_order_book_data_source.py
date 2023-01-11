import asyncio
import time
from abc import ABC
from typing import Any, AsyncGenerator, Dict, List, Optional, TYPE_CHECKING

from bxsolana.provider import WsProvider
from bxsolana_trader_proto import GetOrderbooksStreamResponse

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import BloxrouteOpenbookOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_exchange import BloxrouteOpenbookExchange


class BloxrouteOpenbookAPIOrderBookDataSource(OrderBookTrackerDataSource, ABC):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, ws_provider: WsProvider, trading_pairs: List[str], connector: 'BloxrouteOpenbookExchange'):
        super().__init__(trading_pairs)

        self._ws_provider = ws_provider
        self._connector = connector
        self._orderbook_stream: Optional[AsyncGenerator[GetOrderbooksStreamResponse, None]] = None

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        for trading_pair in self._trading_pairs:
            output.put_nowait(await self._order_book_snapshot(trading_pair))

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        orderbook = await self._ws_provider.get_orderbook(market=trading_pair, project=OPENBOOK_PROJECT)

        return BloxrouteOpenbookOrderBook.snapshot_message_from_exchange(
            orderbook.to_dict(include_default_values=True),
            time.time(),
            {"trading_pair": trading_pair}
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        await self._ws_provider.connect()
        return WSAssistant()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            self._orderbook_stream = self._ws_provider.get_orderbooks_stream(markets=self._trading_pairs,
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
        raise Exception("Bloxroute Openbook does not use orderbook diffs")

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        raise Exception("Bloxroute Openbook does not use trades")

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        self._ws_provider and await self._ws_provider.close()
