import asyncio
from typing import Callable, Optional

from google.protobuf import json_format
from grpc import RpcError

from pyinjective.core.network import CookieAssistant


class GrpcApiStreamAssistant:
    def __init__(self, cookie_assistant: CookieAssistant):
        super().__init__()
        self._cookie_assistant = cookie_assistant

    async def listen_stream(
        self,
        call: Callable,
        request,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        metadata = self._cookie_assistant.metadata()
        stream = call(request, metadata=metadata)

        try:
            async for event in stream:
                parsed_event = json_format.MessageToDict(
                    message=event,
                    always_print_fields_with_no_presence=True,
                )
                if asyncio.iscoroutinefunction(callback):
                    await callback(parsed_event)
                else:
                    callback(parsed_event)
        except RpcError as ex:
            if on_status_callback is not None:
                if asyncio.iscoroutinefunction(on_status_callback):
                    await on_status_callback(ex)
                else:
                    on_status_callback(ex)

        if on_end_callback is not None:
            if asyncio.iscoroutinefunction(on_end_callback):
                await on_end_callback()
            else:
                on_end_callback()
