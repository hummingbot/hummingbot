import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange


class LighterAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector: "LighterExchange",
        api_factory: WebAssistantsFactory,
        auth: LighterAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory
        self._auth = auth
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None
        self._last_listen_error_log_ts: float = 0.0
        self._has_logged_subscription_info: bool = False

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """Override base loop to throttle repeated reconnect exception logs."""
        while True:
            try:
                self._ws_assistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(websocket_assistant=self._ws_assistant)
                await self._send_ping(websocket_assistant=self._ws_assistant)
                await self._process_websocket_messages(websocket_assistant=self._ws_assistant, queue=output)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                close_message = str(connection_exception)
                if "close code = 1000" in close_message.lower():
                    self.logger().debug(f"The websocket connection was closed ({connection_exception})")
                else:
                    self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception as ex:
                now = time.time()
                if now - self._last_listen_error_log_ts >= 30.0:
                    self._last_listen_error_log_ts = now
                    self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
                else:
                    self.logger().debug(
                        "Suppressing repeated user stream listener error during reconnect storm: %s",
                        ex,
                    )
                await self._sleep(2.0)
            finally:
                await self._on_user_stream_interruption(websocket_assistant=self._ws_assistant)
                self._ws_assistant = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        ws_headers = {}
        if self._connector.rest_api_key:
            ws_headers["X-Api-Key"] = self._connector.rest_api_key
        await ws.connect(
            ws_url=web_utils.wss_url(self._domain),
            ws_headers=ws_headers,
            ping_timeout=CONSTANTS.WS_PING_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        response: Optional[WSResponse] = await websocket_assistant.receive()
        message: Dict[str, Any] = response.data if response is not None else {}
        if message.get("type") != "connected":
            raise IOError("Private websocket connection did not acknowledge the session")

        account_identifiers = {
            str(self._auth.user_wallet_public_key),
            str(getattr(self._connector, "account_index", "") or ""),
            str(getattr(self._connector, "api_key_index", "") or ""),
        }
        account_identifiers.discard("")

        sent_channels: set = set()
        auth_token = ""
        try:
            auth_token = str(self._connector._get_lighter_auth_token() or "")
        except Exception:
            auth_token = ""

        # Subscribe SPOT private channels.
        # • account_all            → full account snapshot (assets, orders, trades) on connect;
        #                            incremental updates as orders change state.
        # • account_all_assets     → real-time balance updates (auth token required).
        # • account_all_orders     → full-JSON order history snapshot + incremental updates;
        #                            populates client_order_index → order_id mapping and
        #                            triggers fill-detection when FILLED/CANCELED state arrives.
        # • account_all_trades
        #   Real-time fill channel with ask_client_id/bid_client_id fields.
        #
        # Legacy channels account_trades/account_order_updates are not subscribed
        # for SPOT because they are not consistently supported across environments.
        #
        # Delimiter format differs by deployment (":" vs "/").
        # Subscribe using both formats and rely on Invalid Channel suppression.
        spot_private_channels = (
            CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_ASSETS_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL,
        )
        for account_identifier in sorted(account_identifiers):  # sorted for deterministic test order
            for base_channel in spot_private_channels:
                # Prefer slash format first (validated on live SPOT channels), keep ':' as fallback.
                for channel in (f"{base_channel}/{account_identifier}", f"{base_channel}:{account_identifier}"):
                    if channel in sent_channels:
                        continue
                    payload = {"type": "subscribe", "channel": channel}
                    if (
                        base_channel in {
                            CONSTANTS.WS_ACCOUNT_ALL_ASSETS_CHANNEL,
                            CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL,
                        }
                        and auth_token
                    ):
                        payload["auth"] = auth_token
                    await websocket_assistant.send(WSJSONRequest(payload))
                    sent_channels.add(channel)

        log_method = self.logger().debug
        log_method(
            "Subscribed to spot private channels=%s for %d account identifier(s) (%d subscriptions)",
            [c for c in spot_private_channels],
            len(account_identifiers),
            len(sent_channels),
        )
        self._has_logged_subscription_info = True

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data.get("type") == "ping":
                await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
                continue
            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            if "invalid channel" in str(err_msg).lower():
                self.logger().debug("Ignoring late 'Invalid Channel' response from server: %s", err_msg)
                return
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}.",
            })

        message_type = str(event_message.get("type", ""))
        channel = str(event_message.get("channel", ""))
        event_type_name = message_type.split("/", 1)[1] if "/" in message_type else message_type
        # Forward events from all SPOT private channels plus optional compatibility
        # channels used by some backend deployments.
        account_channels = (
            CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_ASSETS_CHANNEL,
            CONSTANTS.WS_ACCOUNT_TX_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL,
            CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL,
        )
        if (
            event_type_name in account_channels
            or any(message_type.endswith(f"/{account_channel}") for account_channel in account_channels)
            or any(channel.startswith(f"{account_channel}/") for account_channel in account_channels)
            or any(channel.startswith(f"{account_channel}:") for account_channel in account_channels)
            or channel in account_channels
        ):
            queue.put_nowait(event_message)
