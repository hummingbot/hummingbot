import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.crypto_com import crypto_com_constants as CONSTANTS
from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComExchange


class CryptoComAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CryptoComAuth,
                 trading_pairs: List[str],
                 connector: 'CryptoComExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: CryptoComAuth = auth
        self._connector = connector
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange, and authenticates it.
        """
        try:
            ws: WSAssistant = await self._get_ws_assistant()
            # url = CONSTANTS.WSS_PRIVATE_URL
            await ws.connect(ws_url=CONSTANTS.WSS_PRIVATE_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            self.logger().info("Connected to Cryto.com Private WebSocket.")

            await self._sleep(1.0)  # Sleep for 1 second before sending the requests, recommended by the exchange.

            # authenticate the websocket connection
            payload = self._connector.generate_crypto_com_request(method=CONSTANTS.WS_AUTHENTICATE, params={})
            auth_payload = self._auth.add_auth_to_params(params=payload)

            auth_request: WSJSONRequest = WSJSONRequest(payload=auth_payload)
            await ws.send(auth_request)
            self.logger().info("Authenticated the Cryto.com Private WebSocket connection.")

            return ws
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred connecting and authenticating to Crypto.com Private WebSocket...")
            raise

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the user balance, order and trade events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            channels = [CONSTANTS.WS_USER_BALANCE_CHANNEL]
            for trading_pair in self._trading_pairs:
                instrument_name = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                channels.append(f"{CONSTANTS.WS_USER_ORDER_CHANNEL}.{instrument_name}")
                channels.append(f"{CONSTANTS.WS_USER_TRADE_CHANNEL}.{instrument_name}")

            params = {
                "channels": channels
            }
            payload = self._connector.generate_crypto_com_request(method=CONSTANTS.WS_SUBSCRIBE, params=params)
            user_subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await websocket_assistant.send(user_subscribe_request)
            self.logger().info("Subscribed to Crypto.com private channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to Crypto.com private channels...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data

            if data is not None:    # data will be None when the websocket is disconnected
                # deal with heartbeat messages
                if data.get("method", "") == CONSTANTS.WS_PING:
                    # respond to the heartbeat message
                    pong = {
                        "id": data.get("id"),
                        "method": CONSTANTS.WS_PONG,
                    }

                    respond_heartbeat: WSJSONRequest = WSJSONRequest(payload=pong)
                    await websocket_assistant.send(respond_heartbeat)

                    continue

                await self._process_event_message(event_message=data, queue=queue)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)
