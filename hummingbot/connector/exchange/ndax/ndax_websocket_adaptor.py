import aiohttp
import asyncio
from enum import Enum
from typing import AsyncIterable, Dict, Any, Optional

import ujson

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class NdaxMessageType(Enum):
    REQUEST_TYPE = 0
    REPLY_TYPE = 1
    SUBSCRIBE_TO_EVENT_TYPE = 2
    EVENT = 3
    UNSUBSCRIBE_FROM_EVENT = 4
    ERROR = 5


class NdaxWebSocketAdaptor:

    _message_type_field_name = "m"
    _message_number_field_name = "i"
    _endpoint_field_name = "n"
    _payload_field_name = "o"

    """
    Auxiliary class that works as a wrapper of a low level web socket. It contains the logic to create messages
    with the format expected by NDAX
    :param websocket: The low level socket to be used to send and receive messages
    :param previous_messages_number: number of messages already sent to NDAX. This parameter is useful when the
    connection is reestablished after a communication error, and allows to keep a unique identifier for each message.
    The default previous_messages_number is 0
    """
    MESSAGE_TIMEOUT = 20.0
    PING_TIMEOUT = 5.0

    def __init__(
        self,
        throttler: AsyncThrottler,
        websocket: aiohttp.ClientWebSocketResponse,
        previous_messages_number: int = 0,
    ):
        self._websocket = websocket
        self._messages_counter = previous_messages_number
        self._lock = asyncio.Lock()
        self._throttler = throttler

    @classmethod
    def endpoint_from_raw_message(cls, raw_message: str) -> str:
        message = ujson.loads(raw_message)
        return cls.endpoint_from_message(message=message)

    @classmethod
    def endpoint_from_message(cls, message: Dict[str, Any]) -> str:
        return message.get(cls._endpoint_field_name)

    @classmethod
    def payload_from_raw_message(cls, raw_message: str) -> Dict[str, Any]:
        message = ujson.loads(raw_message)
        return cls.payload_from_message(message=message)

    @classmethod
    def payload_from_message(cls, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = ujson.loads(message.get(cls._payload_field_name))
        return payload

    async def next_message_number(self):
        async with self._lock:
            self._messages_counter += 1
            next_number = self._messages_counter
        return next_number

    async def send_request(self, endpoint_name: str, payload: Dict[str, Any], limit_id: Optional[str] = None):
        message_number = await self.next_message_number()
        message = {self._message_type_field_name: NdaxMessageType.REQUEST_TYPE.value,
                   self._message_number_field_name: message_number,
                   self._endpoint_field_name: endpoint_name,
                   self._payload_field_name: ujson.dumps(payload)}

        limit_id = limit_id or endpoint_name
        async with self._throttler.execute_task(limit_id):
            await self._websocket.send_json(message)

    async def receive(self):
        return await self._websocket.receive()

    async def iter_messages(self) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    raw_msg = await asyncio.wait_for(self.receive(), timeout=self.MESSAGE_TIMEOUT)
                    if raw_msg.type == aiohttp.WSMsgType.CLOSED:
                        raise ConnectionError
                    yield raw_msg.data
                except asyncio.TimeoutError:
                    await asyncio.wait_for(
                        self.send_request(CONSTANTS.WS_PING_REQUEST, payload={}, limit_id=CONSTANTS.WS_PING_ID),
                        timeout=self.PING_TIMEOUT
                    )
        except ConnectionError:
            return
        finally:
            await self.close()

    async def close(self):
        if self._websocket is not None:
            await self._websocket.close()
