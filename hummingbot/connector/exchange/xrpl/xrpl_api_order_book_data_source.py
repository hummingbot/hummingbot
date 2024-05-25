import asyncio

# import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# XRPL imports
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import BookOffers

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS

# from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage

# from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource

# from hummingbot.core.utils.async_utils import safe_gather
# from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XrplAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'XrplExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory

    # FIXME: Implement the following methods
    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    # FIXME: Implement the following methods
    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        # Create a client to connect to the test network
        client: JsonRpcClient = self._connector.client
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)

        try:
            orderbook_asks_info = client.request(
                BookOffers(
                    ledger_index="current",
                    taker_gets=base_currency,
                    taker_pays=quote_currency,
                    limit=CONSTANTS.ORDER_BOOK_DEPTH,
                )
            )

            orderbook_bids_info = client.request(
                BookOffers(
                    ledger_index="current",
                    taker_gets=quote_currency,
                    taker_pays=base_currency,
                    limit=CONSTANTS.ORDER_BOOK_DEPTH,
                )
            )

            asks = orderbook_asks_info.result.get("offers", [])
            bids = orderbook_bids_info.result.get("offers", [])

            order_book = {
                "asks": asks,
                "bids": bids,
            }
        except Exception as e:
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}: {e}")
            return {}

        return order_book

    async def _subscribe_channels(self, ws: WSAssistant):
        pass

    # FIXME: Implement the following methods
    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass

    # FIXME: Implement the following methods
    async def _connected_websocket_assistant_for_pair(self, trading_pair: str) -> WSAssistant:
        pass

    # FIXME: Implement the following methods
    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        pass

    # FIXME: Implement the following methods
    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    # FIXME: Implement the following methods
    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    # FIXME: Implement the following methods
    async def _process_websocket_messages_for_pair(self, websocket_assistant: WSAssistant, trading_pair: str):
        pass

    # FIXME: Implement the following methods
    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        pass
