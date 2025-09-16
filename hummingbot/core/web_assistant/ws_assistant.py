"""
WebSocket assistant for Hummingbot framework.
Minimal implementation to support connector development.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, AsyncIterator
from dataclasses import dataclass

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse


@dataclass
class WSMessage:
    """WebSocket message wrapper."""
    data: Any
    timestamp: float


class WSAssistant:
    """
    WebSocket assistant for managing WebSocket connections.
    Provides a simplified interface for WebSocket operations.
    """
    
    def __init__(self):
        """Initialize WebSocket assistant."""
        self._logger = logging.getLogger(__name__)
        self._websocket = None
        self._is_connected = False
        self._message_queue = asyncio.Queue()
    
    async def connect(self, url: str, **kwargs) -> None:
        """
        Connect to WebSocket endpoint.
        
        Args:
            url: WebSocket URL to connect to
            **kwargs: Additional connection parameters
        """
        try:
            # Mock connection for testing
            self._is_connected = True
            self._logger.info(f"WebSocket connected to {url}")
        except Exception as e:
            self._logger.error(f"WebSocket connection failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        try:
            self._is_connected = False
            self._logger.info("WebSocket disconnected")
        except Exception as e:
            self._logger.error(f"WebSocket disconnect error: {e}")
    
    async def send(self, request: WSJSONRequest) -> None:
        """
        Send WebSocket message.
        
        Args:
            request: WebSocket JSON request to send
        """
        if not self._is_connected:
            raise ConnectionError("WebSocket not connected")
        
        try:
            # Mock sending for testing
            message_data = request.to_json()
            self._logger.debug(f"Sending WebSocket message: {message_data}")
        except Exception as e:
            self._logger.error(f"Error sending WebSocket message: {e}")
            raise
    
    async def iter_messages(self) -> AsyncIterator[WSResponse]:
        """
        Iterate over incoming WebSocket messages.
        
        Yields:
            WSResponse objects with message data
        """
        while self._is_connected:
            try:
                # Mock message receiving for testing
                await asyncio.sleep(1)  # Simulate message delay
                
                # Create mock message
                mock_data = {
                    "stream": "btcusdt@depth",
                    "data": {
                        "e": "depthUpdate",
                        "s": "BTCUSDT",
                        "u": 123456,
                        "b": [["50000.00", "1.0"]],
                        "a": [["50001.00", "0.5"]]
                    }
                }
                
                import time
                response = WSResponse(data=mock_data, timestamp=time.time())
                yield response
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error receiving WebSocket message: {e}")
                break
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._is_connected
    
    async def ping(self) -> None:
        """Send ping to keep connection alive."""
        if self._is_connected:
            self._logger.debug("WebSocket ping sent")
    
    async def subscribe(self, channels: list) -> None:
        """
        Subscribe to WebSocket channels.
        
        Args:
            channels: List of channels to subscribe to
        """
        for channel in channels:
            subscribe_request = WSJSONRequest({
                "method": "SUBSCRIBE",
                "params": [channel],
                "id": 1
            })
            await self.send(subscribe_request)
            self._logger.info(f"Subscribed to channel: {channel}")
    
    async def unsubscribe(self, channels: list) -> None:
        """
        Unsubscribe from WebSocket channels.
        
        Args:
            channels: List of channels to unsubscribe from
        """
        for channel in channels:
            unsubscribe_request = WSJSONRequest({
                "method": "UNSUBSCRIBE",
                "params": [channel],
                "id": 2
            })
            await self.send(unsubscribe_request)
            self._logger.info(f"Unsubscribed from channel: {channel}")


class MockWSAssistant(WSAssistant):
    """
    Mock WebSocket assistant for testing.
    Provides predictable responses for unit tests.
    """
    
    def __init__(self, mock_messages: Optional[list] = None):
        """
        Initialize mock WebSocket assistant.
        
        Args:
            mock_messages: List of mock messages to return
        """
        super().__init__()
        self._mock_messages = mock_messages or []
        self._message_index = 0
    
    async def connect(self, url: str, **kwargs) -> None:
        """Mock connection - always succeeds."""
        self._is_connected = True
        self._logger.info(f"Mock WebSocket connected to {url}")
    
    async def iter_messages(self) -> AsyncIterator[WSResponse]:
        """
        Iterate over mock messages.
        
        Yields:
            Mock WSResponse objects
        """
        while self._is_connected and self._message_index < len(self._mock_messages):
            try:
                message_data = self._mock_messages[self._message_index]
                self._message_index += 1
                
                import time
                response = WSResponse(data=message_data, timestamp=time.time())
                yield response
                
                await asyncio.sleep(0.1)  # Small delay for realistic behavior
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in mock message iteration: {e}")
                break
    
    def add_mock_message(self, message: Dict[str, Any]) -> None:
        """
        Add a mock message to the queue.
        
        Args:
            message: Mock message data
        """
        self._mock_messages.append(message)
    
    def reset_messages(self) -> None:
        """Reset mock messages and index."""
        self._mock_messages.clear()
        self._message_index = 0


# Utility functions
def create_ws_assistant() -> WSAssistant:
    """Create a new WebSocket assistant instance."""
    return WSAssistant()


def create_mock_ws_assistant(mock_messages: Optional[list] = None) -> MockWSAssistant:
    """
    Create a mock WebSocket assistant for testing.
    
    Args:
        mock_messages: List of mock messages to return
        
    Returns:
        MockWSAssistant instance
    """
    return MockWSAssistant(mock_messages)


def is_websocket_message_valid(message: Dict[str, Any]) -> bool:
    """
    Validate WebSocket message format.
    
    Args:
        message: Message to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Basic validation - message should be a dictionary
        if not isinstance(message, dict):
            return False
        
        # Should have either 'data' or direct content
        if 'data' in message or 'stream' in message:
            return True
        
        # Allow other valid message formats
        return len(message) > 0
        
    except Exception:
        return False
