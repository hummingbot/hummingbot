import asyncio
import contextlib
import functools
import logging
import uuid
from collections import defaultdict, deque
from typing import Any, Dict, Optional, Tuple, Union
from unittest.mock import AsyncMock, PropertyMock

import aiohttp

from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


def get_stable_key(ws: AsyncMock) -> uuid.UUID:
    """
    Recursively unwraps the websocket mock to retrieve the original stable key.
    If no _stable_key is found, falls back to using the object's id.
    """
    current = ws
    while True:
        if hasattr(current, "_stable_key"):
            return current._stable_key
        elif hasattr(current, "__wrapped__"):
            current = current.__wrapped__
        else:
            return id(current)


class MockWebsocketClientSession:
    # Created this class instead of using a generic mock to be sure that no other methods from the client session
    # are required when working with websockets
    def __init__(self, mock_websocket: AsyncMock):
        self._mock_websocket = mock_websocket
        self._connection_args: Optional[Tuple[Any]] = None
        self._connection_kwargs: Optional[Dict[str, Any]] = None

    @property
    def connection_args(self) -> Tuple[Any]:
        return self._connection_args or ()

    @property
    def connection_kwargs(self) -> Dict[str, Any]:
        return self._connection_kwargs or {}

    async def ws_connect(self, *args, **kwargs):
        self._connection_args = args
        self._connection_kwargs = kwargs
        return self._mock_websocket

    async def close(self):
        pass


class NetworkMockingAssistant:
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, deprecated_loop=None):
        super().__init__()
        self._response_text_queues: dict[uuid.UUID, asyncio.Queue] | None = None
        self._response_json_queues: dict[uuid.UUID, asyncio.Queue] | None = None
        self._response_status_queues: dict[uuid.UUID, deque] | None = None
        self._sent_http_requests: dict[uuid.UUID, asyncio.Queue] | None = None

        self._incoming_websocket_json_queues: dict[uuid.UUID, asyncio.Queue] | None = None
        self._all_incoming_websocket_json_delivered_event: dict[uuid.UUID, asyncio.Event] | None = None
        self._incoming_websocket_text_queues: dict[uuid.UUID, asyncio.Queue] | None = None
        self._all_incoming_websocket_text_delivered_event: dict[uuid.UUID, asyncio.Event] | None = None
        self._incoming_websocket_aiohttp_queues: dict[uuid.UUID, asyncio.Queue] | None = None
        self._all_incoming_websocket_aiohttp_delivered_event: dict[uuid.UUID, asyncio.Event] | None = None
        self._sent_websocket_json_messages: dict[uuid.UUID, list] | None = None
        self._sent_websocket_text_messages: dict[uuid.UUID, list] | None = None

        try:
            self._loop_id = id(asyncio.get_running_loop())
            asyncio.create_task(self.async_init())
        except RuntimeError:
            self._loop_id = None

    async def async_init(self):
        self._response_text_queues: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._response_json_queues: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._response_status_queues: dict[uuid.UUID, deque] = defaultdict(deque)
        self._sent_http_requests: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)

        self._incoming_websocket_json_queues: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._all_incoming_websocket_json_delivered_event: dict[uuid.UUID, asyncio.Event] = defaultdict(asyncio.Event)
        self._incoming_websocket_text_queues: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._all_incoming_websocket_text_delivered_event: dict[uuid.UUID, asyncio.Event] = defaultdict(asyncio.Event)
        self._incoming_websocket_aiohttp_queues: dict[uuid.UUID, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._all_incoming_websocket_aiohttp_delivered_event = defaultdict(asyncio.Event)
        self._sent_websocket_json_messages: dict[uuid.UUID, list] = defaultdict(list)
        self._sent_websocket_text_messages: dict[uuid.UUID, list] = defaultdict(list)

    def verify_async_init(self):
        if any(
                attr is None
                for attr in [
                    self._response_text_queues,
                    self._response_json_queues,
                    self._response_status_queues,
                    self._sent_http_requests,
                    self._incoming_websocket_json_queues,
                    self._all_incoming_websocket_json_delivered_event,
                    self._incoming_websocket_text_queues,
                    self._all_incoming_websocket_text_delivered_event,
                    self._incoming_websocket_aiohttp_queues,
                    self._all_incoming_websocket_aiohttp_delivered_event,
                    self._sent_websocket_json_messages,
                    self._sent_websocket_text_messages
                ]
        ):
            raise Exception("NetworkMockingAssistant must be initialized in async context. Please call async_init() first.")

        with contextlib.suppress(RuntimeError):
            if self._loop_id != id(asyncio.get_running_loop()):
                raise Exception("NetworkMockingAssistant was initialized on a different event loop.")

    @staticmethod
    def async_partial(function, *args, **kwargs):
        """
        Returns an async function that always calls `function` with the bound arguments,
        completely ignoring any extra parameters passed at call time.
        """

        async def partial_func(*_args, **_kwargs):
            return await function(*args, **kwargs)

        return partial_func

    def _get_next_api_response_status(self, http_mock):
        self.verify_async_init()
        return self._response_status_queues[http_mock].popleft()

    async def _get_next_api_response_json(self, http_mock):
        self.verify_async_init()
        return await self._response_json_queues[http_mock].get()

    async def _get_next_api_response_text(self, http_mock):
        self.verify_async_init()
        return await self._response_text_queues[http_mock].get()

    def _handle_http_request(self, http_mock, url, headers=None, params=None, data=None, *args, **kwargs):
        self.verify_async_init()
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=functools.partial(
            self._get_next_api_response_status, http_mock))
        response.json.side_effect = self.async_partial(self._get_next_api_response_json, http_mock)
        response.text.side_effect = self.async_partial(self._get_next_api_response_text, http_mock)
        response.__aenter__.return_value = response

        components = params if params else data
        self._sent_http_requests[http_mock].put_nowait((url, headers, components))

        return response

    def configure_web_assistants_factory(self, web_assistants_factory: WebAssistantsFactory) -> AsyncMock:
        websocket_mock: AsyncMock = self.create_websocket_mock()
        client_session_mock: MockWebsocketClientSession = MockWebsocketClientSession(mock_websocket=websocket_mock)

        web_assistants_factory._connections_factory._ws_independent_session = client_session_mock

        return websocket_mock

    def configure_http_request_mock(self, http_request_mock):
        http_request_mock.side_effect = functools.partial(self._handle_http_request, http_request_mock)

    def add_http_response(self, http_request_mock, response_status, response_json=None, response_text=None):
        self.verify_async_init()
        self._response_status_queues[http_request_mock].append(response_status)
        if response_json is not None:
            self._response_json_queues[http_request_mock].put_nowait(response_json)
        if response_text is not None:
            self._response_text_queues[http_request_mock].put_nowait(response_text)

    async def next_sent_request_data(self, http_request_mock):
        self.verify_async_init()
        return await self._sent_http_requests[http_request_mock].get()

    async def _get_next_websocket_json_message(self, ws_key: uuid.UUID, *args, **kwargs):
        self.verify_async_init()
        queue = self._incoming_websocket_json_queues[ws_key]
        message = await queue.get()
        if queue.empty():
            self._all_incoming_websocket_json_delivered_event[ws_key].set()
        return message

    async def _get_next_websocket_aiohttp_message(self, ws_key: uuid.UUID, *args, **kwargs):
        self.verify_async_init()
        queue = self._incoming_websocket_aiohttp_queues[ws_key]
        message = await queue.get()
        if queue.empty():
            self._all_incoming_websocket_aiohttp_delivered_event[ws_key].set()
        if isinstance(message, (BaseException, Exception)):
            raise message
        return message

    async def _get_next_websocket_text_message(self, ws_key: uuid.UUID, *args, **kwargs):
        self.verify_async_init()
        queue = self._incoming_websocket_text_queues[ws_key]
        message = await queue.get()
        if queue.empty():
            self._all_incoming_websocket_text_delivered_event[ws_key].set()
        return message

    def create_websocket_mock(self):
        self.verify_async_init()
        ws = AsyncMock()
        # Create a stable key
        stable_key: uuid.UUID = uuid.uuid4()
        ws._stable_key = stable_key
        # Ensure __aenter__ returns the same ws instance (with stable key intact)
        ws.__aenter__.side_effect = lambda: ws
        ws.__aexit__.return_value = None

        # Set side effects using async_partial with ignore_first_arg if needed.
        ws.send_json.side_effect = lambda sent_message: self._sent_websocket_json_messages[stable_key].append(
            sent_message)
        ws.send.side_effect = lambda sent_message: self._sent_websocket_text_messages[stable_key].append(sent_message)
        ws.send_str.side_effect = lambda sent_message: self._sent_websocket_text_messages[stable_key].append(
            sent_message)
        ws.receive_json.side_effect = self.async_partial(self._get_next_websocket_json_message, stable_key)
        ws.receive_str.side_effect = self.async_partial(self._get_next_websocket_text_message, stable_key)
        ws.receive.side_effect = self.async_partial(self._get_next_websocket_aiohttp_message, stable_key)
        ws.recv.side_effect = self.async_partial(self._get_next_websocket_text_message, stable_key)
        return ws

    def add_websocket_json_message(self, websocket_mock, message):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        self._incoming_websocket_json_queues[key].put_nowait(message)
        self._all_incoming_websocket_json_delivered_event[key].clear()

    def add_websocket_text_message(self, websocket_mock, message):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        self._incoming_websocket_text_queues[key].put_nowait(message)
        self._all_incoming_websocket_text_delivered_event[key].clear()

    def add_websocket_aiohttp_message(
            self,
            websocket_mock: AsyncMock,
            message: str,
            message_type: aiohttp.WSMsgType = aiohttp.WSMsgType.TEXT
    ):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        msg = aiohttp.WSMessage(message_type, message, extra=None)
        self._incoming_websocket_aiohttp_queues[key].put_nowait(msg)
        self._all_incoming_websocket_aiohttp_delivered_event[key].clear()

    def add_websocket_aiohttp_exception(self, websocket_mock, exception: Union[Exception, BaseException]):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        self._incoming_websocket_aiohttp_queues[key].put_nowait(exception)
        self._all_incoming_websocket_aiohttp_delivered_event[key].clear()

    def json_messages_sent_through_websocket(self, websocket_mock):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        return self._sent_websocket_json_messages[key]

    def text_messages_sent_through_websocket(self, websocket_mock):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        return self._sent_websocket_text_messages[key]

    async def run_until_all_text_messages_delivered(self, websocket_mock, timeout: int = 1):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        all_delivered = self._all_incoming_websocket_text_delivered_event[key]
        await asyncio.wait_for(all_delivered.wait(), timeout)

    async def run_until_all_json_messages_delivered(self, websocket_mock, timeout: int = 1):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        all_delivered = self._all_incoming_websocket_json_delivered_event[key]
        await asyncio.wait_for(all_delivered.wait(), timeout)

    async def run_until_all_aiohttp_messages_delivered(self, websocket_mock, timeout: int = 1):
        self.verify_async_init()
        key: uuid.UUID = get_stable_key(websocket_mock)
        all_delivered = self._all_incoming_websocket_aiohttp_delivered_event[key]
        await asyncio.wait_for(all_delivered.wait(), timeout)
