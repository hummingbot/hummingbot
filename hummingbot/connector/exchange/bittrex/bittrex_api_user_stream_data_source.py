import asyncio

from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class BittrexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(self, auth: BittrexAuth,
                 connector,
                 api_factory):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.BITTREX_WS_URL, ping_timeout=CONSTANTS.PING_TIMEOUT)
        return ws

    async def _authenticate_client(self, ws: WSAssistant):
        try:
            ws_request: WSJSONRequest = WSJSONRequest(
                {
                    "H": "c3",
                    "M": "Authenticate",
                    "A": [],
                    "I": 1
                }
            )
            auth_ws_request = await self._auth.ws_authenticate(ws_request)
            await ws.send(auth_ws_request)
            resp: WSResponse = await ws.receive()
            auth_response = resp.data["R"]
            if not auth_response["Success"]:
                raise ValueError(f"User Stream Authentication Fail! {auth_response['ErrorCode']}")
            self.logger().info("Successfully authenticated to user stream...")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error occurred authenticating websocket connection... Error: {str(e)}", exc_info=True)
            raise

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            await self._authenticate_client(websocket_assistant)
            payload = {
                "H": "c3",
                "M": "Subscribe",
                "A": [["balance", "order", "heartbeat", "execution"]],
                "I": 1
            }
            subscribe_private_channels__request: WSJSONRequest = WSJSONRequest(payload=payload)
            await websocket_assistant.send(subscribe_private_channels__request)
            resp: WSResponse = await websocket_assistant.receive()
            sub_response = resp.data["R"]
            resp_list = [resp["Success"] for resp in sub_response]
            if not all(resp_list):
                raise ValueError("Error subscribing to private channels")
            self.logger().info("Successfully subscribed to private channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Cannot subscribe to private channel")
            raise
