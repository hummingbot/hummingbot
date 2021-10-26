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
from hummingbot.connector.exchange.peatio.peatio_urls import PEATIO_ROOT_API, PEATIO_WS_PUBLIC_URL
from hummingbot.connector.exchange.peatio.peatio_order_book import PeatioOrderBook
from hummingbot.connector.exchange.peatio.peatio_utils import convert_to_exchange_trading_pair, PeatioAPIError


PEATIO_TRADES_STREAM = "stream={market}.trades"

PEATIO_MARKETS_PATH = "/public/markets"
PEATIO_TICKER_PATH = "/public/markets/tickers"
PEATIO_DEPTH_PATH = "/public/markets/{market}/depth"


class PeatioAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    STATES = dict()

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

        url = PEATIO_ROOT_API + path
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
        except Exception as e:
            raise IOError(f"Error {e} parsing data from {url}.")

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        resp_json = await cls.http_api_request(method='get', path=PEATIO_TICKER_PATH)
        if resp_json is None:
            return results
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
                async with websockets.connect(PEATIO_WS_PUBLIC_URL) as ws:
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
                                for trade in msg[stream_name]["trades"]:
                                    data = {
                                        "direction": trade["taker_type"],
                                        "id": trade["tid"],
                                        "amount": trade["amount"],
                                        "price": trade["price"],
                                        "timestamp": trade["date"],
                                    }
                                    trade_message: OrderBookMessage = PeatioOrderBook.trade_message_from_exchange(
                                        data, metadata={"trading_pair": trading_pair}
                                    )
                                    output.put_nowait(trade_message)
                        else:
                            self.logger().debug(f"Unrecognized message [listen_for_trades] received from Peatio websocket: {msg}")
            except asyncio.CancelledError as e:
                self.logger().error(e)
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(PEATIO_WS_PUBLIC_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "streams": [
                            f"{convert_to_exchange_trading_pair(trading_pair)}.ob-inc"
                            for trading_pair in trading_pairs
                        ],
                        "event": "subscribe"
                    }
                    required_streams = set(subscribe_request["streams"])
                    required_streams.update(
                        {f"{convert_to_exchange_trading_pair(trading_pair)}.ob-snap" for trading_pair in trading_pairs}
                    )
                    await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        self.logger().info(f"stream msg: {msg}")
                        if "error" in msg:
                            raise PeatioAPIError(msg["error"]["message"])
                        elif len(required_streams.intersection(set(msg.keys()))) > 0:
                            for stream_name in required_streams.intersection(set(msg.keys())):
                                trading_pair = stream_name.split(".")[0]
                                sequence = msg[stream_name].get("sequence", 0)
                                if sequence <= self.STATES.get(trading_pair, {}).get("last_sequence", -1):
                                    continue
                                if stream_name.endswith(".ob-snap"):
                                    self.STATES[trading_pair] = {
                                        "last_sequence": sequence,
                                        "bids": dict(msg[stream_name].get("bids", [])),
                                        "asks": dict(msg[stream_name].get("asks", [])),
                                    }
                                elif stream_name.endswith(".ob-inc"):
                                    self.STATES[trading_pair]["last_sequence"] = sequence
                                    new_bid = msg[stream_name].get('bids', [])
                                    if len(new_bid) > 1:
                                        if new_bid[1] != '':
                                            self.STATES[trading_pair]["bids"].update(dict([new_bid]))
                                        else:
                                            self.STATES[trading_pair]["bids"].pop(new_bid[0], None)
                                    new_ask = msg[stream_name].get('asks', [])
                                    if len(new_ask) > 1:
                                        if new_ask[1] != '':
                                            self.STATES[trading_pair]["asks"].update(dict([new_ask]))
                                        else:
                                            self.STATES[trading_pair]["asks"].pop(new_ask[0], None)
                                else:
                                    self.logger().warning(f"unexpected stream {stream_name}. msg={msg}")
                                    continue

                                data = {
                                    "bids": list(self.STATES[trading_pair].get("bids", []).items()),
                                    "asks": list(self.STATES[trading_pair].get("asks", []).items()),
                                    "update_id": self.STATES[trading_pair].get("last_sequence", 0),
                                    "timestamp": datetime.datetime.utcnow().timestamp(),
                                }
                                self.logger().info(f"{trading_pair} ob: {data}")
                                order_book_message: OrderBookMessage = PeatioOrderBook.diff_message_from_exchange(data, metadata={"trading_pair": trading_pair})
                                output.put_nowait(order_book_message)
                        else:
                            self.logger().debug(f"Unrecognized message [listen_for_order_book_diffs] received from Peatio websocket: {msg}")
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
