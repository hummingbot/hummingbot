import asyncio
from typing import TYPE_CHECKING, List, Optional

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_derivative import VegaPerpetualDerivative


class VegaPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(
            self,
            connector: 'VegaPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):

        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._ws_total_count = 0
        self._ws_total_closed_count = 0
        self._ws_connected = True

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        t = 0.0
        if len(self._ws_assistants) > 0:
            t = min([wsa.last_recv_time for wsa in self._ws_assistants])
        return t

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        tasks_future = None
        try:
            tasks = []
            if self._connector._best_connection_endpoint == "":
                await self._connector.connection_base()

            tasks.append(
                # account stream
                self._start_websocket(url=f"{web_utils._wss_url(CONSTANTS.ACCOUNT_STREAM_URL, self._connector._best_connection_endpoint)}?partyId={self._connector.vega_perpetual_public_key}",
                                      channel_id=CONSTANTS.ACCOUNT_STREAM_ID,
                                      output=output)
            )
            tasks.append(
                # orders stream
                self._start_websocket(url=f"{web_utils._wss_url(CONSTANTS.ORDERS_STREAM_URL, self._connector._best_connection_endpoint)}?partyIds={self._connector.vega_perpetual_public_key}",
                                      channel_id=CONSTANTS.ORDERS_STREAM_ID,
                                      output=output)
            )
            tasks.append(
                # positions stream
                self._start_websocket(url=f"{web_utils._wss_url(CONSTANTS.POSITIONS_STREAM_URL, self._connector._best_connection_endpoint)}?partyId={self._connector.vega_perpetual_public_key}",
                                      channel_id=CONSTANTS.POSITIONS_STREAM_ID,
                                      output=output)
            )
            tasks.append(
                # trades stream
                self._start_websocket(url=f"{web_utils._wss_url(CONSTANTS.TRADE_STREAM_URL, self._connector._best_connection_endpoint)}?partyIds={self._connector.vega_perpetual_public_key}",
                                      channel_id=CONSTANTS.TRADES_STREAM_ID,
                                      output=output)
            )

            tasks_future = asyncio.gather(*tasks)
            await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def _start_websocket(self, url: str, channel_id: str, output: asyncio.Queue):
        ws: Optional[WSAssistant] = None
        self._ws_total_count += 1
        _sleep_count = 0
        while True:
            try:
                ws = await self._get_connected_websocket_assistant(url)
                self._ws_assistants.append(ws)
                await ws.ping()
                _sleep_count = 0  # success, reset sleep count
                self._ws_connected = True
                await self._process_websocket_messages(websocket_assistant=ws, channel_id=channel_id, queue=output)

            except Exception as e:
                self._ws_total_closed_count += 1
                self.logger().error("Websocket closed.  Reconnecting. Retrying after 1 seconds...")
                self.logger().debug(e)
                _sleep_count += 1
                _sleep_duration = 1.0
                if _sleep_count > 10:
                    # sleep for longer as we keep failing
                    self._ws_connected = False
                    _sleep_duration = 30.0
                await self._sleep(_sleep_duration)
            finally:
                await self._on_user_stream_interruption(ws)
                if ws in self._ws_assistants:
                    ws and self._ws_assistants.remove(ws)

    async def _get_connected_websocket_assistant(self, ws_url: str) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, channel_id: str, queue: asyncio.Queue):
        while True:
            try:
                async for ws_response in websocket_assistant.iter_messages():
                    data = ws_response.data
                    data["channel_id"] = channel_id

                    await self._process_event_message(event_message=data, queue=queue)

            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"op": "ping"})  # pragma: no cover
                await websocket_assistant.send(ping_request)  # pragma: no cover

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass  # pragma: no cover

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # pragma: no cover

    async def _authenticate(self, ws: WSAssistant):
        pass  # pragma: no cover
