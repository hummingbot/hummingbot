import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitrue import bitrue_constants as CONSTANTS, bitrue_web_utils as web_utils
from hummingbot.connector.exchange.bitrue.bitrue_order_book import BitrueOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitrue.bitrue_exchange import BitrueExchange


class BitrueAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 15.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'BitrueExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE
        self._domain = domain
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
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": 1000
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                payload = {
                    "event": "sub",
                    "params": {
                        "cb_id": symbol.lower(),
                        "channel": f"market_{symbol.lower()}_simple_depth_step0"
                    },
                }

                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book channels. Bitrues does not have trade channels.")
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
        await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL,
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot["lastUpdateId"] = int(self._time() * 1e3)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BitrueOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "tick" in raw_message:
            symbol = raw_message["channel"].split("_")[1].split("_")[0].upper()
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

            # pre-process raw message according to the REST format
            raw_message["bids"] = raw_message["tick"]["buys"]
            raw_message["asks"] = raw_message["tick"]["asks"]
            raw_message["lastUpdateId"] = int(self._time() * 1e3)

            del raw_message["tick"]
            del raw_message["channel"]
            del raw_message["ts"]

            order_book_message: OrderBookMessage = BitrueOrderBook.snapshot_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if "channel" in event_message:
            channel_name = ""
            channel = event_message["channel"]
            channel = (self._snapshot_messages_queue_key if self._snapshot_messages_queue_key in channel else self._trade_messages_queue_key)
            return channel_name

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = self._connector.decompress_ws_data(ws_response.data)
            if data is not None:  # data will be None when the websocket is disconnected
                channel: str = self._channel_originating_message(event_message=data)
                valid_channels = self._get_messages_queue_keys()
                if channel in valid_channels:
                    self._message_queue[channel].put_nowait(data)
                else:
                    await self._process_message_for_unknown_channel(
                        event_message=data, websocket_assistant=websocket_assistant
                    )
