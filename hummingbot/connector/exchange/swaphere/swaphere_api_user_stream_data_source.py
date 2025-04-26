import asyncio
import logging
from typing import List, Optional

from hummingbot.connector.exchange.swaphere import swaphere_constants as CONSTANTS
from hummingbot.connector.exchange.swaphere.swaphere_auth import SwaphereAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class SwaphereAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    
    def __init__(
        self,
        auth: SwaphereAuth,
        trading_pairs: List[str] = None,
        web_assistants_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs or []
        self._web_assistants_factory = web_assistants_factory or WebAssistantsFactory(auth=self._auth)
        self._ws_assistant: Optional[WSAssistant] = None
        self._current_listening_key = None
        
    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger
        
    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates a websocket assistant and connects it to the exchange
        :return: a websocket assistant
        """
        if self._ws_assistant is None:
            self._ws_assistant = await self._web_assistants_factory.get_ws_assistant()
            await self._ws_assistant.connect(
                ws_url=CONSTANTS.SWAPHERE_WS_URI_PRIVATE,
                ping_timeout=30,
            )
        return self._ws_assistant
        
    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Subscribe to user account events and listen for updates
        :param output: a queue to put user stream messages into
        """
        ws = None
        try:
            ws = await self._connected_websocket_assistant()
            
            # Subscribe to account and orders channels
            account_subscription = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": CONSTANTS.SWAPHERE_WS_ACCOUNT_CHANNEL,
                    },
                ],
            }
            
            orders_subscription = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": CONSTANTS.SWAPHERE_WS_ORDERS_CHANNEL,
                        "instType": "SPOT",
                    },
                ],
            }
            
            account_request = WSJSONRequest(payload=account_subscription)
            orders_request = WSJSONRequest(payload=orders_subscription)
            
            await ws.send(account_request)
            await ws.send(orders_request)
            
            self.logger().info("Subscribed to private account and orders channels")
            
            # Listen for messages
            async for ws_response in ws.iter_messages():
                data = ws_response.data
                if "event" in data:
                    # Handle subscription responses
                    if data["event"] == "subscribe" and data.get("success") is True:
                        channel = data.get("channel")
                        self.logger().info(f"Successfully subscribed to {channel} channel")
                    continue
                    
                if "arg" in data and "data" in data:
                    # Process the user account or order update
                    data_channel = data.get("arg", {}).get("channel")
                    
                    if data_channel == CONSTANTS.SWAPHERE_WS_ACCOUNT_CHANNEL:
                        # Handle account balance updates
                        output.put_nowait({"account": data.get("data")})
                    elif data_channel == CONSTANTS.SWAPHERE_WS_ORDERS_CHANNEL:
                        # Handle order updates
                        output.put_nowait({"order": data.get("data")})
                        
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            await asyncio.sleep(5)
        finally:
            # Close the websocket if needed
            if ws is not None:
                await ws.disconnect()
                self._ws_assistant = None 