import asyncio
from typing import TYPE_CHECKING, Optional

from hummingbot.connector.derivative.pacifica_perpetual import (
    pacifica_perpetual_constants as CONSTANTS,
    pacifica_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_auth import PacificaPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_derivative import (
        PacificaPerpetualDerivative,
    )


class PacificaPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector: "PacificaPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        auth: PacificaPerpetualAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory
        self._auth = auth
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()

        ws_headers = {}
        if self._connector.api_config_key:
            ws_headers["PF-API-KEY"] = self._connector.api_config_key

        await ws.connect(ws_url=web_utils.wss_url(self._domain), ws_headers=ws_headers)
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        try:
            # https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-order-updates
            account_order_updates_payload = {
                "method": "subscribe",
                "params": {
                    "source": CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL,
                    "account": self._auth.user_wallet_public_key,
                }
            }

            # https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-positions
            account_positions_payload = {
                "method": "subscribe",
                "params": {
                    "source": CONSTANTS.WS_ACCOUNT_POSITIONS_CHANNEL,
                    "account": self._auth.user_wallet_public_key,
                }
            }

            # https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-info
            account_info_payload = {
                "method": "subscribe",
                "params": {
                    "source": CONSTANTS.WS_ACCOUNT_INFO_CHANNEL,
                    "account": self._auth.user_wallet_public_key,
                }
            }

            # https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-trades
            account_trades_payload = {
                "method": "subscribe",
                "params": {
                    "source": CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL,
                    "account": self._auth.user_wallet_public_key,
                }
            }

            await websocket_assistant.send(WSJSONRequest(account_order_updates_payload))
            await websocket_assistant.send(WSJSONRequest(account_positions_payload))
            await websocket_assistant.send(WSJSONRequest(account_info_payload))
            await websocket_assistant.send(WSJSONRequest(account_trades_payload))

            self.logger().info("Subscribed to private account and orders channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        while True:
            try:
                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
                await ws.send(WSJSONRequest(payload={"op": "ping"}))
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().warning("Error sending ping to Pacifica WebSocket", exc_info=True)
                await asyncio.sleep(5.0)
