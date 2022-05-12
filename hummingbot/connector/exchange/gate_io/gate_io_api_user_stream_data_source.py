import asyncio
import logging
import time
from typing import List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_web_utils import APIError
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class GateIoAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth,
                 trading_pairs: List[str],
                 domain: str = "",
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__()
        self._api_factory = api_factory
        self._auth: GateIoAuth = auth
        self._trading_pairs: List[str] = trading_pairs
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_ws_message_sent_timestamp = 0

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
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages

        :param output: an async queue where the incoming messages are stored
        """

        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WS_URL, ping_timeout=CONSTANTS.PING_TIMEOUT)
                await ws.ping()  # to update last_recv_timestamp
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()
                await self._process_ws_messages(websocket_assistant=ws, output=output)

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
            symbols = [await GateIoAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                api_factory=self._api_factory) for trading_pair in self._trading_pairs]

            orders_change_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                "event": "subscribe",
                "payload": symbols
            }
            subscribe_order_change_request: WSRequest = WSRequest(payload=orders_change_payload, is_auth_required=True)

            trades_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                "event": "subscribe",
                "payload": symbols
            }
            subscribe_trades_request: WSRequest = WSRequest(payload=trades_payload, is_auth_required=True)

            balance_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
                "event": "subscribe",  # "unsubscribe" for unsubscription
            }
            subscribe_balance_request: WSRequest = WSRequest(payload=balance_payload, is_auth_required=True)

            await ws.send(subscribe_order_change_request)
            await ws.send(subscribe_trades_request)
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
            if data.get("error") is not None:
                err_msg = data.get("error", {}).get("message", data["error"])
                raise APIError({
                    "label": "WSS_ERROR",
                    "message": f"Error received via websocket - {err_msg}."
                })
            elif data.get("event") == "update" and data.get("channel") in [
                CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
            ]:
                output.put_nowait(data)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _time(self):
        return time.time()
