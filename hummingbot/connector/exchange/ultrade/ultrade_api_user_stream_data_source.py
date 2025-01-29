import asyncio
import time
from typing import TYPE_CHECKING, List, Optional

from ultrade import Client as UltradeClient, socket_options

from hummingbot.connector.exchange.ultrade import ultrade_constants as CONSTANTS
from hummingbot.connector.exchange.ultrade.ultrade_auth import UltradeAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ultrade.ultrade_exchange import UltradeExchange


class UltradeAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: UltradeAuth,
                 trading_pairs: List[str],
                 connector: 'UltradeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: UltradeAuth = auth
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs

        self.ultrade_client = self.create_ultrade_client()
        self.ultrade_events_queue: asyncio.Queue = asyncio.Queue()
        self.subscriptions_list: List[str] = []
        self._last_recv_time = 1.0

    def create_ultrade_client(self) -> UltradeClient:
        client = UltradeClient(network=self._domain)
        client.set_trading_key(
            trading_key=self._connector.ultrade_trading_key,
            address=self._connector.ultrade_wallet_address,
            trading_key_mnemonic=self._connector.ultrade_mnemonic_key
        )
        return client

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        while True:
            try:
                self._message_queue = output
                self._ws_assistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(websocket_assistant=self._ws_assistant)
                await self._process_websocket_messages_ultrade()
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 1 seconds...")
                await self._sleep(1.0)
            finally:
                await self._on_user_stream_interruption(websocket_assistant=self._ws_assistant)
                self._ws_assistant = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        return ws

    def ultrade_user_streams_event_handler(self, event_name, event_data):
        try:
            self.logger().info(f"STREAM::Received message from Ultrade: {event_name} - {event_data}")
            if event_name is not None and event_data is not None:
                event_message = {
                    "event": event_name,
                    "data": event_data
                }
                self.ultrade_events_queue.put_nowait(event_message)
                self._last_recv_time = int(time.time())
        except Exception:
            raise

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        Ultrade does not require any channel subscription.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                request = {
                    'symbol': symbol,
                    'streams': [
                        socket_options.ORDERS,
                        socket_options.TRADES,
                        socket_options.CODEX_BALANCES
                    ],
                    'options': {
                        'address': self._connector.ultrade_wallet_address,
                        'company_id': 1,
                    }
                }
                self.logger().info(f"Subscribing to user streams for {trading_pair} with options: {request}")

                connection_id: str = str(await self.ultrade_client.subscribe(request, self.ultrade_user_streams_event_handler))
                self.subscriptions_list.append(connection_id)
                self.logger().info(f"Subscribed to user streams for {trading_pair} with connection ID: {connection_id} with options: {request}")

            self.logger().info("Subscribed to private user streams...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to user streams...",
                exc_info=True
            )
            raise

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _process_websocket_messages_ultrade(self):
        while True:
            try:
                event = await self.ultrade_events_queue.get()
                event_name = event["event"]
                self.logger().debug(f"STREAM::Processing message from Ultrade: {event}")
                if event_name in [CONSTANTS.USER_ORDER_EVENT_TYPE, CONSTANTS.USER_TRADE_EVENT_TYPE, CONSTANTS.USER_BALANCE_EVENT_TYPE]:
                    self._message_queue.put_nowait(event)
                else:
                    pass    # Ignore all other channels
            except Exception:
                raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        for connection_id in self.subscriptions_list:
            try:
                await self.ultrade_client.unsubscribe(str(connection_id))
            except Exception:
                continue
        self.subscriptions_list.clear()
