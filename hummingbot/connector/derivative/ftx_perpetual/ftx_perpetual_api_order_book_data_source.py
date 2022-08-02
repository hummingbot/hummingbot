import asyncio
import logging
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import simplejson
import ujson
import websockets
from signalr_aio import Connection
from websockets.exceptions import ConnectionClosed

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_order_book import FtxPerpetualOrderBook
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger

EXCHANGE_NAME = "ftx_perpetual"

FTX_REST_URL = "https://ftx.com/api"
FTX_EXCHANGE_INFO_PATH = "/markets"
FTX_WS_FEED = "wss://ftx.com/ws/"

MAX_RETRIES = 20
SNAPSHOT_TIMEOUT = 10.0
NaN = float("nan")
API_CALL_TIMEOUT = 5.0


class FtxPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _ftxaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ftxaobds_logger is None:
            cls._ftxaobds_logger = logging.getLogger(__name__)
        return cls._ftxaobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__(trading_pairs)
        self._websocket_connection: Optional[Connection] = None
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            async with await client.get(f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}", timeout=API_CALL_TIMEOUT) as response:
                response_json = await response.json()
                results = response_json['result']
                return {convert_from_exchange_trading_pair(result['name']): float(result['last'])
                        for result in results if convert_from_exchange_trading_pair(result['name']) in trading_pairs}

    async def get_trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        async with client.get(f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/{convert_to_exchange_trading_pair(trading_pair)}/orderbook?depth=100") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching FTX market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = simplejson.loads(await response.text(), parse_float=Decimal)

            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
            snapshot_timestamp: float = self._time()
            snapshot_msg: OrderBookMessage = FtxPerpetualOrderBook.restful_snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        async with aiohttp.ClientSession() as client:
            snapshot_response: Dict[str, Any] = await self.get_snapshot(
                client=client,
                trading_pair=trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response["result"]
        snapshot_timestamp: float = self._time()
        update_id: int = int(snapshot_timestamp)

        order_book_message_content = {
            "market": convert_to_exchange_trading_pair(trading_pair),
            "trading_pair": trading_pair,
            "update_id": update_id,
            "data": {
                "bids": [(price, amount) for price, amount in snapshot_data.get("bids", [])],
                "asks": [(price, amount) for price, amount in snapshot_data.get("asks", [])],
            }
        }
        snapshot_msg: OrderBookMessage = FtxPerpetualOrderBook.snapshot_message_from_exchange(
            msg=order_book_message_content,
            timestamp=snapshot_timestamp,
        )

        return snapshot_msg

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws = websockets.connect(FTX_WS_FEED)
                for pair in self._trading_pairs:
                    subscribe_request: Dict[str, Any] = {
                        "op": "subscribe",
                        "channel": "trades",
                        "market": convert_to_exchange_trading_pair(pair)
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                async for raw_msg in self._inner_messages(ws):
                    msg = simplejson.loads(raw_msg, parse_float=Decimal)
                    if "channel" in msg:
                        if msg["channel"] == "trades" and msg["type"] == "update":
                            for trade in msg["data"]:
                                trade_msg: OrderBookMessage = FtxPerpetualOrderBook.trade_message_from_exchange(msg, trade)
                                output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
            finally:
                if ws is not None:
                    ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws = websockets.connect(FTX_WS_FEED)
                for pair in self._trading_pairs:
                    subscribe_request: Dict[str, Any] = {
                        "op": "subscribe",
                        "channel": "orderbook",
                        "market": convert_to_exchange_trading_pair(pair)
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                async for raw_msg in self._inner_messages(ws):
                    msg = simplejson.loads(raw_msg, parse_float=Decimal)
                    if "channel" in msg:
                        if msg["channel"] == "orderbook" and msg["type"] == "update":
                            order_book_message: OrderBookMessage = FtxPerpetualOrderBook.diff_message_from_exchange(msg, msg["data"]["time"])
                            output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
            finally:
                if ws is not None:
                    ws.close()

    async def listen_for_subscriptions(self):
        pass
