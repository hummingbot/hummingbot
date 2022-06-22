#!/usr/bin/env python

import asyncio
import logging
from typing import List, Optional

from aiohttp import ClientConnectionError

from hummingbot.connector.exchange.digifinex import digifinex_utils
from hummingbot.connector.exchange.digifinex.digifinex_global import DigifinexGlobal

# from .digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_websocket import DigifinexWebsocket
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class DigifinexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, _global: DigifinexGlobal, trading_pairs: Optional[List[str]] = []):
        self._global: DigifinexGlobal = _global
        self._trading_pairs = trading_pairs
        self._listen_for_user_stream_task = None
        self._ws: Optional[DigifinexWebsocket] = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        if self._ws:
            return self._ws.last_recv_time
        return -1

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages

        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                self._ws = DigifinexWebsocket(self._global.auth)
                await self._ws.connect()

                trading_pairs: List[str] = [digifinex_utils.convert_to_ws_trading_pair(pair)
                                            for pair in self._trading_pairs]
                currencies = set()
                for trade_pair in self._trading_pairs:
                    trade_pair_currencies = trade_pair.split('-')
                    currencies.update(trade_pair_currencies)

                await self._ws.subscribe("order", trading_pairs)
                await self._ws.subscribe("balance", list(currencies))

                async for msg in self._ws.iter_messages():
                    if msg is None or "params" not in msg or "method" not in msg:
                        continue
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except ClientConnectionError:
                self.logger().warning("Attemping re-connection with Websocket Private Channels...")
            except Exception as e:
                self.logger().error(
                    f"Unexpected error with WebSocket connection. {str(e)}",
                    exc_info=True
                )
            finally:
                self._ws and await self._ws.disconnect()
