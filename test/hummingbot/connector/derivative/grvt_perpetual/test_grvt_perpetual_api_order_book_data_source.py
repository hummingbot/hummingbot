import asyncio
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from bidict import bidict

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)


class GrvtPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC_USDT_Perp")
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDT")
        self.connector._api_post = AsyncMock(return_value={
            "result": {
                "event_time": "1700000000000000000",
                "instrument": "BTC_USDT_Perp",
                "bids": [{"price": "62000", "size": "1.2"}],
                "asks": [{"price": "62010", "size": "1.5"}],
                "index_price": "61990",
                "mark_price": "62005",
                "funding_rate_8h_curr": "0.0001",
                "next_funding_time": "1700006400000000000",
            }
        })
        self.connector._trading_pair_symbol_map = bidict({"BTC_USDT_Perp": "BTC-USDT"})
        self.api_factory = MagicMock()
        self.data_source = GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-USDT"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_get_funding_info(self):
        funding_info = await self.data_source.get_funding_info("BTC-USDT")
        self.assertEqual("BTC-USDT", funding_info.trading_pair)
        self.assertEqual(Decimal("61990"), funding_info.index_price)
        self.assertEqual(Decimal("62005"), funding_info.mark_price)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)
        self.assertEqual(1700006400, funding_info.next_funding_utc_timestamp)

    async def test_parse_funding_info_message(self):
        output = asyncio.Queue()
        await self.data_source._parse_funding_info_message(
            {
                "stream": "v1.ticker.s",
                "feed": {
                    "instrument": "BTC_USDT_Perp",
                    "index_price": "61990",
                    "mark_price": "62005",
                    "funding_rate_8h_curr": "0.0001",
                    "next_funding_time": "1700006400000000000",
                },
            },
            output,
        )
        update = output.get_nowait()
        self.assertEqual("BTC-USDT", update.trading_pair)
        self.assertEqual(Decimal("0.0001"), update.rate)
        self.assertEqual(1700006400, update.next_funding_utc_timestamp)
