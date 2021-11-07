#!/usr/bin/env python
import asyncio
import hashlib
import json
from urllib.parse import urlencode

import aiohttp
import aiohttp.client_ws

import logging

from typing import (
    Optional,
    AsyncIterable,
    List,
    Dict,
    Any
)

from hummingbot.connector.exchange.mexc.constants import MEXC_WS_URL_PUBLIC
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth

import time

from websockets.exceptions import ConnectionClosed


class MexcAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _mexcausds_logger: Optional[HummingbotLogger] = None
    MESSAGE_TIMEOUT = 300.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._mexcausds_logger is None:
            cls._mexcausds_logger = logging.getLogger(__name__)

        return cls._mexcausds_logger

    def __init__(self, mexc_auth: MexcAuth, trading_pairs: Optional[List[str]] = []):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_stram_task = None
        self._last_recv_time: float = 0
        self._auth: MexcAuth = mexc_auth
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _authenticate_client(self):
        pass

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                session = aiohttp.ClientSession()
                async with session.ws_connect(MEXC_WS_URL_PUBLIC) as ws:
                    ws: aiohttp.client_ws.ClientWebSocketResponse = ws

                    params: Dict[str, Any] = {
                        'api_key': self._auth.api_key,
                        "op": "sub.personal",
                        'req_time': int(time.time() * 1000),
                        "api_secret": self._auth.secret_key,
                    }
                    params_sign = urlencode(params)
                    sign_data = hashlib.md5(params_sign.encode()).hexdigest()
                    del params['api_secret']
                    params["sign"] = sign_data

                    await ws.send_str(json.dumps(params))

                    async for raw_msg in self._inner_messages(ws):
                        self._last_recv_time = time.time()
                        decoded_msg: dict = raw_msg
                        if 'channel' in decoded_msg.keys() and decoded_msg['channel'] == 'push.personal.order':
                            output.put_nowait(decoded_msg)
                        elif 'channel' in decoded_msg.keys() and decoded_msg['channel'] == 'sub.personal':
                            pass
                        else:
                            self.logger().debug(f"other message received from MEXC websocket: {decoded_msg}")

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error("Unexpected error with WebSocket connection ,Retrying after 30 seconds..." + str(ex),
                                    exc_info=True)
                await asyncio.sleep(30.0)
            finally:
                await session.close()

    async def _inner_messages(self,
                              ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await asyncio.wait_for(ws.receive_json(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
        except asyncio.TimeoutError:
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
