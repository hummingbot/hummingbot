from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.connector.exchange.zigzag import (
    zigzag_constants as CONSTANTS,
)


class ZigZagStream:
    async def ws_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        ws: WSAssistant = await self._get_ws_assistant()

        await ws.connect(
            ws_url=CONSTANTS.WSS_URL,
            ping_timeout=CONSTANTS.WS_PING_TIMEOUT)

        payload = {
            "op": "login",
            "args": self._auth.websocket_login_parameters()
        }

        login_request: WSJSONRequest = WSJSONRequest(payload=payload)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIBE):
            await ws.send(login_request)

        response: WSResponse = await ws.receive()
        message = response.data
        if "errorCode" in message or "error_code" in message or message.get("event") != "login":
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError(f"Private websocket connection authentication failed ({message})")

        return ws
