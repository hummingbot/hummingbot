from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_ws_parser import build_ws_subscribe_request
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
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
        self._ws: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger.logger_name_for_class(cls)
        return cls._logger

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbol": ex_symbol, "limit": 1000}
        return await self._connector._api_get(CONSTANTS.ORDER_BOOK_SNAPSHOT_URL, params=params)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        ts = (snapshot.get("E") or snapshot.get("timestamp") or int(time.time() * 1e3)) / 1e3
        content = {
            "trading_pair": trading_pair,
            "update_id": snapshot.get("lastUpdateId", int(ts * 1e3)),
            "bids": snapshot.get("bids", []),
            "asks": snapshot.get("asks", []),
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, ts)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # TODO: connect to hb trade messages
        return

    async def _parse_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # TODO: connect to hb diff messages
        return

    async def listen_for_subscriptions(self):
        # Best-effort public ws subscription loop
        while True:
            try:
                self._ws = await self._api_factory.get_ws_assistant()
                await self._ws.connect(ws_url=self._connector.web_utils.public_ws_url(self._domain), ping_timeout=30)

                streams: List[str] = []
                for trading_pair in self._trading_pairs:
                    ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                    streams.append(f"{ex_symbol.lower()}@trade")
                    streams.append(f"{ex_symbol.lower()}@depth@100ms")

                subscribe_payload = build_ws_subscribe_request(streams)
                await self._ws.send(subscribe_payload)

                while True:
                    msg = await self._ws.receive()
                    if msg is None:
                        continue
                    # Messages are handled by base class listen_for_order_book_diffs/trades in the full connector.
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in public order book listener. Retrying...")
                await asyncio.sleep(5)
