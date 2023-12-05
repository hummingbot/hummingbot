import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.penumbra import penumbra_utils as utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.penumbra.penumbra_exchange import PenumbraExchange


class PenumbraAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: "PenumbraExchange",
        api_factory: Optional[WebAssistantsFactory] = None,
        domain: str = 'localhost:8081',
        throttler: Optional[AsyncThrottler] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or utils.build_api_factory(
            throttler=self._throttler,
        )
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0

    # TODO: Need to actually implement

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        print("get_last_traded_prices")
        raise NotImplementedError

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        print("_order_book_snapshot")
        raise NotImplementedError

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        print("_request_order_book_snapshot")
        raise NotImplementedError

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        print("_parse_trade_message")
        raise NotImplementedError

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        print("_parse_order_book_diff_message")
        raise NotImplementedError

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        print("_subscribe_channels")

        raise NotImplementedError

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        print("_channel_originating_message")
        raise NotImplementedError

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        print("_process_websocket_messages")
        raise NotImplementedError

    async def _connected_websocket_assistant(self) -> WSAssistant:
        print("_connected_websocket_assistant")
        raise NotImplementedError
