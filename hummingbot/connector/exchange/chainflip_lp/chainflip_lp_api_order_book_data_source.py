import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
<<<<<<< HEAD
<<<<<<< HEAD
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLpDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
=======
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLPDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLpDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
>>>>>>> cb0a3d276 ((refactor) implement review changes)
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange


class ChainflipLpAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: "ChainflipLpExchange",
<<<<<<< HEAD
<<<<<<< HEAD
        data_source: "ChainflipLpDataSource",
=======
        data_source: "ChainflipLPDataSource",
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        data_source: "ChainflipLpDataSource",
>>>>>>> cb0a3d276 ((refactor) implement review changes)
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._connector = connector
        self._data_source = data_source
        self._domain = domain
        # self._forwarders = []
        # self._configure_event_forwarders()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._data_source.order_book_snapshot(trading_pair=trading_pair)
        return snapshot

    async def listen_for_subscriptions(self):
        # no supported subscription available to listen to in chainflip lp
<<<<<<< HEAD
        pass
=======
        raise NotImplementedError
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _connected_websocket_assistant(self) -> WSAssistant:
<<<<<<< HEAD
<<<<<<< HEAD
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to the trades and order diffs
        """
        # subscriptions to trades and order diffs does not exist in chainflip lp
        pass
=======
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_RPC_URLS[self._domain], ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws
=======
        pass
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to the trades and order diffs
        """
        # subscriptions to trades and order diffs does not exist in chainflip lp
<<<<<<< HEAD
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return ""
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        raise NotImplementedError
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
