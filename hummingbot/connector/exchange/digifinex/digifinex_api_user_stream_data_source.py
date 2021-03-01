#!/usr/bin/env python

import time
import asyncio
import logging
from typing import Optional, List, AsyncIterable, Any
from hummingbot.connector.exchange.digifinex.digifinex_global import DigifinexGlobal
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
# from .digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_websocket import DigifinexWebsocket
from hummingbot.connector.exchange.digifinex import digifinex_utils


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
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            ws = DigifinexWebsocket(self._global.auth)
            await ws.connect()
            await ws.subscribe("order", list(map(
                               lambda pair: f"{digifinex_utils.convert_to_ws_trading_pair(pair)}",
                               self._trading_pairs
                               )))

            currencies = set()
            for trade_pair in self._trading_pairs:
                trade_pair_currencies = trade_pair.split('-')
                currencies.update(trade_pair_currencies)
            await ws.subscribe("balance", currencies)

            balance_snapshot = await self._global.rest_api.get_balance()
            # {
            #   "code": 0,
            #   "list": [
            #     {
            #       "currency": "BTC",
            #       "free": 4723846.89208129,
            #       "total": 0
            #     }
            #   ]
            # }
            yield {'method': 'balance.update', 'params': balance_snapshot['list']}
            self._last_recv_time = time.time()

            # await ws.subscribe(["user.order", "user.trade", "user.balance"])
            async for msg in ws.on_message():
                # {
                # 	"method": "balance.update",
                # 	"params": [{
                # 		"currency": "USDT",
                # 		"free": "99944652.8478545303601106",
                # 		"total": "99944652.8478545303601106",
                # 		"used": "0.0000000000"
                # 	}],
                # 	"id": null
                # }
                yield msg
                self._last_recv_time = time.time()
                if (msg.get("result") is None):
                    continue
        except Exception as e:
            self.logger().exception(e)
            raise e
        finally:
            await ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
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
