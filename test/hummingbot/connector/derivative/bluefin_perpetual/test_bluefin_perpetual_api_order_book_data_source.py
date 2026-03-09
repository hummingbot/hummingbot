import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_api_order_book_data_source import (
    BluefinPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.funding_info import FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BluefinPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = "BTC-USD"

    def setUp(self) -> None:
        super().setUp()

        self.connector = MagicMock()
        self.data_source = MagicMock()

        def _from_e9(e9: Any) -> Decimal:
            return Decimal(str(e9)) / Decimal("1e9")

        def _to_hb_symbol(symbol: Any) -> str:
            return "BTC-USD" if symbol == "BTC-PERP" else str(symbol)

        self.data_source.from_e9.side_effect = _from_e9
        self.data_source.bluefin_to_hb_symbol.side_effect = _to_hb_symbol
        self.data_source.get_market_ticker = AsyncMock(
            return_value=SimpleNamespace(last_trade_price_e9="101250000000")
        )

        self.order_book_source = BluefinPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.data_source,
        )

    async def test_get_last_traded_prices_fetches_from_ticker(self):
        prices = await self.order_book_source.get_last_traded_prices([self.trading_pair])

        self.assertEqual({"BTC-USD": 101.25}, prices)
        self.data_source.get_market_ticker.assert_awaited_once_with("BTC-USD")

    async def test_listen_for_order_book_diffs_forwards_diff_message(self):
        output: asyncio.Queue[Any] = asyncio.Queue()
        diff_event = type(
            "OrderbookDiffDepthUpdate",
            (),
            {
                "symbol": "BTC-PERP",
                "bids_e9": [["100000000000", "2000000000"]],
                "asks_e9": [["101000000000", "3000000000"]],
                "last_update_id": 123,
                "updated_at_millis": 1000,
            },
        )()

        self.data_source.get_market_order_book_event = AsyncMock(side_effect=[diff_event, asyncio.CancelledError()])

        with self.assertRaises(asyncio.CancelledError):
            await self.order_book_source.listen_for_order_book_diffs(self.local_event_loop, output)

        message = output.get_nowait()
        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual("BTC-USD", message.content["trading_pair"])

    async def test_listen_for_funding_info_emits_funding_update(self):
        output: asyncio.Queue[Any] = asyncio.Queue()
        funding_event = type(
            "OraclePriceUpdate",
            (),
            {
                "symbol": "BTC-PERP",
                "oracle_price_e9": "99900000000",
                "mark_price_e9": "100100000000",
            },
        )()

        self.data_source.get_market_funding_event = AsyncMock(side_effect=[funding_event, asyncio.CancelledError()])

        with self.assertRaises(asyncio.CancelledError):
            await self.order_book_source.listen_for_funding_info(output)

        update = output.get_nowait()
        self.assertIsInstance(update, FundingInfoUpdate)
        self.assertEqual("BTC-USD", update.trading_pair)
