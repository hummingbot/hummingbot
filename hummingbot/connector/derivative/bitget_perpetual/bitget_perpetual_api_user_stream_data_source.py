import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSPlainTextRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative


class BitgetPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Data source for retrieving user stream data from
    the Bitget Perpetual exchange via WebSocket APIs.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitgetPerpetualAuth,
        trading_pairs: List[str],
        connector: 'BitgetPerpetualDerivative',
        api_factory: WebAssistantsFactory,
    ) -> None:
        super().__init__()
        self._api_factory = api_factory
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._ping_task: Optional[asyncio.Task] = None

    async def _authenticate(self, websocket_assistant: WSAssistant) -> None:
        """
        Authenticates user to websocket.

        The login signature carries a timestamp that the exchange rejects once it is more than 30
        seconds from its own clock (error 30014, "Timestamp request expired"). Hummingbot's
        TimeSynchronizer derives that timestamp from time.perf_counter(), which does not advance
        while the host is suspended, so after a laptop sleep or a long network stall the offset is
        stale and every login is refused until enough fresh samples have flushed the 5-sample
        buffer. Re-sampling the server clock before signing is what Bitget's own documentation
        recommends, and a reconnect is rare enough that the extra request costs nothing.
        """
        await self._refresh_server_time_offset()

        await websocket_assistant.send(
            WSJSONRequest({
                "op": "login",
                "args": [self._auth.get_ws_auth_payload()]
            })
        )
        response: WSResponse = await websocket_assistant.receive()
        message = response.data

        # The login is only successful when the exchange echoes the "login" event *and* reports a
        # zero result code. Either one alone being wrong means the session was rejected, so the
        # listener must fail here and reconnect instead of subscribing on a rejected session.
        if message.get("event") != "login" or str(message.get("code")) != "0":
            self.logger().error(
                f"Error authenticating the private websocket connection. Response message {message}"
            )
            raise IOError("Private websocket connection authentication failed")

    async def _refresh_server_time_offset(self) -> None:
        """
        Re-samples the server clock and makes the fresh sample the whole offset.

        TimeSynchronizer keeps a five-sample deque and derives the offset from their median and
        weighted average, so appending one fresh sample to five stale ones barely moves it: after
        an hour-long suspend the offset is still ~49 minutes out, and it takes five fresh samples
        to recover. The stale samples are therefore discarded, but only once Bitget has answered.
        Discarding them before the request would leave none if it fails, and the synchronizer
        would then sign with the local clock, which is exactly what the offset corrects. A failed
        request is logged by the synchronizer and the existing offset stays in place.
        """
        synchronizer = self._connector._time_synchronizer

        async def server_time_replacing_stale_samples() -> float:
            server_time = await web_utils.get_current_server_time(
                throttler=self._connector._throttler,
                domain=self._connector.domain,
            )
            # The synchronizer records the fresh sample right after this returns, with nothing
            # awaited in between, so no request is ever signed with an empty buffer.
            synchronizer.clear_time_offset_ms_samples()
            return server_time

        await synchronizer.update_server_time_offset_with_time_provider(
            time_provider=server_time_replacing_stale_samples()
        )

    async def _parse_pong_message(self) -> None:
        self.logger().debug("PING-PONG message for user stream completed")

    async def _process_message_for_unknown_channel(
        self,
        event_message: Dict[str, Any]
    ) -> None:
        if event_message == CONSTANTS.PUBLIC_WS_PONG_RESPONSE:
            await self._parse_pong_message()
        elif "event" in event_message:
            if event_message["event"] == "error":
                message = event_message.get("msg", "Unknown error")
                error_code = event_message.get("code", "Unknown code")
                error = f"Failed to subscribe to private channels: {message} ({error_code})"
                # A rejected subscription leaves the connection up but silent, so raise to let
                # listen_for_user_stream tear the session down and resubscribe from scratch. Pause
                # first: the listener reconnects a second after the raise, so a rejection that never
                # clears would otherwise repeat connect, login and subscribe about once a second.
                self.logger().error(error)
                await self._sleep(CONSTANTS.WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS)
                raise IOError(error)

            if event_message["event"] == "subscribe":
                # V3 names the channel "topic", V2 (Classic accounts) "channel".
                arg = event_message["arg"]
                channel: str = arg.get("topic", arg.get("channel", ""))
                self.logger().info(f"Subscribed to private channel: {channel.upper()}")
        else:
            self.logger().warning(f"Message for unknown channel received: {event_message}")

    async def _process_event_message(
        self,
        event_message: Dict[str, Any],
        queue: asyncio.Queue
    ) -> None:
        if "arg" in event_message and "action" in event_message:
            queue.put_nowait(event_message)
        else:
            await self._process_message_for_unknown_channel(event_message)

    async def _subscription_topics(self) -> List[Dict[str, str]]:
        if not await self._connector._is_unified_account():
            # Classic (V2): every channel once per product type traded.
            product_types: set[str] = {
                await self._connector.product_type_associated_to_trading_pair(trading_pair)
                for trading_pair in self._trading_pairs
            } or set(CONSTANTS.ALL_PRODUCT_TYPES)
            return [
                {"instType": product_type, "channel": channel, "coin": "default"}
                for product_type in product_types
                for channel in (
                    CONSTANTS.CLASSIC_WS_ACCOUNT_ENDPOINT,
                    CONSTANTS.CLASSIC_WS_POSITIONS_ENDPOINT,
                    CONSTANTS.CLASSIC_WS_ORDERS_ENDPOINT,
                )
            ]
        # Under the V3 UTA account private channels are subscribed with instType "UTA" and cover the
        # whole unified account (no per-product-type fan-out).
        return [
            {"instType": CONSTANTS.INST_TYPE_UTA, "topic": channel}
            for channel in (
                CONSTANTS.WS_ACCOUNT_ENDPOINT,
                CONSTANTS.WS_POSITIONS_ENDPOINT,
                CONSTANTS.WS_ORDERS_ENDPOINT,
                CONSTANTS.WS_FILL_ENDPOINT,
            )
        ]

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        try:
            subscription_topics = await self._subscription_topics()

            await websocket_assistant.send(
                WSJSONRequest({
                    "op": "subscribe",
                    "args": subscription_topics
                })
            )

            self.logger().info("Subscribed to private channels...")
            self._ping_task = asyncio.create_task(self.send_interval_ping(websocket_assistant))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                "Unexpected error occurred subscribing to private channels..."
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        unified_account = await self._connector._is_unified_account()
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(
            ws_url=web_utils.private_ws_url() if unified_account else web_utils.classic_private_ws_url(),
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        await self._authenticate(websocket_assistant)

        return websocket_assistant

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        await websocket_assistant.send(
            WSPlainTextRequest(CONSTANTS.PUBLIC_WS_PING_REQUEST)
        )

    async def send_interval_ping(self, websocket_assistant: WSAssistant) -> None:
        """
        Coroutine to send PING messages periodically. The first ping is the one listen_for_user_stream
        sends right after subscribing.

        :param websocket_assistant: The websocket assistant to use to send the PING message.
        """
        try:
            while True:
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await self._send_ping(websocket_assistant)
        except asyncio.CancelledError:
            self.logger().info("Interval PING task cancelled")
            raise
        except Exception:
            self.logger().exception("Error sending interval PING")

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
