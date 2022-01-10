import gzip
import json

from typing import Any, Dict

from hummingbot.core.web_assistant.connections.data_types import WSResponse
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase


class HuobiWSPostProcessor(WSPostProcessorBase):
    """
    Performs the necessary response processing from both public and private websocket streams.
    """

    async def post_process(self, response: WSResponse) -> WSResponse:
        if not isinstance(response.data, bytes):
            # Unlike Market WebSocket, the return data of Account and Order Websocket are not compressed by GZIP.
            return response
        encoded_msg: bytes = gzip.decompress(response.data)
        msg: Dict[str, Any] = json.loads(encoded_msg.decode("utf-8"))

        return WSResponse(data=msg)
