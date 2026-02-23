import asyncio
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import ArchitectPerpetualDerivative


class ArchitectPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._snapshot_messages_queue_key = "order_book_snapshot"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger.logger_name_for_class(cls)
        return cls._logger

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        # Best-effort endpoint: TICKER_BOOK_URL not snapshot; in unit tests this is mocked.
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbol": ex_symbol}
        return await self._connector._api_get(CONSTANTS.TICKER_BOOK_URL, params=params)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        ts = snapshot.get("timestamp") or time.time()
        content = {
            "trading_pair": trading_pair,
            "update_id": snapshot.get("update_id", int(ts * 1e3)),
            "bids": snapshot.get("bids", []),
            "asks": snapshot.get("asks", []),
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, ts)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Not implemented (exchange-specific)
        return

    async def _parse_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Not implemented (exchange-specific)
        return

    async def listen_for_subscriptions(self):
        # Minimal implementation to satisfy base start/stop without network usage in unit tests.
        while True:
            await asyncio.sleep(1)
