import asyncio
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from bxsolana import Provider
from bxsolana_trader_proto import GetOrderbookResponse, GetOrderbooksStreamResponse

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import SPOT_ORDERBOOK_PROJECT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import BloxrouteOpenbookOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_exchange import BloxrouteOpenbookExchange


class BloxrouteOpenbookAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self, provider: Provider, trading_pairs: List[str], connector: "BloxrouteOpenbookExchange"):
        super().__init__(trading_pairs)

        self._provider = provider
        self._connector = connector

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        orderbook: GetOrderbookResponse = await self._provider.get_orderbook(
            market=trading_pair, limit=1, project=SPOT_ORDERBOOK_PROJECT
        )

        snapshot_timestamp: float = time.time()

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(time.time()),
            "bids": [(bid.price, bid.size) for bid in orderbook.bids],
            "asks": [(ask.price, ask.size) for ask in orderbook.asks],
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, order_book_message_content, snapshot_timestamp)

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        raise NotImplementedError

    async def _process_websocket_messages(self, _: WSAssistant):
        pass

    async def listen_for_subscriptions(self):
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        pass

    # connector does not use Websocket assistant
    async def _connected_websocket_assistant(self) -> WSAssistant:
        raise NotImplementedError

    async def _subscribe_channels(self, ws: WSAssistant):
        raise NotImplementedError

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        pass
