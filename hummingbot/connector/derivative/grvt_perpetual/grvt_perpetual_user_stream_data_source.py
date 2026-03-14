import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class GrvtPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Subscribes to user-specific WebSocket streams on GRVT:
    - Order updates
    - Position updates
    - Fill updates
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: GrvtPerpetualAuth,
        trading_pairs: List[str],
        connector,
        api_factory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistant = None
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """Subscribe to user order/position/fill update streams via WebSocket."""
        while True:
            try:
                await self._run_user_stream(output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _run_user_stream(self, output: asyncio.Queue):
        ws_url = web_utils.get_trade_ws_url(self._domain)
        import websockets

        async with websockets.connect(ws_url) as ws:
            # Authenticate WebSocket session with API key
            login_msg = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": "login",
                    "selectors": [self._auth._api_key],
                },
                "id": 1,
            }
            await ws.send(json.dumps(login_msg))
            auth_response = await asyncio.wait_for(ws.recv(), timeout=10)

            # Subscribe to order updates
            for stream_name in [
                CONSTANTS.WS_ORDER_UPDATES_STREAM,
                CONSTANTS.WS_POSITION_UPDATES_STREAM,
                CONSTANTS.WS_FILL_UPDATES_STREAM,
            ]:
                sub_msg = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": {
                        "stream": stream_name,
                        "selectors": [str(self._auth.trading_account_id)],
                    },
                    "id": 2,
                }
                await ws.send(json.dumps(sub_msg))

            # Heartbeat task
            async def heartbeat():
                while True:
                    await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                    await ws.send(json.dumps({"jsonrpc": "2.0", "method": "ping", "id": 99}))

            heartbeat_task = asyncio.create_task(heartbeat())
            try:
                async for raw_msg in ws:
                    self._last_recv_time = time.time()
                    try:
                        msg = json.loads(raw_msg)
                    except Exception:
                        continue
                    await output.put(msg)
            finally:
                heartbeat_task.cancel()
