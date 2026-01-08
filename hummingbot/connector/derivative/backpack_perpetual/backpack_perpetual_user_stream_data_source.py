import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BackpackPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        trading_pairs: List[str],
        connector: "BackpackPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.orders_wss_url(self._domain))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        timestamp = int(time.time() * 1000)
        window = CONSTANTS.DEFAULT_WINDOW

        auth_payload = {
            "method": "AUTHENTICATE",
            "params": {
                "apiKey": self._auth.api_key,
                "timestamp": timestamp,
                "window": window,
            }
        }

        if hasattr(self._auth, '_generate_signature'):
            signature = self._auth._generate_signature("subscribe", {}, timestamp, window)
            auth_payload["params"]["signature"] = signature

        auth_request = WSJSONRequest(payload=auth_payload)
        await websocket_assistant.send(auth_request)

        await asyncio.sleep(0.5)

        subscribe_orders = WSJSONRequest(
            payload={
                "method": "SUBSCRIBE",
                "params": ["orders"],
            }
        )
        await websocket_assistant.send(subscribe_orders)

        subscribe_positions = WSJSONRequest(
            payload={
                "method": "SUBSCRIBE",
                "params": ["positions"],
            }
        )
        await websocket_assistant.send(subscribe_positions)

        subscribe_balances = WSJSONRequest(
            payload={
                "method": "SUBSCRIBE",
                "params": ["balances"],
            }
        )
        await websocket_assistant.send(subscribe_balances)

    async def _process_websocket_messages(
        self,
        websocket_assistant: WSAssistant,
        queue: asyncio.Queue,
    ):
        async for ws_response in websocket_assistant.iter_messages():
            self._last_recv_time = time.time()
            data = ws_response.data

            stream = data.get("stream", "")
            if stream in ["orders", "positions", "balances"] or data.get("e") in ["ORDER_UPDATE", "POSITION_UPDATE", "BALANCE_UPDATE"]:
                queue.put_nowait(data)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        if websocket_assistant:
            await websocket_assistant.disconnect()

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream error: {e}")
                await asyncio.sleep(5.0)
            finally:
                await self._on_user_stream_interruption(ws)
