import gzip
import json

from typing import Any, Dict

from hummingbot.core.web_assistant.connections.data_types import WSResponse
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase


class ScallopWSPostProcessor(WSPostProcessorBase):
    """
    Performs the necessary response processing from both public and private websocket streams.
    """

    async def post_process(self, response: WSResponse) -> WSResponse:
        # The returned data will be binary compressed except the heartbeat data.
        if not isinstance(response.data, bytes):
            return response
        encoded_msg: bytes = gzip.decompress(response.data)
        msg: Dict[str, Any] = json.loads(encoded_msg.decode("utf-8"))

        return WSResponse(data=msg)
