import asyncio
from enum import Enum
from typing import Dict, Any

import ujson
import websockets


class NdaxMessageType(Enum):
    REQUEST_TYPE = 0
    REPLY_TYPE = 1
    SUBSCRIBE_TO_EVENT_TYPE = 2
    EVENT = 3
    UNSUBSCRIBE_FROM_EVENT = 4
    ERROR = 5


class NdaxWebSocketAdaptor:
    """
    Auxiliary class that works as a wrapper of a low level web socket. It contains the logic to create messages
    with the format expected by NDAX
    :param websocket: The low level socket to be used to send and receive messages
    :param previous_messages_number: number of messages already sent to NDAX. This parameter is useful when the
    connection is reestablished after a communication error, and allows to keep a unique identifier for each message.
    The default previous_messages_number is 0
    """
    def __init__(self, websocket: websockets.WebSocketClientProtocol, previous_messages_number: int = 0):
        self._websocket = websocket
        self._messages_counter = previous_messages_number
        self._lock = asyncio.Lock()

    async def next_message_number(self):
        async with self._lock:
            self._messages_counter += 1
            next_number = self._messages_counter
        return next_number

    async def send_request(self, endpoint_name: str, payload: Dict[str, Any]):
        message_number = await self.next_message_number()
        message = {"m": NdaxMessageType.REQUEST_TYPE.value,
                   "i": message_number,
                   "n": endpoint_name,
                   "o": ujson.dumps(payload)}

        await self._websocket.send(ujson.dumps(message))

    async def recv(self):
        return await self._websocket.recv()
