import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class EvedexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Subscribes to user-specific Centrifuge WebSocket channels on EVEDEX:
    - order-{user_id} — order state updates
    - position-{user_id} — position updates
    - orderFills-{user_id} — trade fill events
    - funding-{user_id} — funding balance updates
    - user-{user_id} — general account updates
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: EvedexPerpetualAuth,
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
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                await self._run_user_stream(output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _get_centrifuge_token(self) -> str:
        """Get a Centrifuge connection token from EVEDEX auth."""
        import aiohttp
        auth_url = web_utils.get_auth_base_url(self._domain)
        headers = self._auth.get_auth_headers()
        headers["Content-Type"] = "application/json"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{web_utils.get_trade_base_url(self._domain)}/api/dx-feed/auth",
                headers={**self._auth.get_auth_headers(), "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token", "")
        return ""

    async def _run_user_stream(self, output: asyncio.Queue):
        ws_url = web_utils.get_ws_url(self._domain)
        prefix = web_utils.get_ws_prefix(self._domain)
        user_id = self._auth.user_exchange_id

        if not user_id:
            self.logger().warning("User exchange ID not set — cannot subscribe to user streams")
            await asyncio.sleep(10)
            return

        import websockets
        async with websockets.connect(ws_url) as ws:
            # Connect with auth token
            centrifuge_token = await self._get_centrifuge_token()
            connect_msg = {"id": 1, "connect": {"token": centrifuge_token, "data": {}}}
            await ws.send(json.dumps(connect_msg))
            await asyncio.wait_for(ws.recv(), timeout=10)

            # Subscribe to user channels
            user_channels = [
                f"{prefix}:order-{user_id}",
                f"{prefix}:position-{user_id}",
                f"{prefix}:orderFills-{user_id}",
                f"{prefix}:funding-{user_id}",
                f"{prefix}:user-{user_id}",
            ]

            for i, channel in enumerate(user_channels, start=2):
                await ws.send(json.dumps({
                    "id": i,
                    "subscribe": {"channel": channel},
                }))

            # Heartbeat task
            async def heartbeat():
                while True:
                    await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                    await ws.send(json.dumps({"id": 99, "ping": {}}))

            heartbeat_task = asyncio.create_task(heartbeat())
            try:
                async for raw_msg in ws:
                    self._last_recv_time = time.time()
                    try:
                        msg = json.loads(raw_msg)
                        await output.put(msg)
                    except Exception:
                        pass
            finally:
                heartbeat_task.cancel()
