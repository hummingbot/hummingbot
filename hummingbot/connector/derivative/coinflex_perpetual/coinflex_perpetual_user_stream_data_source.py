import asyncio
import logging
from typing import Dict, List, Optional

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_auth import CoinflexPerpetualAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class CoinflexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _cfpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cfpusds_logger is None:
            cls._cfpusds_logger = logging.getLogger(__name__)
        return cls._cfpusds_logger

    def __init__(
        self,
        auth: CoinflexPerpetualAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__()
        self._auth: CoinflexPerpetualAuth = auth
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler
        self._api_factory: WebAssistantsFactory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            auth=auth)
        self._ws_assistant: Optional[WSAssistant] = None
        self._subscribed_channels: List[str] = []

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        if not all([chan in self._subscribed_channels for chan in CONSTANTS.WS_CHANNELS["USER_STREAM"]]):
            return 0
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload: Dict[str, str] = {
                "op": "subscribe",
                "args": CONSTANTS.WS_CHANNELS["USER_STREAM"],
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_request)

            self.logger().info("Subscribing to private channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private streams...",
                exc_info=True
            )
            raise

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(
                    ws_url=web_utils.websocket_url(domain=self._domain),
                    ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await ws.send(WSJSONRequest({}, is_auth_required=True))
                await self._subscribe_channels(ws)
                await ws.ping()  # to update last_recv_timestamp

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    event_type = data.get("event")
                    if event_type == "subscribe" and data.get("channel"):
                        self._subscribed_channels.append(data.get("channel"))
                        self.logger().info(f"Subscribed to private channel - {data.get('channel')}...")
                    elif len(data) > 0:
                        output.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error while listening to user stream. Retrying after 5 seconds... "
                    f"Error: {e}",
                    exc_info=True,
                )
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                self._subscribed_channels = []
                await self._sleep(5)
