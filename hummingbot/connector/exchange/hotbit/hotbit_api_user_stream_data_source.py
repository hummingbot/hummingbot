import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.hotbit import hotbit_constants as CONSTANTS
from hummingbot.connector.exchange.hotbit.hotbit_auth import HotbitAuth
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.hotbit.hotbit_exchange import HotbitExchange


class HotbitAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: HotbitAuth,
                 trading_pairs: List[str],
                 connector: 'HotbitExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: HotbitAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs
        self._connector = connector

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        sign = self._auth.sign(params={})
        payload = {
            "method": "server.auth",
            "params": [self._auth.api_key, sign],
            "id": 1
        }
        auth_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await ws.send(auth_request)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events, balance events and account events

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            order_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                order_params.append(f"{symbol.upper()}")
            order_payload = {
                "method": "order.subscribe",
                "params": order_params,
                "id": 1
            }
            subscribe_order_request: WSJSONRequest = WSJSONRequest(payload=order_payload)
            await websocket_assistant.send(subscribe_order_request)

            symbols = set()
            for trading_pair in self._trading_pairs:
                base, quote = split_hb_trading_pair(trading_pair)
                symbols.add(base)
                symbols.add(quote)
            asset_payload = {
                "method": "asset.subscribe",
                "params": sorted(list(symbols)),
                "id": 1
            }
            subscribe_asset_request: WSJSONRequest = WSJSONRequest(payload=asset_payload)
            await websocket_assistant.send(subscribe_asset_request)

            self.logger().info("Subscribed to private user order and asset channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private user streams...",
                exc_info=True
            )
            raise
