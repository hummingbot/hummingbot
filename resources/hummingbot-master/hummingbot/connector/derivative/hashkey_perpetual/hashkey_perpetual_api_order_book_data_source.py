import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from hummingbot.connector.derivative.hashkey_perpetual import (
    hashkey_perpetual_constants as CONSTANTS,
    hashkey_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_order_book import HashkeyPerpetualsOrderBook
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.hashkey_perpetual.hashkey_perpetual_derivative import (
        HashkeyPerpetualDerivative,
    )


class HashkeyPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    ONE_HOUR = 60 * 60
    FIVE_MINUTE = 60 * 5
    EXCEPTION_INTERVAL = 5

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'HashkeyPerpetualDerivative',
                 api_factory: Optional[WebAssistantsFactory] = None,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._time_synchronizer = time_synchronizer
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
        )
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
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
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "1000"
        }
        data = await self._connector._api_request(path_url=CONSTANTS.SNAPSHOT_PATH_URL,
                                                  method=RESTMethod.GET,
                                                  params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = float(snapshot["t"]) * 1e-3
        snapshot_msg: OrderBookMessage = HashkeyPerpetualsOrderBook.snapshot_message_from_exchange_rest(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["symbol"])
        for trades in raw_message["data"]:
            trades["q"] = self._connector.get_amount_of_contracts(trading_pair, int(trades["q"]))
            trade_message: OrderBookMessage = HashkeyPerpetualsOrderBook.trade_message_from_exchange(
                trades, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Hashkey not support funding info in websocket
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        This method runs continuously and request the full order book content from the exchange every hour.
        The method uses the REST API from the exchange because it does not provide an endpoint to get the full order
        book through websocket. With the information creates a snapshot messages that is added to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        while True:
            try:
                await asyncio.wait_for(self._process_ob_snapshot(snapshot_queue=output), timeout=self.ONE_HOUR)
            except asyncio.TimeoutError:
                await self._take_full_order_book_snapshot(trading_pairs=self._trading_pairs, snapshot_queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._take_full_order_book_snapshot(trading_pairs=self._trading_pairs, snapshot_queue=output)
                await self._sleep(self.EXCEPTION_INTERVAL)

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Reads the funding info events queue and updates the local funding info information.
        """
        while True:
            try:
                # hashkey global not support funding rate event
                await self._update_funding_info_by_api(self._trading_pairs, message_queue=output)
                await self._sleep(self.FIVE_MINUTE)
            except Exception as e:
                self.logger().exception(f"Unexpected error when processing public funding info updates from exchange: {e}")
                await self._sleep(self.EXCEPTION_INTERVAL)

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL[self._domain])
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()

                while True:
                    try:
                        seconds_until_next_ping = (CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL - (
                            self._time() - self._last_ws_message_sent_timestamp))
                        await asyncio.wait_for(self._process_ws_messages(ws=ws), timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        ping_time = self._time()
                        payload = {
                            "ping": int(ping_time * 1e3)
                        }
                        ping_request = WSJSONRequest(payload=payload)
                        await ws.send(request=ping_request)
                        self._last_ws_message_sent_timestamp = ping_time
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(self.EXCEPTION_INTERVAL)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_payload = {
                    "topic": "trade",
                    "event": "sub",
                    "symbol": symbol,
                    "params": {
                        "binary": False
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trade_payload)

                depth_payload = {
                    "topic": "depth",
                    "event": "sub",
                    "symbol": symbol,
                    "params": {
                        "binary": False
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=depth_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)

                self.logger().info(f"Subscribed to public order book and trade channels of {trading_pair}...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _process_ws_messages(self, ws: WSAssistant):
        async for ws_response in ws.iter_messages():
            data = ws_response.data
            if data.get("msg") == "Success":
                continue
            event_type = data.get("topic")
            if event_type == CONSTANTS.SNAPSHOT_EVENT_TYPE:
                self._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE].put_nowait(data)
            elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
                self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(data)

    async def _process_ob_snapshot(self, snapshot_queue: asyncio.Queue):
        message_queue = self._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                    symbol=json_msg["symbol"])
                for snapshot_data in json_msg["data"]:
                    snapshot = self.convert_snapshot_amounts(snapshot_data, trading_pair)
                    order_book_message: OrderBookMessage = HashkeyPerpetualsOrderBook.snapshot_message_from_exchange_websocket(
                        snapshot, snapshot["t"], {"trading_pair": trading_pair})
                    snapshot_queue.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error when processing public order book updates from exchange")
                raise

    def convert_snapshot_amounts(self, snapshot_data, trading_pair):
        msg = {"a": [], "b": [], "t": snapshot_data["t"]}
        for ask_order_book in snapshot_data["a"]:
            msg["a"].append([ask_order_book[0], self._connector.get_amount_of_contracts(trading_pair, int(ask_order_book[1]))])
        for bid_order_book in snapshot_data["b"]:
            msg["b"].append([bid_order_book[0], self._connector.get_amount_of_contracts(trading_pair, int(bid_order_book[1]))])

        return msg

    async def _take_full_order_book_snapshot(self, trading_pairs: List[str], snapshot_queue: asyncio.Queue):
        for trading_pair in trading_pairs:
            try:
                snapshot_data: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair=trading_pair)
                snapshot = self.convert_snapshot_amounts(snapshot_data, trading_pair)
                snapshot_timestamp: float = float(snapshot["t"]) * 1e-3
                snapshot_msg: OrderBookMessage = HashkeyPerpetualsOrderBook.snapshot_message_from_exchange_rest(
                    snapshot,
                    snapshot_timestamp,
                    metadata={"trading_pair": trading_pair}
                )
                snapshot_queue.put_nowait(snapshot_msg)
                self.logger().debug(f"Saved order book snapshot for {trading_pair}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                    exc_info=True)
                await self._sleep(self.EXCEPTION_INTERVAL)

    async def _update_funding_info_by_api(self, trading_pairs: list, message_queue: asyncio.Queue) -> None:
        funding_rate_list = await self._request_funding_rate()
        funding_infos = {item["symbol"]: item for item in funding_rate_list}
        for trading_pair in trading_pairs:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            index_symbol = await self._connector.exchange_index_symbol_associated_to_pair(trading_pair=trading_pair)
            funding_rate_info = funding_infos[symbol]
            mark_info, index_info = await asyncio.gather(
                self._request_mark_price(symbol),
                self._request_index_price(index_symbol),
            )

            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(index_info["index"][index_symbol]),
                mark_price=Decimal(mark_info["price"]),
                next_funding_utc_timestamp=int(float(funding_rate_info["nextSettleTime"]) * 1e-3),
                rate=Decimal(funding_rate_info["rate"]),
            )

            message_queue.put_nowait(funding_info)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_rate_info, mark_info, index_info = await self._request_complete_funding_info(trading_pair)
        index_symbol = await self._connector.exchange_index_symbol_associated_to_pair(trading_pair=trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(index_info["index"][index_symbol]),
            mark_price=Decimal(mark_info["price"]),
            next_funding_utc_timestamp=int(float(funding_rate_info["nextSettleTime"]) * 1e-3),
            rate=Decimal(funding_rate_info["rate"]),
        )
        return funding_info

    async def _request_complete_funding_info(self, trading_pair: str):
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        index_symbol = await self._connector.exchange_index_symbol_associated_to_pair(trading_pair=trading_pair)

        funding_rate_info, mark_info, index_info = await asyncio.gather(
            self._request_funding_rate(symbol),
            self._request_mark_price(symbol),
            self._request_index_price(index_symbol),
        )
        funding_rate_dict = {item["symbol"]: item for item in funding_rate_info}
        return funding_rate_dict[symbol], mark_info, index_info

    async def _request_funding_rate(self, symbol: str = None):
        params = {"timestamp": int(self._time_synchronizer.time() * 1e3)}
        if symbol:
            params["symbol"] = symbol,
        return await self._connector._api_request(path_url=CONSTANTS.FUNDING_INFO_URL,
                                                  method=RESTMethod.GET,
                                                  params=params)

    async def _request_mark_price(self, symbol: str):
        return await self._connector._api_request(path_url=CONSTANTS.MARK_PRICE_URL,
                                                  method=RESTMethod.GET,
                                                  params={"symbol": symbol})

    async def _request_index_price(self, symbol: str):
        return await self._connector._api_request(path_url=CONSTANTS.INDEX_PRICE_URL,
                                                  method=RESTMethod.GET,
                                                  params={"symbol": symbol})

    def _time(self):
        return time.time()
