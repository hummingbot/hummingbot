import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.clob.clob_order_book import CLOBOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class CLOBAPIOrderBookDataSource(OrderBookTrackerDataSource):

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        tickers: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_tickers(
            chain="",  # TODO fix!!!
            network="",  # TODO fix!!!
            connector="",  # TODO fix!!!
            market_names=trading_pairs
        )

        return tickers

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_order_books(
            chain="",  # TODO fix!!!
            network="",  # TODO fix!!!
            connector="",  # TODO fix!!!
            market_name=trading_pair
        )

        snapshot_timestamp: float = time.time()

        snapshot_msg: OrderBookMessage = CLOBOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )

        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    async def _subscribe_channels(self, ws: WSAssistant):
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        # TODO do we need to override this method?!!!
        raise NotImplementedError
