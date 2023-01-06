import asyncio
import time
from abc import ABC
from typing import AsyncGenerator, TYPE_CHECKING, Any, Dict, List, Optional

from aiostream import stream
from bxsolana.provider import HttpProvider, WsProvider

from hummingbot.connector.exchange.bloxroute_openbook import bloxroute_openbook_constants as CONSTANTS
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
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

    def __init__(self,
                 ws_provider: WsProvider,
                 rpc_provider: HttpProvider,
                 trading_pairs: List[str],
                 connector: 'BloxrouteOpenbookExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._ws_provider = ws_provider
        self._rpc_provider = rpc_provider
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory
        self._combined_trade_stream: AsyncGenerator
        self._combined_orderbook_stream: AsyncGenerator

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._rpc_provider.get_price()  # TODO we need to create an endpoint for trading_pairs

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """

        orderbook = await self._rpc_provider.get_orderbook(market=trading_pair, project=OPENBOOK_PROJECT)
        return orderbook.to_dict()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_streams = []
            for trading_pair in self._trading_pairs:
                trade_stream = self._ws_provider.get_trades_stream(market=trading_pair, project=OPENBOOK_PROJECT)
                trade_streams.append(trade_stream)

            self._combined_trade_stream = stream.merge(*trade_streams)
            self._combined_orderbook_stream = self._ws_provider.get_orderbooks_stream(markets=self._trading_pairs,
                                                                                      project=OPENBOOK_PROJECT)

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
        await self._ws_provider.connect()
        await self._rpc_provider.connect()

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
            trade_message = BinanceOrderBook.trade_message_from_exchange(
                raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
            order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        raise Exception("Bloxroute Openbook does not use `_channel_originating_message`")

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        raise Exception("Bloxroute Openbook does not use orderbook diffs")

    async def _process_websocket_messages(self, _: WSAssistant):
        self._process_trade_events_task = safe_ensure_future(
            self._handle_trade_events()
        )

        self._process_order_book_events_task = safe_ensure_future(
            self._handle_order_book_updates()
        )

    async def _handle_trade_events(self):
        trade_queue = self._message_queue[self._trade_messages_queue_key]
        async for trade_event in self._combined_trade_stream:
            trade_queue.put_nowait(trade_event)

    async def _handle_order_book_updates(self):
        orderbook_queue = self._message_queue[self._snapshot_messages_queue_key]
        async for orderbook_event in self._combined_orderbook_stream:
            orderbook_queue.put_nowait(orderbook_event)

    @property
    async def process_trade_events_task(self):
        return self._process_trade_events_task

    @property
    async def process_order_book_events_task(self):
        return self._process_order_book_events_task
