import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange


class NdaxAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        auth: NdaxAuth,
        trading_pairs: str,
        connector: "NdaxExchange",
        api_factory: WebAssistantsFactory,
        domain: Optional[str] = None,
    ):
        super().__init__()
        self._trading_pairs = trading_pairs
        self._ws_adaptor = None
        self._auth_assistant: NdaxAuth = auth
        self._last_recv_time: float = 0
        self._account_id: Optional[int] = None
        self._oms_id: Optional[int] = None
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> NdaxWebSocketAdaptor:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = CONSTANTS.WSS_URLS.get(self._domain or "ndax_main")
        await ws.connect(ws_url=url)
        return NdaxWebSocketAdaptor(ws)

    async def _authenticate(self, ws: NdaxWebSocketAdaptor):
        """
        Authenticates user to websocket
        """
        try:
            await ws.send_request(
                CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME, self._auth_assistant.header_for_authentication()
            )
            auth_resp = await ws.websocket.receive()
            auth_payload: Dict[str, Any] = ws.payload_from_raw_message(auth_resp.data)

            if not auth_payload["Authenticated"]:
                self.logger().error(f"Response: {auth_payload}", exc_info=True)
                raise Exception("Could not authenticate websocket connection with NDAX")

            auth_user = auth_payload.get("User")
            self._account_id = auth_user.get("AccountId")
            self._oms_id = auth_user.get("OMSId")

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred when authenticating to user stream ({ex})", exc_info=True)
            raise

    async def _subscribe_channels(self, ws: NdaxWebSocketAdaptor):
        """
        Subscribes to User Account Events
        """
        payload = {"AccountId": self._account_id, "OMSId": self._oms_id}
        try:
            await ws.send_request(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME, payload)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(
                f"Error occurred subscribing to {CONSTANTS.EXCHANGE_NAME} private channels ({ex})", exc_info=True
            )
            raise

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages

        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                ws: NdaxWebSocketAdaptor = await self._connected_websocket_assistant()
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_channels(ws)
                self.logger().info("Successfully subscribed to user events.")

                await ws.process_websocket_messages(queue=output)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
                await self._sleep(1.0)
            finally:
                await self._on_user_stream_interruption(websocket_assistant=self._ws_assistant)
                self._ws_assistant = None
