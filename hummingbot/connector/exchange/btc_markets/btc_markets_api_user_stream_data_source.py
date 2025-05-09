import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.exchange.btc_markets.btc_markets_constants as CONSTANTS
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.btc_markets.btc_markets_exchange import BtcMarketsExchange


class BtcMarketsAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BtcMarketsAuth,
        trading_pairs: List[str],
        connector: 'BtcMarketsExchange',
        api_factory: WebAssistantsFactory
    ):
        super().__init__()
        self._auth: BtcMarketsAuth = auth
        self._domain = CONSTANTS.DEFAULT_DOMAIN
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange

        :return: an instance of WSAssistant connected to the exchange
        """
        print("Connecting ...")
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()

        await self._ws_assistant.connect(
            ws_url=CONSTANTS.WSS_PRIVATE_URL[self._domain],
            ping_timeout=CONSTANTS.WS_PING_TIMEOUT)

        return self._ws_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            marketIds = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                marketIds.append(symbol)

            payload = self._auth.generate_ws_authentication_message()
            payload["channels"] = [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.FUND_CHANGE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
            payload["marketIds"] = marketIds

            subscribe_request: WSJSONRequest = WSJSONRequest(payload)

            async with self._api_factory.throttler.execute_task(limit_id = CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private account and orders channels...")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to private account and orders channels ...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data

            messageType = data.get("messageType")
            if messageType == "error":
                code = data.get("code")
                msg = data.get("message")
                raise ValueError(f"Error message ({code}: {msg}) received in the user stream data source: {data}")

            if messageType in [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.FUND_CHANGE_EVENT_TYPE]:
                queue.put_nowait(data)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
