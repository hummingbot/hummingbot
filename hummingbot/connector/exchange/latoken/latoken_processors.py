from typing import Any, Dict

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class LatokenWSPostProcessor(WSPostProcessorBase):
    async def post_process(self, response: WSResponse) -> WSResponse:
        msg_in = stomper.Frame()
        data: Dict[str, Any] = msg_in.unpack(response.data.decode())
        return WSResponse(data=data)


class LatokenWSPreProcessor(WSPreProcessorBase):
    async def pre_process(self, response: WSRequest) -> WSRequest:
        if response.payload == CONSTANTS.WS_CONNECT_MSG:
            msg_out = stomper.Frame()
            msg_out.cmd = CONSTANTS.WS_CONNECT_MSG
            msg_out.headers.update({
                "accept-version": "1.1",
                "heart-beat": "0,0"
            })
            response.payload = msg_out.pack()
        return response
