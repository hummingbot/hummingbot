#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import ujson
import websockets

import hummingbot.connector.exchange.k2.k2_constants as constants

from typing import Optional, List, Dict, AsyncIterable, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.k2.k2_order_book import K2OrderBook
from hummingbot.connector.exchange.k2 import k2_utils


class K2APIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 60.0
    SNAPSHOT_TIMEOUT = 10.0
    PING_TIMEOUT = 30.0
    SNAPSHOT_INTERVAL = 300

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}{constants.GET_TRADING_PAIRS_STATS}") as resp:
                resp_json = await resp.json()
                if resp_json["success"] is False:
                    raise IOError(
                        f"Error fetching last traded prices at {constants.EXCHANGE_NAME}. "
                        f"HTTP status is {resp.status}."
                        f"Content: {resp.content}"
                    )
                for t_pair in trading_pairs:
                    last_trade = [o["lastprice"]
                                  for o in resp_json["data"] if o["symbol"] == k2_utils.convert_to_exchange_trading_pair(t_pair)]
                    if last_trade and last_trade[0] is not None:
                        result[t_pair] = last_trade[0]
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}{constants.GET_TRADING_PAIRS}", timeout=10) as response:
                if response.status == 200:
                    try:
                        data: Dict[str, Any] = await response.json()
                        return [k2_utils.convert_from_exchange_trading_pair(item["symbol"]) for item in data["data"]]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Obtain orderbook using REST API
        """
        async with aiohttp.ClientSession() as client:
            params = {"symbol": k2_utils.convert_to_exchange_trading_pair(trading_pair)}
            async with client.get(url=f"{constants.REST_URL}{constants.GET_ORDER_BOOK}",
                                  params=params) as resp:
                if resp.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {constants.EXCHANGE_NAME}. "
                        f"HTTP status is {resp.status}."
                    )

                orderbook_data: Dict[str, Any] = await resp.json()

        return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: int = int(time.time() * 1e3)
        snapshot_msg: OrderBookMessage = K2OrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        bids, asks = k2_utils.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
        except asyncio.TimeoutError:
            pong_waiter = await ws.ping()
            await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                async with websockets.connect(uri=constants.WSS_URL,
                                              ping_timeout=self.PING_TIMEOUT) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in self._trading_pairs:
                        params: Dict[str, Any] = {
                            "name": "SubscribeTrades",
                            "data": k2_utils.convert_to_exchange_trading_pair(trading_pair)
                        }
                        await ws.send(ujson.dumps(params))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if msg["method"] != "marketchanged":
                            continue
                        for trade_entry in msg["data"]["trades"]:
                            trade_msg: OrderBookMessage = K2OrderBook.trade_message_from_exchange(trade_entry)
                            output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            async with websockets.connect(constants.WSS_URL) as ws:
                try:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in self._trading_pairs:
                        params: Dict[str, Any] = {
                            "name": "SubscribeOrderBook",
                            "data": k2_utils.convert_to_exchange_trading_pair(trading_pair)
                        }
                        await ws.send(ujson.dumps(params))
                    async for raw_msg in self._inner_messages(ws):
                        response = ujson.loads(raw_msg)
                        timestamp = int(time.time() * 1e3)
                        if response["method"] == "SubscribeOrderBook":
                            trading_pair = k2_utils.convert_from_exchange_trading_pair(response["pair"])
                            message: OrderBookMessage = K2OrderBook.snapshot_message_from_exchange(
                                msg=response,
                                timestamp=timestamp,
                                metadata={"trading_pair": trading_pair})
                        elif response["method"] == "orderbookchanged":
                            data = ujson.loads(response["data"])
                            trading_pair = k2_utils.convert_from_exchange_trading_pair(data["pair"])
                            message: OrderBookMessage = K2OrderBook.diff_message_from_exchange(
                                msg=data,
                                timestamp=timestamp,
                                metadata={"trading_pair": trading_pair})
                        else:
                            # Ignores all other messages
                            continue
                        output.put_nowait(message)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().network(
                        "Unexpected error with WebSocket connection.",
                        exc_info=True,
                        app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                        "Check network connection."
                    )
                    await asyncio.sleep(30.0)
                finally:
                    await ws.close()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook using the REST API.
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_timestamp: int = int(time.time() * 1e3)
                        snapshot_msg: OrderBookMessage = K2OrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error occured retrieving Order Book Data using REST API. Retying in 5 seconds",
                            exc_info=True
                        )
                        await asyncio.sleep(5.0)
                await asyncio.sleep(self.SNAPSHOT_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occured.", exc_info=True)
                await asyncio.sleep(5.0)
