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

from hummingbot.connector.exchange.mexc import mexc_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth

import time

from websockets.exceptions import ConnectionClosed


class MexcAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    MESSAGE_TIMEOUT = 300.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)

        return cls._logger

    def __init__(self, throttler: AsyncThrottler, mexc_auth: MexcAuth, trading_pairs: Optional[List[str]] = [],
                 shared_client: Optional[aiohttp.ClientSession] = None):
        self._shared_client = shared_client or self._get_session_instance()
        self._last_recv_time: float = 0
        self._auth: MexcAuth = mexc_auth
        self._trading_pairs = trading_pairs
        self._throttler = throttler
        super().__init__()

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _authenticate_client(self):
        pass

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            session = self._shared_client
            try:
                ws = await session.ws_connect(CONSTANTS.MEXC_WS_URL_PUBLIC)
                ws: aiohttp.client_ws.ClientWebSocketResponse = ws
                try:
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
                    async with self._throttler.execute_task(CONSTANTS.MEXC_WS_URL_PUBLIC):
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
                except Exception as ex2:
                    raise ex2
                finally:
                    await ws.close()

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error("Unexpected error with WebSocket connection ,Retrying after 30 seconds..." + str(ex),
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        try:
            while True:
                msg = await asyncio.wait_for(ws.receive(), timeout=self.MESSAGE_TIMEOUT)
                if msg.type == aiohttp.WSMsgType.CLOSED:
                    raise ConnectionError
                yield json.loads(msg.data)
        except asyncio.TimeoutError:
            return
        except ConnectionClosed:
            return
        except ConnectionError:
            return
