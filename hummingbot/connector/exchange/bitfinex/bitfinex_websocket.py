#!/usr/bin/env python
import asyncio
import logging
import websockets
import ujson
import uuid

from typing import Optional, AsyncIterable, Any
from websockets.exceptions import ConnectionClosed
from async_timeout import timeout
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bitfinex import BITFINEX_WS_URI
from hummingbot.connector.exchange.bitfinex.bitfinex_auth import BitfinexAuth


# reusable websocket class
class BitfinexWebsocket():
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[BitfinexAuth]):
        self._client = None
        self._auth = auth
        self._consumers = dict()
        self._listening = False

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(BITFINEX_WS_URI)
            return self
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'")

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        await self._client.wait_closed()

    # listen for new websocket messages and add them to queue
    async def _listen_to_ws(self) -> AsyncIterable[Any]:
        if self._listening:
            raise AssertionError("cannot listen twice")

        self._listening = True

        try:
            while True:
                try:
                    msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    msg = ujson.loads(msg_str)
                    # print("received", msg)

                    for queue in self._consumers.values():
                        await queue.put(msg)

                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await self._client.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().error("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            self._listening = False
            await self.disconnect()

    # listen to consumer's queue updates
    async def _listen_to_queue(self, consumer_id: str) -> AsyncIterable[Any]:
        try:
            msg = self._consumers[consumer_id].get_nowait()
            yield msg
        except asyncio.QueueEmpty:
            yield None
        except Exception as e:
            self.logger().error(f"_listen_to_queue error {str(e)}", exc_info=True)
            raise e

    async def _listen(self, consumer_id: str) -> AsyncIterable[Any]:
        try:
            while True:
                if self._listening:
                    async for msg in self._listen_to_queue(consumer_id):
                        if msg is not None:
                            yield msg

                    await asyncio.sleep(0.5)
                else:
                    async for msg in self._listen_to_ws():
                        yield msg
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise e

    async def messages(self, waitFor: Optional[Any] = None) -> AsyncIterable[Any]:
        consumer_id = uuid.uuid4()
        self._consumers[consumer_id] = asyncio.Queue()

        try:
            async for msg in self._listen(consumer_id):
                if waitFor is None:
                    yield msg
                else:
                    async with timeout(self.PING_TIMEOUT):
                        try:
                            if (waitFor(msg) is True):
                                yield msg
                        except IOError as e:
                            raise e
                        except Exception:
                            pass
        except Exception as e:
            self.logger().error(f"_listen error {str(e)}", exc_info=True)
            raise e
        finally:
            self._consumers.pop(consumer_id, None)

    # emit messages
    async def emit(self, data):
        if (self._listening is False):
            await self.connect()

        # print("send", data)
        await self._client.send(ujson.dumps(data))

    # authenticate: authenticate session
    async def authenticate(self):
        if self._auth is None:
            raise "auth not provided"

        payload = self._auth.generate_auth_payload('AUTH{nonce}'.format(nonce=self._auth.get_nonce()))

        def waitFor(msg):
            isAuthEvent = msg.get("event", None) == "auth"
            isStatusOk = msg.get("status", None) == "OK"
            return isAuthEvent and isStatusOk

        await self.emit(payload)

        async for msg in self.messages(waitFor):
            return msg
