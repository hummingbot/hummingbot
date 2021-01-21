#!/usr/bin/env python
import asyncio
import logging
import ujson
import websockets

from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    List
)

import hummingbot.connector.exchange.k2.k2_constants as constants

from hummingbot.connector.exchange.k2.k2_auth import K2Auth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class K2APIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: K2Auth, trading_pairs: Optional[List[str]] = []):
        self._websocket_client: websockets.WebSocketClientProtocol = None
        self._k2_auth: K2Auth = auth
        self._trading_pairs = trading_pairs

        self._listen_for_user_stream_tasks = None

        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _init_websocket_connection(self):
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._websocket_client is None:
                self._websocket_client = await websockets.connect(constants.WSS_URL)
        except Exception:
            self.logger().network("Unexpected error occured with K2 WebSocket Connection")
        finally:
            if self._websocket_client is not None:
                self._websocket_client.close()
                self._websocket_client = None

    async def _authenticate(self):
        """
        Authenticates user to Websocket.
        """
        auth_dict: Dict[str, Any] = self._k2_auth.generate_auth_dict(path_url=constants.WSS_LOGIN)

        params: Dict[str, Any] = {
            "name": constants.WSS_LOGIN,
            "data": {
                "apikey": auth_dict["APIKey"],
                "apisignature": auth_dict["APISignature"],
                "apiauthpayload": auth_dict["APIAuthPayload"]
            },
            "apinonce": auth_dict["APINonce"]
        }
        try:
            await self._websocket_client.send(ujson.dumps(params))
            resp = await self._websocket_client.recv()

            msg: Dict[str, Any] = ujson.loads(resp)
            if msg["success"] is not True:
                raise websockets.WebSocketProtocolError("Websocket Authentication unsuccessful.")
            else:
                return

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected Error occur authenticating for to websocket channel. ", exc_info=True)
            await asyncio.sleep(5.0)
        finally:
            if self._websocket_client is not None:
                await self._websocket_client.close()
                self._websocket_client = None

    async def _subscribe_to_channels(self,):
        """
        Subscribe to SubscribeMyOrders, SubscribeMyTrades and SubscribeMyBalanceChanges channels
        """
        for channel in ["SubscribeMyOrders", "SubscribeMyTrades", "SubscribeMyBalanceChanges"]:
            params: Dict[str, Any] = {
                "name": channel,
                "data": ""
            }
            await self._websocket_client.send(ujson.dumps(params))

    async def listen_for_user_stream(self, ev_loop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        Subscribe to user stream via websocket, and keep the connection open for incoming messages
        """
        while True:
            try:
                await self._init_websocket_connection()
                self.logger().info("Authenticating")
                await self._authenticate()
                await self._subscribe_to_channels()
                async for msg in self._websocket_client.recv():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occured with K2 WebSocket Connection. Retrying in 30 seconds.",
                    exc_info=True,
                    app_warning_msg="""
                    Unexpected error occured with K2 WebSocket Connection. Retrying in 30 seconds.
                    """
                )
                if self._websocket_client is not None:
                    self._websocket_client.close()
                    self._websocket_client = None
                await asyncio.sleep(30.0)
