import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.kalqix import kalqix_constants as CONSTANTS, kalqix_web_utils as web_utils
from hummingbot.connector.exchange.kalqix.kalqix_api_user_stream_data_source import (
    EVENT_ORDER_UPDATE,
    EVENT_TRADE,
    KalqixAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.kalqix.kalqix_exchange import KalqixExchange


class KalqixAPIUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):

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
        self.connector = KalqixExchange(
            kalqix_api_key="testKey",
            kalqix_api_secret="testSecret",
            kalqix_agent_index=6,
            kalqix_agent_private_key="0" * 63 + "1",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.connector._set_trading_pair_symbol_map(bidict({self.exchange_ticker_body: self.trading_pair}))
        self.data_source = KalqixAPIUserStreamDataSource(
            auth=self.connector._auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

    def _orders_regex_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL, domain=self.domain)
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    def _user_trades_regex_url(self):
        url = web_utils.rest_url(CONSTANTS.USER_TRADES_PATH_URL, domain=self.domain)
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    @aioresponses()
    async def test_poll_open_orders_emits_order_update_events(self, mock_api):
        # Single short page (< ORDERS_MAX_PAGE_SIZE) ends paging after one request.
        order_doc = {"order_id": "srv-1", "client_order_id": "cid-1",
                     "status": "PENDING", "remaining_quantity": "1"}
        mock_api.get(self._orders_regex_url(), body=json.dumps({"data": [order_doc]}))
        output = asyncio.Queue()

        await self.data_source._poll_open_orders(output)

        event = output.get_nowait()
        self.assertTrue(output.empty())
        self.assertEqual(EVENT_ORDER_UPDATE, event["event_type"])
        self.assertEqual(order_doc, event["order"])

    @aioresponses()
    async def test_poll_user_trades_cold_start_primes_cursor_without_emitting(self, mock_api):
        trades = {"data": [
            {"trade_id": "t1", "price_formatted": "100", "quantity_formatted": "1",
             "timestamp": 1000, "fee_formatted": "0.1"},
            {"trade_id": "t2", "price_formatted": "101", "quantity_formatted": "2",
             "timestamp": 2000, "fee_formatted": "0.2"},
        ]}
        mock_api.get(self._user_trades_regex_url(), body=json.dumps(trades))
        output = asyncio.Queue()

        await self.data_source._poll_user_trades(output)

        self.assertTrue(output.empty())
        self.assertEqual(2000, self.data_source._last_trade_ts_us[self.trading_pair])

    @aioresponses()
    async def test_poll_user_trades_warm_emits_trade_events_oldest_first(self, mock_api):
        self.data_source._last_trade_ts_us[self.trading_pair] = 1500
        trades = {"data": [
            {"trade_id": "t3", "price_formatted": "103", "quantity_formatted": "3",
             "timestamp": 3000, "fee_formatted": "0.3"},
            {"trade_id": "t2", "price_formatted": "102", "quantity_formatted": "2",
             "timestamp": 2000, "fee_formatted": "0.2"},
            {"trade_id": "t1", "price_formatted": "100", "quantity_formatted": "1",
             "timestamp": 1000, "fee_formatted": "0.1"},
        ]}
        mock_api.get(self._user_trades_regex_url(), body=json.dumps(trades), repeat=True)
        output = asyncio.Queue()

        await self.data_source._poll_user_trades(output)

        first = output.get_nowait()
        second = output.get_nowait()
        self.assertTrue(output.empty())
        self.assertEqual(EVENT_TRADE, first["event_type"])
        self.assertEqual("t2", first["trade"]["trade_id"])
        self.assertEqual("t3", second["trade"]["trade_id"])
        self.assertEqual(3000, self.data_source._last_trade_ts_us[self.trading_pair])

    def test_last_recv_time_reflects_internal_state(self):
        self.assertEqual(0.0, self.data_source.last_recv_time)
        self.data_source._last_recv_time = 123.0
        self.assertEqual(123.0, self.data_source.last_recv_time)
