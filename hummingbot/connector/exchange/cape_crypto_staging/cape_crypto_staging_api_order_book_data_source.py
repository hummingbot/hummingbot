import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.cape_crypto_staging import (
    cape_crypto_staging_constants as CONSTANTS,
    cape_crypto_staging_web_utils as web_utils,
)
from hummingbot.connector.exchange.cape_crypto_staging.cape_crypto_staging_order_book import CapeCryptoStagingOrderBookBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.cape_crypto_staging.cape_crypto_staging_exchange import CapeCryptoStagingExchange


class CapeCryptoStagingAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 25.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CapeCryptoStagingExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_CHANNEL_ID
        self._domain = domain
        self._api_factory = api_factory
        self._last_ws_message_sent_timestamp = 0

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
 
        pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL.format(pair), domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the 'diff' orders events through the provided websocket connection.
        Cape Crypto subscribes to the orderbook wss during url connection
        :param ws: the websocket assistant used to connect to the exchange
        """
        pass

    def _get_messages_queue_keys(self) -> List[str]:
        return [self._snapshot_messages_queue_key, self._diff_messages_queue_key]

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        snapshots = '?stream='
        for trading_pair in self._trading_pairs:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            snapshots += f"{symbol.lower()}.ob-inc&"
        
        await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL.format(snapshots), ping_timeout=CONSTANTS.WSS_PING_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot['sequence'] = 1
        snapshot_msg: OrderBookMessage = CapeCryptoStagingOrderBookBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pair = next(iter(raw_message)).split(".ob")[0]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CapeCryptoStagingOrderBookBook.snapshot_message_from_exchange(
            raw_message[next(iter(raw_message))],
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        message_queue.put_nowait(snapshot_msg)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
        trade_message = CapeCryptoStagingOrderBookBook.trade_message_from_exchange(
            raw_message, {"trading_pair": trading_pair})
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pair = next(iter(raw_message)).split(".ob")[0]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=pair)
        diff_timestamp: float = time.time()
        diff_msg: OrderBookMessage = CapeCryptoStagingOrderBookBook.diff_message_from_exchange(
            raw_message[next(iter(raw_message))],
            diff_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        message_queue.put_nowait(diff_msg)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        msg_key = next(iter(event_message))
        if "ob-snap" in msg_key:
            channel = self._snapshot_messages_queue_key
        if "ob-inc" in msg_key:
            channel = self._diff_messages_queue_key
        
        return channel
