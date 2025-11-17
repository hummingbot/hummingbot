import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
        LighterPerpetualDerivative,
    )


class LighterPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AuthBase,
        trading_pairs: List[str],
        connector: "LighterPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._trading_pairs = trading_pairs
        self._ws_assistant: Optional[WSAssistant] = None
        self._current_auth_token: Optional[str] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger("LighterPerpetualUserStreamDataSource")
        return cls._logger

    @property
    def _ws(self) -> WSAssistant:
        if self._ws_assistant is None:
            raise RuntimeError("Websocket assistant not initialized.")
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_url(self._domain),
            ping_timeout=self.HEARTBEAT_TIME_INTERVAL,
        )
        safe_ensure_future(self._send_heartbeat(ws))
        self._ws_assistant = ws
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            self._current_auth_token = await self._auth.create_auth_token()
            account_index = self._connector.account_index
            subscriptions = [
                CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_CHANNEL.format(
                    account_index=account_index
                ),
                CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_ORDERS_CHANNEL.format(
                    account_index=account_index
                ),
                CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_TRADES_CHANNEL.format(
                    account_index=account_index
                ),
                CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_POSITIONS_CHANNEL.format(
                    account_index=account_index
                ),
            ]
            for trading_pair in self._trading_pairs:
                market_id = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair
                )
                subscriptions.append(
                    CONSTANTS.PRIVATE_WS_ACCOUNT_MARKET_CHANNEL.format(
                        account_index=account_index, market_id=market_id
                    )
                )
            for channel in subscriptions:
                payload = {
                    "type": "subscribe",
                    "channel": channel,
                    "auth": self._current_auth_token,
                }
                await ws.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to private user channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                "Unexpected error occurred subscribing to user streams..."
            )
            raise

    async def _process_event_message(
        self, event_message: Dict[str, Any], queue: asyncio.Queue
    ):
        if event_message.get("type") == "error":
            raise IOError(event_message)
        channel = event_message.get("channel", "")
        if channel.startswith("account_") or channel in {
            CONSTANTS.WS_TRANSACTION_CHANNEL,
            CONSTANTS.WS_EXECUTED_TRANSACTION_CHANNEL,
        }:
            queue.put_nowait(event_message)

    async def _send_heartbeat(self, ws: WSAssistant):
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_TIME_INTERVAL)
                await ws.send(WSJSONRequest(payload={"type": "ping"}))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().debug("Heartbeat task error", exc_info=True)

    async def _process_websocket_messages(
        self, websocket_assistant: WSAssistant, queue: asyncio.Queue
    ):
        while True:
            try:
                message = await websocket_assistant.receive_json()
                await self._process_event_message(message, queue)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error while processing user stream messages"
                )
                await self._sleep(5)
