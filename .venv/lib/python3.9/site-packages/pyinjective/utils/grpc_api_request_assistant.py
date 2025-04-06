from typing import Any, Callable, Dict

from google.protobuf import json_format

from pyinjective.core.network import CookieAssistant


class GrpcApiRequestAssistant:
    def __init__(self, cookie_assistant: CookieAssistant):
        super().__init__()
        self._cookie_assistant = cookie_assistant

    async def execute_call(self, call: Callable, request) -> Dict[str, Any]:
        metadata = self._cookie_assistant.metadata()
        grpc_call = call(request, metadata=metadata)
        response = await grpc_call

        await self._cookie_assistant.process_response_metadata(grpc_call=grpc_call)

        result = json_format.MessageToDict(
            message=response,
            always_print_fields_with_no_presence=True,
        )

        return result
