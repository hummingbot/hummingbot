import asyncio
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_utils as utils
import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_derivative import BingXPerpetualDerivative


class BingXPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'BingXPerpetualDerivative',
                 api_factory: Optional[WebAssistantsFactory] = None,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._connector = connector
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
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
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "symbol": symbol,
            "limit": "100"
        }
        data = await self._connector._api_request(
            path_url=CONSTANTS.SNAPSHOT_PATH_URL,
            method=RESTMethod.GET,
            params=params
        )
        snapshot = data.get("data", data)
        snapshot["trading_pair"] = trading_pair
        snapshot["timestamp"] = data.get("timestamp", int(time.time() * 1e3))
        return snapshot

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = float(snapshot.get("timestamp", time.time() * 1e3)) * 1e-3
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessage.SNAPSHOT,
            content=snapshot,
            timestamp=snapshot_timestamp
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message["dataType"].split('@')[0]
        trade_data = raw_message.get("data", raw_message)
        trade_message = OrderBookMessage(
            message_type=OrderBookMessage.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_type": float(trade_data.get("m", True)),
                "trade_id": trade_data.get("t", str(time.time())),
                "update_id": trade_data.get("t", str(time.time())),
                "price": trade_data.get("p", "0"),
                "amount": trade_data.get("q", "0"),
            },
            timestamp=float(trade_data.get("T", time.time() * 1e3)) * 1e-3
        )
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message.get('dataType', '').split('@')[0]
        diff_data = raw_message.get("data", raw_message)
        order_book_message = OrderBookMessage(
            message_type=OrderBookMessage.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": diff_data.get("t", int(time.time() * 1e3)),
                "bids": diff_data.get("bids", []),
                "asks": diff_data.get("asks", []),
            },
            timestamp=self._time()
        )
        message_queue.put_nowait(order_book_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
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
                await self._sleep(5.0)

    async def listen_for_subscriptions(self):
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
                        payload = {"ping": int(ping_time * 1e3)}
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
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                trade_payload = {
                    "id": "trade",
                    "reqType": "sub",
                    "dataType": f"{symbol}@trade"
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trade_payload)

                depth_payload = {
                    "id": "depth",
                    "reqType": "sub",
                    "dataType": f"{symbol}@depth20"
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
            data = utils.decompress_ws_message(ws_response.data)
            if isinstance(data, dict):
                if data.get("msg") == "SUCCESS":
                    continue
                if data.get("ping"):
                    payload = "pong"
                    ping_request = WSJSONRequest(payload=payload)
                    await ws.send(request=ping_request)
                elif data.get("dataType"):
                    symbol = data.get("dataType").split('@')[0]
                    event_type = data.get("dataType").split('@')[1]
                    # Remove depth level suffix (e.g. depth20 -> depth)
                    if event_type.startswith("depth"):
                        event_type = CONSTANTS.DIFF_EVENT_TYPE
                    data['symbol'] = symbol
                    if event_type == CONSTANTS.DIFF_EVENT_TYPE:
                        self._message_queue[CONSTANTS.DIFF_EVENT_TYPE].put_nowait(data)
                    elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
                        self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(data)

    async def _process_ob_snapshot(self, snapshot_queue: asyncio.Queue):
        message_queue = self._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()
                trading_pair = json_msg["symbol"]
                order_book_message = OrderBookMessage(
                    message_type=OrderBookMessage.SNAPSHOT,
                    content={
                        "trading_pair": trading_pair,
                        "update_id": json_msg.get("data", {}).get("t", int(time.time() * 1e3)),
                        "bids": json_msg.get("data", {}).get("bids", []),
                        "asks": json_msg.get("data", {}).get("asks", []),
                    },
                    timestamp=self._time()
                )
                snapshot_queue.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error when processing public order book updates from exchange")
                raise

    async def _take_full_order_book_snapshot(self, trading_pairs: List[str], snapshot_queue: asyncio.Queue):
        for trading_pair in trading_pairs:
            try:
                snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair=trading_pair)
                snapshot_timestamp: float = float(snapshot.get("timestamp", time.time() * 1e3)) * 1e-3
                snapshot_msg = OrderBookMessage(
                    message_type=OrderBookMessage.SNAPSHOT,
                    content={
                        "trading_pair": trading_pair,
                        "update_id": snapshot.get("t", int(time.time() * 1e3)),
                        "bids": snapshot.get("bids", []),
                        "asks": snapshot.get("asks", []),
                    },
                    timestamp=snapshot_timestamp
                )
                snapshot_queue.put_nowait(snapshot_msg)
                self.logger().debug(f"Saved order book snapshot for {trading_pair}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                    exc_info=True)
                await self._sleep(5.0)

    def _time(self):
        return time.time()
