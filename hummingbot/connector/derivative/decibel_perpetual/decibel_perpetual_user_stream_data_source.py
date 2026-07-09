import asyncio
import time
from typing import TYPE_CHECKING, Optional

from hummingbot.connector.derivative.decibel_perpetual import (
    decibel_perpetual_constants as CONSTANTS,
    decibel_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )


class DecibelPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Decibel Perpetual.

    Handles private WebSocket channels for:
    - Account overview (balance, margin)
    - User positions
    - Open orders
    - User trades

    All subscriptions are subaccount-based since Decibel uses subaccounts for trading.
    """
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector: "DecibelPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        auth: DecibelPerpetualAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory
        self._auth = auth
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None
        self._subaccount_address: Optional[str] = None

    async def _get_account_address(self) -> str:
        """
        Get the account address for WebSocket subscriptions.
        Decibel uses main wallet address for all API queries (REST and WebSocket).
        Cached to avoid repeated access.
        """
        if self._subaccount_address is None:
            # Use main wallet address (not derived subaccount)
            self._subaccount_address = self._auth.main_wallet_address
        return self._subaccount_address

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect WebSocket assistant for private channels.
        Includes API key authentication in headers.
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        ws_url = web_utils.wss_url(self._domain)

        # Add authentication headers for WebSocket connection
        headers = {}
        if hasattr(self._connector, 'api_key') and self._connector.api_key:
            headers["Authorization"] = f"Bearer {self._connector.api_key}"

        await ws.connect(
            ws_url=ws_url,
            ping_timeout=None,  # Disable aiohttp heartbeat
            ws_headers=headers
        )
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        """
        Subscribe to private WebSocket channels.

        Decibel private channel format:
        {
            "method": "subscribe",
            "params": {
                "topic": "account_overview:<subaccount_address>"
            }
        }
        """
        try:
            account_addr = await self._get_account_address()

            # Subscribe to account overview (balance, margin, etc.)
            account_overview_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_ACCOUNT_OVERVIEW_CHANNEL}:{account_addr}"
            }

            # Subscribe to user positions
            user_positions_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_USER_POSITIONS_CHANNEL}:{account_addr}"
            }

            # Subscribe to open orders
            open_orders_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_USER_OPEN_ORDERS_CHANNEL}:{account_addr}"
            }

            # Subscribe to user trades
            user_trades_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_USER_TRADES_CHANNEL}:{account_addr}"
            }

            await websocket_assistant.send(WSJSONRequest(account_overview_payload))
            await websocket_assistant.send(WSJSONRequest(user_positions_payload))
            await websocket_assistant.send(WSJSONRequest(open_orders_payload))
            await websocket_assistant.send(WSJSONRequest(user_trades_payload))

            self.logger().debug(f"Subscribed to private channels for account {account_addr}")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to private user streams")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handle WebSocket interruption/disconnection.
        """
        await super()._on_user_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        """
        Send periodic ping to keep WebSocket connection alive.
        We update `self._last_recv_time` directly so Hummingbot knows the connection
        is active even if the exchange sends no user messages (e.g. empty testnet).
        """
        while True:
            try:
                ping_request = WSJSONRequest({"method": "ping"})
                await ws.send(ping_request)

                # Update last_recv_time so the connector becomes instantly ready
                # and doesn't get marked as stalled by the tracker.
                self._last_recv_time = time.time()

                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().debug("Error sending ping to Decibel WebSocket", exc_info=True)
                await asyncio.sleep(5.0)
