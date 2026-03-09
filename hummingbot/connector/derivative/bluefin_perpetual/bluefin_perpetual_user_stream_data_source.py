"""
User stream data source for Bluefin Perpetual connector.

Handles account events via the Bluefin SDK including:
- Order updates
- Trade updates
- Position updates
- Account balance updates
"""
import asyncio
from typing import TYPE_CHECKING, Any, List, Optional

from hummingbot.core.web_assistant.ws_assistant import WSAssistant

from hummingbot.connector.derivative.bluefin_perpetual import bluefin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bluefin_perpetual.data_sources.bluefin_data_source import BluefinDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import (
        BluefinPerpetualDerivative,
    )


class BluefinPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """User stream data source for Bluefin Perpetual."""

    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'BluefinPerpetualDerivative',
        data_source: BluefinDataSource,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize user stream data source.

        :param trading_pairs: List of trading pairs
        :param connector: Parent connector instance
        :param data_source: Bluefin SDK data source wrapper
        :param domain: Domain (mainnet or staging)
        """
        super().__init__()
        self._connector = connector
        self._data_source = data_source
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._last_recv_time = 0

    @property
    def last_recv_time(self) -> float:
        """Get time of last received message."""
        return self._last_recv_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Bluefin SDK manages websocket lifecycle in the shared data source."""
        factory = getattr(self._connector, "_web_assistants_factory")
        return await factory.get_ws_assistant()

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """Subscriptions are configured by BluefinDataSource when streams are created."""
        del websocket_assistant

    async def listen_for_user_stream(self, output: asyncio.Queue[Any]):
        """
        Listen for user stream messages from the Bluefin SDK.

        Continuously receives account events and puts them in the output queue.
        The events are forwarded from the BluefinDataSource which manages
        the WebSocket connection via the SDK.

        :param output: Queue to put user stream messages
        """
        event_getters = [
            self._data_source.get_account_order_event,
            self._data_source.get_account_trade_event,
            self._data_source.get_account_position_event,
            self._data_source.get_account_balance_event,
        ]

        while True:
            pending_tasks = []
            try:
                pending_tasks = [asyncio.create_task(getter()) for getter in event_getters]
                done, pending = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Cancel all pending tasks
                for task in pending:
                    task.cancel()

                # Find first successfully completed task (without exception)
                event = None
                for task in done:
                    if not task.cancelled() and task.exception() is None:
                        event = task.result()
                        break

                # If no successful task was found, all getters failed/cancelled
                if event is None:
                    continue

                # Update last receive time
                self._last_recv_time = asyncio.get_event_loop().time()

                # Put event in output queue for processing by connector
                output.put_nowait(event)

                self.logger().debug("Received account event: %s", type(event).__name__)

            except asyncio.CancelledError:
                for task in pending_tasks:
                    task.cancel()
                raise
            except (AttributeError, RuntimeError, TypeError, ValueError):
                self.logger().exception(
                    "Unexpected error while listening for user stream. Retrying after 5 seconds..."
                )
                await asyncio.sleep(5)
