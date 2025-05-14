import asyncio
from enum import Enum
from typing import Any, Dict, Optional

import ujson

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


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
        websocket: WSAssistant,
        previous_messages_number: int = 0,
    ):
        self._websocket = websocket
        self._messages_counter = previous_messages_number
        self._lock = asyncio.Lock()

    @classmethod
    def endpoint_from_raw_message(cls, raw_message: str) -> str:
        message = ujson.loads(raw_message)
        return cls.endpoint_from_message(message=message)

    @classmethod
    def endpoint_from_message(cls, message: Dict[str, Any]) -> str:
        return message.get(cls._endpoint_field_name)

    @classmethod
    def payload_from_raw_message(cls, raw_message: str) -> Dict[str, Any]:
        return cls.payload_from_message(message=raw_message)

    @classmethod
    def payload_from_message(cls, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = ujson.loads(message.get(cls._payload_field_name))
        return payload

    @property
    def websocket(self) -> WSAssistant:
        return self._websocket

    async def next_message_number(self):
        async with self._lock:
            self._messages_counter += 1
            next_number = self._messages_counter
        return next_number

    async def send_request(self, endpoint_name: str, payload: Dict[str, Any], limit_id: Optional[str] = None):
        message_number = await self.next_message_number()
        message = {
            self._message_type_field_name: NdaxMessageType.REQUEST_TYPE.value,
            self._message_number_field_name: message_number,
            self._endpoint_field_name: endpoint_name,
            self._payload_field_name: ujson.dumps(payload),
        }

        message_request: WSJSONRequest = WSJSONRequest(payload=message)

        await self._websocket.send(message_request)

    async def process_websocket_messages(self, queue: asyncio.Queue):
        async for ws_response in self._websocket.iter_messages():
            data = ws_response.data
            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            queue.put_nowait(event_message)

    async def close(self):
        if self._websocket is not None:
            await self._websocket.disconnect()

    async def disconnect(self):
        if self._websocket is not None:
            await self._websocket.disconnect()
