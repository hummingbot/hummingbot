#!/usr/bin/env python
import datetime

import aiohttp
import asyncio
import json
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.peatio.peatio_order_book import PeatioOrderBook
from hummingbot.connector.exchange.peatio.peatio_utils import convert_to_exchange_trading_pair, PeatioAPIError

PEATIO_BASE_API_URL = "https://market.bitzlato.com/api/v2/peatio"
PEATIO_WS_URL = "wss://market.bitzlato.com/api/v2/ranger/public"

PEATIO_TRADES_STREAM = "stream={market}.trades"

PEATIO_MARKETS_PATH = "/public/markets"
PEATIO_TICKER_PATH = "/public/markets/tickers"
PEATIO_DEPTH_PATH = "/public/markets/{market}/depth"


class PeatioAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def http_api_request(cls, method: str, path: str, params: Optional[Dict[str, Any]] = None,
                               data=None, client: aiohttp.ClientSession = None):
        assert path.startswith('/'), 'path must be start switch on "/"'
        content_type = "application/json"
        accept = "application/json"

        headers = {
            "Content-Type": content_type,
            "Accept": accept,
        }

        url = PEATIO_BASE_API_URL + path
        if client is None:
            async with aiohttp.ClientSession() as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    data=ujson.dumps(data) if data is not None else None,
                )
        else:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                data=ujson.dumps(data) if data is not None else None,
            )
        if resp.status not in [200, 201]:
            raise IOError(f"Error fetching data from {url}. HTTP status is {resp.status}.")

        try:
            return await resp.json()
        except Exception:
            raise IOError(f"Error parsing data from {url}.")

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        resp_json = await cls.http_api_request(method='get', path=PEATIO_TICKER_PATH)
        for trading_pair in trading_pairs:
            resp_record = resp_json.get(convert_to_exchange_trading_pair(trading_pair))
            if resp_record is None:
                continue
            results[trading_pair] = float(resp_record["ticker"]["last"])
        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            from hummingbot.connector.exchange.peatio.peatio_utils import convert_from_exchange_trading_pair
            valid_trading_pairs: list = []
            trading_pair_list: List[str] = []

            all_trading_pairs = await PeatioAPIOrderBookDataSource.http_api_request(
                method='get',
                path=PEATIO_MARKETS_PATH
            )

            for item in all_trading_pairs:
                if item["state"] == "enabled":
                    valid_trading_pairs.append(item["symbol"])

            for raw_trading_pair in valid_trading_pairs:
                converted_trading_pair: Optional[str] = convert_from_exchange_trading_pair(raw_trading_pair)
                if converted_trading_pair is not None:
                    trading_pair_list.append(converted_trading_pair)

            return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for peatio trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        api_data = await PeatioAPIOrderBookDataSource.http_api_request(
            method='get',
            path=PEATIO_DEPTH_PATH.format(market=convert_to_exchange_trading_pair(trading_pair)),
            client=client
        )
        return api_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_msg: OrderBookMessage = PeatioOrderBook.snapshot_message_from_exchange(
                msg=snapshot,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(PEATIO_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "streams": [
                            f"{convert_to_exchange_trading_pair(trading_pair)}.trades"
                            for trading_pair in trading_pairs
                        ],
                        "event": "subscribe"
                    }
                    await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "error" in msg:
                            raise PeatioAPIError(msg["error"]["message"])
                        elif len(set(subscribe_request["streams"]).intersection(set(msg.keys()))) > 0:
                            for stream_name in set(subscribe_request["streams"]).intersection(set(msg.keys())):
                                trading_pair = stream_name.split(".")[1]
                                data = {
                                    "direction": msg[stream_name]["taker_type"],
                                    "id": msg[stream_name]["tid"],
                                    "amount": msg[stream_name]["amount"],
                                    "price": msg[stream_name]["price"],
                                    "timestamp": msg[stream_name]["created_at"],
                                }
                                trade_message: OrderBookMessage = PeatioOrderBook.trade_message_from_exchange(
                                    data, metadata={"trading_pair": trading_pair}
                                )
                                output.put_nowait(trade_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Peatio websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(PEATIO_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "streams": [
                            f"{convert_to_exchange_trading_pair(trading_pair)}.ob-inc"
                            for trading_pair in trading_pairs
                        ],
                        "event": "subscribe"
                    }
                    await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "error" in msg:
                            raise PeatioAPIError(msg["error"]["message"])
                        elif len(set(subscribe_request["streams"]).intersection(set(msg.keys()))) > 0:
                            for stream_name in set(subscribe_request["streams"]).intersection(set(msg.keys())):
                                trading_pair = stream_name.split(".")[1]
                                data = {
                                    "bids": msg[stream_name]["bids"],
                                    "asks": msg[stream_name]["asks"],
                                    "timestamp": datetime.datetime.utcnow(),
                                }

                                order_book_message: OrderBookMessage = PeatioOrderBook.diff_message_from_exchange(data, metadata={"trading_pair": trading_pair})
                                output.put_nowait(order_book_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Peatio websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(
                                client,
                                convert_to_exchange_trading_pair(trading_pair)
                            )
                            snapshot_message: OrderBookMessage = PeatioOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
