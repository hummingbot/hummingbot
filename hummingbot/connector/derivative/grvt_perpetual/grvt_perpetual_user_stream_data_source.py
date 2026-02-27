import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative


class GrvtPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_trade_url(self._domain),
            ping_timeout=30,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """Subscribe to user-specific streams: orders, fills, positions."""
        sub_account_id = self._auth._sub_account_id
        cookie = self._auth._session_cookie or ""

        # Authenticate the WS session
        await ws.send(WSJSONRequest(payload={
            "op": "subscribe",
            "channel": "auth",
            "cookie": cookie,
        }))

        # Subscribe to order updates
        await ws.send(WSJSONRequest(payload={
            "op": "subscribe",
            "channel": CONSTANTS.WS_ORDER,
            "sub_account_id": sub_account_id,
        }))

        # Subscribe to fill updates
        await ws.send(WSJSONRequest(payload={
            "op": "subscribe",
            "channel": CONSTANTS.WS_FILL,
            "sub_account_id": sub_account_id,
        }))

        # Subscribe to position updates
        await ws.send(WSJSONRequest(payload={
            "op": "subscribe",
            "channel": CONSTANTS.WS_POSITION,
            "sub_account_id": sub_account_id,
        }))

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                self._ws = ws
                await self._subscribe_channels(ws)
                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if isinstance(data, dict) and data.get("channel") in (
                        CONSTANTS.WS_ORDER,
                        CONSTANTS.WS_FILL,
                        CONSTANTS.WS_POSITION,
                    ):
                        output.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener. Reconnecting...")
                await asyncio.sleep(5)
            finally:
                self._ws = None
