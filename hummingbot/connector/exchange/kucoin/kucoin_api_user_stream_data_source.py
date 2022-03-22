import asyncio
import logging
import time
from typing import Optional

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_web_utils as web_utils,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class KucoinAPIUserStreamDataSource(UserStreamTrackerDataSource):
    PING_TIMEOUT = 50.0

    _kausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_ws_message_sent_timestamp = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kausds_logger is None:
            cls._kausds_logger = logging.getLogger(__name__)
        return cls._kausds_logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection, listens to all balance events and order updates provided by the exchange and stores them in the
        output queue

        :param output: The queue where all received events should be stored
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                connection_info = await web_utils.api_request(
                    path=CONSTANTS.PRIVATE_WS_DATA_PATH_URL,
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    domain=self._domain,
                    method=RESTMethod.POST,
                    is_auth_required=True,
                )

                ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
                ping_interval = int(int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3)
                token = connection_info["data"]["token"]

                ws = await self._get_ws_assistant()
                await ws.connect(ws_url=f"{ws_url}?token={token}", message_timeout=ping_interval)
                await ws.ping()  # to update last_recv_timestamp
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()

                while True:
                    try:
                        seconds_until_next_ping = ping_interval - (self._time() - self._last_ws_message_sent_timestamp)
                        await asyncio.wait_for(self._process_ws_messages(websocket_assistant=ws, output=output),
                                               timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        payload = {
                            "id": web_utils.next_message_id(),
                            "type": "ping",
                        }
                        ping_request = WSRequest(payload=payload)
                        self._last_ws_message_sent_timestamp = self._time()
                        await ws.send(request=ping_request)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to user streams. Retrying in 5 seconds...")
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            orders_change_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": "/spotMarket/tradeOrders",
                "privateChannel": True,
                "response": False,
            }
            subscribe_order_change_request: WSRequest = WSRequest(payload=orders_change_payload)

            balance_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": "/account/balance",
                "privateChannel": True,
                "response": False,
            }
            subscribe_balance_request: WSRequest = WSRequest(payload=balance_payload)

            await ws.send(subscribe_order_change_request)
            await ws.send(subscribe_balance_request)

            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_ws_messages(self, websocket_assistant: WSAssistant, output: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if (data.get("type") == "message"
                    and data.get("subject") in [CONSTANTS.ORDER_CHANGE_EVENT_TYPE,
                                                CONSTANTS.BALANCE_EVENT_TYPE]):
                output.put_nowait(data)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _time(self):
        return time.time()
