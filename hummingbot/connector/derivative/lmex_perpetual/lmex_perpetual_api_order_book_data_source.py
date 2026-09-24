import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_derivative import LmexPerpetualDerivative


class LmexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    REST-polling order book data source for LMEX Perpetual.

    LMEX does not expose a public WebSocket feed, so we rely entirely on
    periodic REST snapshots.  ``listen_for_subscriptions`` is left as a no-op
    infinite loop; the framework drives snapshots via
    ``listen_for_order_book_snapshots`` which calls ``_order_book_snapshot``.
    """

    POLL_INTERVAL = 1.0  # seconds between snapshot refreshes

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LmexPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    # ------------------------------------------------------------------
    # Required abstract method
    # ------------------------------------------------------------------

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    # ------------------------------------------------------------------
    # Funding info
    # ------------------------------------------------------------------

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Retrieves the latest funding info for *trading_pair* via REST.
        LMEX returns funding rate in market_summary; we derive next funding
        timestamp from the current time and the funding interval.
        """
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                endpoint=CONSTANTS.MARKET_SUMMARY_PATH_URL, domain=self._domain
            ),
            params={"symbol": ex_symbol},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKET_SUMMARY_PATH_URL,
        )

        # Response is a list of market summaries; find our symbol
        summary = self._find_symbol_summary(response, ex_symbol)

        funding_rate = Decimal(str(summary.get("fundingRate", "0")))
        funding_interval_minutes = int(summary.get("fundingIntervalMinutes", 480))
        mark_price = Decimal(str(summary.get("last", "0")))

        # Estimate next funding timestamp
        now = time.time()
        interval_seconds = funding_interval_minutes * 60
        next_funding_ts = int(now) + interval_seconds - (int(now) % interval_seconds)

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=mark_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding_ts,
            rate=funding_rate,
        )

    # ------------------------------------------------------------------
    # Order book snapshot (drives the framework's snapshot listener)
    # ------------------------------------------------------------------

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = float(snapshot_response.get("timestamp", time.time() * 1000)) * 1e-3

        bids = [
            [entry["price"], entry["size"]]
            for entry in snapshot_response.get("buyQuote", [])
        ]
        asks = [
            [entry["price"], entry["size"]]
            for entry in snapshot_response.get("sellQuote", [])
        ]

        snapshot_msg = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(snapshot_response.get("timestamp", time.time() * 1000)),
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                endpoint=CONSTANTS.ORDER_BOOK_PATH_URL, domain=self._domain
            ),
            params={"symbol": ex_symbol, "depth": 50},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )

    # ------------------------------------------------------------------
    # Websocket overrides — LMEX has no public WS; we do REST polling only.
    # The framework's listen_for_order_book_snapshots already uses _order_book_snapshot.
    # We override listen_for_subscriptions to be a harmless no-op so the
    # framework doesn't crash trying to connect to a WS URL.
    # ------------------------------------------------------------------

    async def listen_for_subscriptions(self):
        """No-op: LMEX Futures has no public WebSocket order book feed."""
        while True:
            await self._sleep(3600.0)

    async def _connected_websocket_assistant(self) -> WSAssistant:  # type: ignore[override]
        raise NotImplementedError("LMEX Perpetual does not support WebSocket order book streaming.")

    async def _subscribe_channels(self, ws: WSAssistant):
        raise NotImplementedError("LMEX Perpetual does not support WebSocket order book streaming.")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return ""

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_symbol_summary(response: Any, symbol: str) -> Dict[str, Any]:
        """
        market_summary returns a list; find the entry matching *symbol*.
        Falls back to first item if not found.
        """
        if isinstance(response, list):
            for item in response:
                if item.get("symbol") == symbol:
                    return item
            return response[0] if response else {}
        return response

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    def _time(self) -> float:
        return time.time()
