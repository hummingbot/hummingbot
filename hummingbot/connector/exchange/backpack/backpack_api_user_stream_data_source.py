"""Backpack API user stream data source."""
import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange


class BackpackAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Backpack Exchange.
    
    Handles WebSocket connections for private user data streams including:
    - Order updates
    - Balance updates
    - Position updates (for perpetuals)
    """

    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: "BackpackAuth",
        trading_pairs: List[str],
        connector: "BackpackExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        """
        Initializes the user stream data source.
        
        :param auth: Authentication object
        :param trading_pairs: List of trading pairs to track
        :param connector: The Backpack exchange connector
        :param api_factory: Web assistants factory
        :param domain: Domain for the API
        """
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistant: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message.
        
        :return: Timestamp of last received message
        """
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0.0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates and connects a WebSocket assistant for user streams.
        
        :return: Connected WebSocket assistant
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        self._ws_assistant = await self._api_factory.get_ws_assistant()
        
        # Connect to WebSocket
        await self._ws_assistant.connect(
            ws_url=web_utils.ws_url(self._domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )
        
        # Authenticate the WebSocket connection
        await self._authenticate()
        
        # Subscribe to user data streams
        await self._subscribe_user_streams()
        
        return self._ws_assistant

    async def _authenticate(self):
        """
        Authenticates the WebSocket connection.
        """
        auth_message = self._auth.generate_websocket_auth_message()
        auth_request = WSJSONRequest(payload=auth_message)
        await self._ws_assistant.send(auth_request)
        self.logger().info("Sent WebSocket authentication message")

    async def _subscribe_user_streams(self):
        """
        Subscribes to user data streams.
        """
        try:
            from hummingbot.connector.exchange.backpack.backpack_utils import get_backpack_trading_pair
            
            # Subscribe to account updates
            account_payload = {
                "method": "subscribe",
                "params": ["account"],
            }
            await self._ws_assistant.send(WSJSONRequest(payload=account_payload))
            
            # Subscribe to order updates for each trading pair
            order_params = []
            for trading_pair in self._trading_pairs:
                symbol = get_backpack_trading_pair(trading_pair)
                order_params.append(f"orderUpdate.{symbol}")
            
            if order_params:
                order_payload = {
                    "method": "subscribe",
                    "params": order_params,
                }
                await self._ws_assistant.send(WSJSONRequest(payload=order_payload))
            
            # Subscribe to position updates (for perpetuals)
            position_payload = {
                "method": "subscribe",
                "params": ["position"],
            }
            await self._ws_assistant.send(WSJSONRequest(payload=position_payload))
            
            self.logger().info("Subscribed to user data streams")
            
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Error subscribing to user streams", exc_info=True)
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Processes messages from the WebSocket.
        
        :param websocket_assistant: The WebSocket assistant
        :param queue: Queue to put processed messages
        """
        while True:
            try:
                message = await websocket_assistant.receive()
                if message is None:
                    continue
                
                # Process the message
                data = message.data
                if isinstance(data, dict):
                    # Add message to queue for processing
                    await queue.put(data)
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error processing WebSocket message: {e}", exc_info=True)
                raise

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Listens for user stream messages.
        
        :param output: Queue to output messages
        """
        while True:
            try:
                websocket_assistant: WSAssistant = await self._connected_websocket_assistant()
                await self._process_websocket_messages(websocket_assistant, output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _sleep(self, delay: float):
        """
        Async sleep that can be cancelled.
        
        :param delay: Sleep duration in seconds
        """
        await asyncio.sleep(delay)
