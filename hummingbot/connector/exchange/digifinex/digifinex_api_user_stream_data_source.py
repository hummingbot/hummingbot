#!/usr/bin/env python

import asyncio
import logging
from typing import Any, AsyncIterable, List, Optional

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
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._ws: Optional[DigifinexWebsocket] = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        if self._ws:
            return self._ws.last_recv_time
        return -1

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            self._ws = DigifinexWebsocket(self._global.auth)
            await self._ws.connect()

            trading_pairs: List[str] = [digifinex_utils.convert_to_ws_trading_pair(pair)
                                        for pair in self._trading_pairs]
            await self._ws.subscribe("order", trading_pairs)

            currencies = list()
            for trade_pair in self._trading_pairs:
                trade_pair_currencies = trade_pair.split('-')
                currencies.extend(trade_pair_currencies)
            await self._ws.subscribe("balance", currencies)
            async for msg in self._ws.iter_messages():
                if (msg.get("result") is None):
                    continue
                yield msg

        except Exception as e:
            self.logger().exception(e)
            raise e
        finally:
            await self._ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages

        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for msg in self._listen_to_orders_trades_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Digifinex WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)
