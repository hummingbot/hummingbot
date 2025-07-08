import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
    foxbit_utils as utils,
    foxbit_web_utils as web_utils,
)
from hummingbot.connector.exchange.foxbit.foxbit_order_book import (
    FoxbitOrderBook,
    FoxbitOrderBookFields,
    FoxbitTradeFields,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.foxbit.foxbit_exchange import FoxbitExchange


class FoxbitAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_exc_id = {}
    _trading_pair_hb_dict = {}
    _ORDER_BOOK_INTERVAL = 1.0

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'FoxbitExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = "trade"
        self._diff_messages_queue_key = "order_book_diff"
        self._domain = domain
        self._api_factory = api_factory
        self._first_update_id = {}
        for trading_pair in self._trading_pairs:
            self._first_update_id[trading_pair] = 0

        self._live_stream_connected = {}

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair

        :param trading_pair: the trading pair for which the order book has to be retrieved

        :return: a local copy of the current order book in the exchange
        """
        await self._load_exchange_instrument_id()
        instrument_id = await self._get_instrument_id_from_trading_pair(trading_pair)
        self._live_stream_connected[instrument_id] = False

        snapshot_msg: OrderBookMessage = await self._order_book_snapshot(trading_pair=trading_pair)
        order_book: OrderBook = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """

        instrument_id = await self._get_instrument_id_from_trading_pair(trading_pair)
        wait_count = 0

        while (not (instrument_id in self._live_stream_connected) or self._live_stream_connected[instrument_id] is False) and wait_count < 30:
            self.logger().info("Waiting for real time stream before getting a snapshot")
            await asyncio.sleep(self._ORDER_BOOK_INTERVAL)
            wait_count += 1

        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL.format(symbol[0]), domain=self._domain),
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
                # Subscribe OrderBook
                header = utils.get_ws_message_frame(endpoint=CONSTANTS.WS_SUBSCRIBE_ORDER_BOOK,
                                                    msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Subscribe"],
                                                    payload={"OMSId": 1, "InstrumentId": await self._get_instrument_id_from_trading_pair(trading_pair), "Depth": CONSTANTS.ORDER_BOOK_DEPTH},)
                subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header))
                await ws.send(subscribe_request)

                header = utils.get_ws_message_frame(endpoint=CONSTANTS.WS_SUBSCRIBE_TRADES,
                                                    msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Subscribe"],
                                                    payload={"InstrumentId": await self._get_instrument_id_from_trading_pair(trading_pair)},)
                subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header))
                await ws.send(subscribe_request)

            self.logger().info("Subscribed to public order book channel...")
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
        await ws.connect(ws_url=web_utils.websocket_url(), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = FoxbitOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        self._first_update_id[trading_pair] = snapshot['sequence_id']
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if CONSTANTS.WS_SUBSCRIBE_TRADES or CONSTANTS.WS_TRADE_RESPONSE in raw_message['n']:
            full_msg = eval(raw_message['o'].replace(",false,", ",False,"))
            for msg in full_msg:
                instrument_id = int(msg[FoxbitTradeFields.INSTRUMENTID.value])
                trading_pair = ""

                if instrument_id not in self._trading_pair_hb_dict:
                    trading_pair = await self._get_trading_pair_from_instrument_id(instrument_id)
                else:
                    trading_pair = self._trading_pair_hb_dict[instrument_id]

                trade_message = FoxbitOrderBook.trade_message_from_exchange(
                    msg=msg,
                    metadata={"trading_pair": trading_pair},
                )
                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if CONSTANTS.WS_ORDER_BOOK_RESPONSE or CONSTANTS.WS_ORDER_STATE in raw_message['n']:
            full_msg = eval(raw_message['o'])
            for msg in full_msg:
                instrument_id = int(msg[FoxbitOrderBookFields.PRODUCTPAIRCODE.value])

                trading_pair = ""

                if instrument_id not in self._trading_pair_hb_dict:
                    trading_pair = await self._get_trading_pair_from_instrument_id(instrument_id)
                else:
                    trading_pair = self._trading_pair_hb_dict[instrument_id]

                order_book_message: OrderBookMessage = FoxbitOrderBook.diff_message_from_exchange(
                    msg=msg,
                    metadata={"trading_pair": trading_pair},
                )
                message_queue.put_nowait(order_book_message)
                self._live_stream_connected[instrument_id] = True

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "o" in event_message:
            event_type = event_message.get("n")
            if event_type == CONSTANTS.WS_SUBSCRIBE_TRADES:
                return self._trade_messages_queue_key
            elif event_type == CONSTANTS.WS_ORDER_BOOK_RESPONSE:
                return self._diff_messages_queue_key
        return channel

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _load_exchange_instrument_id(self):
        for trading_pair in self._trading_pairs:
            instrument_id = int(await self._connector.exchange_instrument_id_associated_to_pair(trading_pair=trading_pair))
            self._trading_pair_exc_id[trading_pair] = instrument_id
            self._trading_pair_hb_dict[instrument_id] = trading_pair

    async def _get_trading_pair_from_instrument_id(self, instrument_id: int) -> str:
        if instrument_id not in self._trading_pair_hb_dict:
            await self._load_exchange_instrument_id()
        return self._trading_pair_hb_dict[instrument_id]

    async def _get_instrument_id_from_trading_pair(self, traiding_pair: str) -> int:
        if traiding_pair not in self._trading_pair_exc_id:
            await self._load_exchange_instrument_id()
        return self._trading_pair_exc_id[traiding_pair]
