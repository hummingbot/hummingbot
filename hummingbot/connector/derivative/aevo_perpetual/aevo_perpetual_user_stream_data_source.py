import asyncio
from typing import List, Optional
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS

class AevoPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(self,
                 auth,
                 trading_pairs: List[str],
                 api_factory: Optional[WebAssistantsFactory] = None,
                 domain: str = "aevo"):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._api_factory = api_factory
        self._domain = domain

    async def _listen_to_user_messages(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                # Use api_factory to get authenticated WS connection if supported, or manual auth
                ws = await self._api_factory.get_ws_connection(CONSTANTS.AEVO_WS_URL)
                await ws.connect()
                
                # Authenticate
                auth_payload = self._auth.get_ws_auth_payload()
                await ws.send_json(auth_payload)
                
                # Subscribe to private channels
                channels = [
                    "orders",
                    "fills",
                    "positions",
                    "account"
                ]
                subscribe_request = {
                    "op": "subscribe",
                    "data": channels
                }
                await ws.send_json(subscribe_request)
                
                async for msg in ws.iter_messages():
                    if msg.data:
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User Stream WS Error: {e}", exc_info=True)
                await asyncio.sleep(5)
            finally:
                if ws:
                    await ws.disconnect()
