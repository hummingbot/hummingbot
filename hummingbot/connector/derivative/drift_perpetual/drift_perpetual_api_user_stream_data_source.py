import asyncio
import logging
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.drift_perpetual.drift_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DriftPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Streams the operator's private events from the self-hosted Drift
    Gateway WebSocket (default ws://127.0.0.1:1337).

    Subscribe shape (verified, gateway README):
        {"method": "subscribe", "subAccountId": <int>}

    Event envelope (verified):
        {"data": {"orderCreate"|"fill"|"fundingPayment": {...}},
         "channel": "orders"|"fills"|"funding",
         "subAccountId": <int>}

    A single subscription delivers all three private channels for the
    sub-account; the connector's user-stream event listener demuxes by
    the `channel` field.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, api_factory: Optional[WebAssistantsFactory], connector):
        self._api_factory: WebAssistantsFactory = api_factory
        self._ws_assistant: Optional[WSAssistant] = None
        self._connector = connector
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = self._connector.drift_gateway_ws_url
        self.logger().info(f"Connecting to Drift Gateway WS {ws_url}")
        self._ws_assistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(
            ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_INTERVAL
        )
        return self._ws_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            subscribe_request: WSJSONRequest = WSJSONRequest(
                payload={
                    "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                    "subAccountId": self._connector.sub_account_id,
                },
                is_auth_required=False,
            )
            await websocket_assistant.send(subscribe_request)
            self.logger().info(
                f"Subscribed to Drift private channels "
                f"(orders/fills/funding) for sub-account "
                f"{self._connector.sub_account_id}"
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to Drift user stream channels.")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        # Forward only payload-bearing events; ignore subscribe acks /
        # heartbeats that carry no `data`/`channel`.
        if not isinstance(event_message, dict):
            return
        if event_message.get("channel") in (
            CONSTANTS.WS_CHANNEL_ORDERS,
            CONSTANTS.WS_CHANNEL_FILLS,
            CONSTANTS.WS_CHANNEL_FUNDING,
        ) and event_message.get("data") is not None:
            queue.put_nowait(event_message)
