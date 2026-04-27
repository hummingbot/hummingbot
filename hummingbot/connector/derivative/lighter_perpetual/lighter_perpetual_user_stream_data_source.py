import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
        LighterPerpetualDerivative,
    )


class LighterPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector: "LighterPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        auth: LighterPerpetualAuth,
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
        if self._connector.rest_api_key:
            ws_headers["X-Api-Key"] = self._connector.rest_api_key

        await ws.connect(ws_url=web_utils.wss_url(self._domain), ws_headers=ws_headers)
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        try:
            response: Optional[WSResponse] = await websocket_assistant.receive()
            message: Dict[str, Any] = response.data if response is not None else {}
            if message.get("type") != "connected":
                raise IOError("Private websocket connection did not acknowledge the session")

            # Some environments emit private events for different account identifiers
            # (account index, wallet/public key, api key index). Subscribe to all known
            # candidates and both delimiter styles to avoid missing manual exchange updates.
            account_identifiers = {
                str(self._auth.user_wallet_public_key),
                str(getattr(self._connector, "account_index", "") or ""),
                str(getattr(self._connector, "api_key_index", "") or ""),
            }
            account_identifiers.discard("")

            channels = (
                CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
                CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL,
                CONSTANTS.WS_ACCOUNT_POSITIONS_CHANNEL,
                CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL,
                CONSTANTS.WS_ACCOUNT_INFO_CHANNEL,
            )

            sent_channels = set()
            for account_identifier in account_identifiers:
                for channel_const in channels:
                    for channel in (f"{channel_const}/{account_identifier}", f"{channel_const}:{account_identifier}"):
                        if channel in sent_channels:
                            continue
                        await websocket_assistant.send(WSJSONRequest({
                            "type": "subscribe",
                            "channel": channel,
                        }))
                        sent_channels.add(channel)

            # Also subscribe to the dedicated per-type channels so each event type
            # arrives independently via its own channel subscription.
            self.logger().info(
                "Subscribed to private account channels for identifiers=%s (%d subscriptions)",
                sorted(account_identifiers),
                len(sent_channels),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data.get("type") == "ping":
                await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
                continue
            await self._process_event_message(event_message=data, queue=queue)

    _ACCEPTED_CHANNEL_PREFIXES = (
        "account_all",
        "account_order_updates",
        "account_positions",
        "account_trades",
        "account_info",
    )

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        message_type = str(event_message.get("type", ""))
        channel = str(event_message.get("channel", ""))
        event_type_name = message_type.split("/", 1)[1] if "/" in message_type else message_type
        # Forward account_all messages (subscribed/update variants) AND all dedicated channel messages.
        if (
            event_type_name in self._ACCEPTED_CHANNEL_PREFIXES
            or "account_all" in message_type
            or any(channel.startswith(f"{prefix}/") or channel.startswith(f"{prefix}:") for prefix in self._ACCEPTED_CHANNEL_PREFIXES)
            or channel in self._ACCEPTED_CHANNEL_PREFIXES
        ):
            queue.put_nowait(event_message)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        while True:
            try:
                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
                await ws.send(WSJSONRequest(payload={"type": "ping"}))
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().warning("Error sending ping to LIGHTER WebSocket", exc_info=True)
                await asyncio.sleep(5.0)
