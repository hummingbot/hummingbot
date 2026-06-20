import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.kalqix import kalqix_constants as CONSTANTS, kalqix_web_utils as web_utils
from hummingbot.connector.exchange.kalqix.kalqix_api_order_book_data_source import KalqixAPIOrderBookDataSource
from hummingbot.connector.exchange.kalqix.kalqix_exchange import KalqixExchange
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class KalqixAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_ticker_path = f"{cls.base_asset}_{cls.quote_asset}"
        cls.exchange_ticker_body = f"{cls.base_asset}/{cls.quote_asset}"
        cls.domain = "com"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.connector = KalqixExchange(
            kalqix_api_key="",
            kalqix_api_secret="",
            kalqix_agent_index=0,
            kalqix_agent_private_key="0" * 63 + "1",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = KalqixAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.connector._set_trading_pair_symbol_map(bidict({self.exchange_ticker_body: self.trading_pair}))

    def handle(self, record):
        self.log_records.append(record)

    def _snapshot_response(self):
        return {
            "BUY": [{"price_formatted": "4.0", "quantity_formatted": "431.0"}],
            "SELL": [{"price_formatted": "4.000002", "quantity_formatted": "12.0"}],
        }

    def _snapshot_regex_url(self):
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_PATH_URL.format(ticker=self.exchange_ticker_path), domain=self.domain
        )
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    def _trades_regex_url(self):
        url = web_utils.rest_url(
            CONSTANTS.TRADES_PATH_URL.format(ticker=self.exchange_ticker_path), domain=self.domain
        )
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    @aioresponses()
    async def test_request_order_book_snapshot_returns_raw_response(self, mock_api):
        mock_api.get(self._snapshot_regex_url(), body=json.dumps(self._snapshot_response()))

        raw = await self.data_source._request_order_book_snapshot(self.trading_pair)

        self.assertEqual(self._snapshot_response(), raw)

    @aioresponses()
    async def test_order_book_snapshot_uses_formatted_prices(self, mock_api):
        mock_api.get(self._snapshot_regex_url(), body=json.dumps(self._snapshot_response()))

        snapshot_message: OrderBookMessage = await self.data_source._order_book_snapshot(self.trading_pair)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(self.trading_pair, snapshot_message.trading_pair)
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)

    @aioresponses()
    async def test_emit_new_trades_cold_start_primes_cursor_without_emitting(self, mock_api):
        trades = {"data": [
            {"trade_id": "t1", "price_formatted": "100", "quantity_formatted": "1",
             "timestamp": 1000, "maker_side": "BUY"},
            {"trade_id": "t2", "price_formatted": "101", "quantity_formatted": "2",
             "timestamp": 2000, "maker_side": "SELL"},
        ]}
        mock_api.get(self._trades_regex_url(), body=json.dumps(trades))
        output = asyncio.Queue()

        await self.data_source._emit_new_trades(self.trading_pair, output)

        self.assertTrue(output.empty())
        # cursor primed to newest seen timestamp
        self.assertEqual(2000, self.data_source._last_trade_ts_us[self.trading_pair])

    @aioresponses()
    async def test_emit_new_trades_warm_emits_only_fresh_oldest_first(self, mock_api):
        # Prime the cursor so this is a warm poll.
        self.data_source._last_trade_ts_us[self.trading_pair] = 1500
        # Descending-by-timestamp page; 3000 and 2000 are fresh, 1000 is old (stops paging).
        trades = {"data": [
            {"trade_id": "t3", "price_formatted": "103", "quantity_formatted": "3",
             "timestamp": 3000, "maker_side": "BUY"},
            {"trade_id": "t2", "price_formatted": "102", "quantity_formatted": "2",
             "timestamp": 2000, "maker_side": "SELL"},
            {"trade_id": "t1", "price_formatted": "100", "quantity_formatted": "1",
             "timestamp": 1000, "maker_side": "BUY"},
        ]}
        mock_api.get(self._trades_regex_url(), body=json.dumps(trades), repeat=True)
        output = asyncio.Queue()

        await self.data_source._emit_new_trades(self.trading_pair, output)

        first = output.get_nowait()
        second = output.get_nowait()
        self.assertTrue(output.empty())
        # oldest-first ordering (microsecond timestamp lives in content["update_id"])
        self.assertEqual(2000, first.content["update_id"])
        self.assertEqual(3000, second.content["update_id"])
        self.assertEqual("t2", first.trade_id)
        self.assertEqual("t3", second.trade_id)
        self.assertEqual(3000, self.data_source._last_trade_ts_us[self.trading_pair])

    async def test_subscribe_and_unsubscribe_are_noops_returning_true(self):
        self.assertTrue(await self.data_source.subscribe_to_trading_pair(self.trading_pair))
        self.assertTrue(await self.data_source.unsubscribe_from_trading_pair(self.trading_pair))

    async def test_get_last_traded_prices_delegates_to_connector(self):
        with patch.object(
            self.connector, "get_last_traded_prices", new=AsyncMock(return_value={self.trading_pair: 10.0})
        ) as delegate:
            result = await self.data_source.get_last_traded_prices([self.trading_pair])
        delegate.assert_awaited_once()
        self.assertEqual({self.trading_pair: 10.0}, result)
