import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.okex import constants as CONSTANTS, okex_web_utils as web_utils
from hummingbot.connector.exchange.okex.okex_exchange import OkexExchange
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderType, MarketEvent


class TestOKExExchange(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = OkexExchange(
            self.api_key, self.api_secret_key, self.api_passphrase, trading_pairs=[self.trading_pair]
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        # self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        # self.exchange._time_synchronizer.logger().setLevel(1)
        # self.exchange._time_synchronizer.logger().addHandler(self)
        # self.exchange._order_tracker.logger().setLevel(1)
        # self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.utils.get_tracking_nonce_low_res")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 9

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        url = web_utils.rest_url(path_url=CONSTANTS.OKEX_INSTRUMENTS_PATH)
        url = url + "?instType=SPOT"

        mock_response: Dict[str, Any] = {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "BTC",
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": "BTC-USDT",
                    "instType": "SPOT",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.00000001",
                    "minSz": "0.00001",
                    "optType": "",
                    "quoteCcy": "USDT",
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.1",
                    "uly": ""
                },
                {
                    "alias": "",
                    "baseCcy": "ETH",
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": "ETH-USDT",
                    "instType": "SPOT",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.000001",
                    "minSz": "0.001",
                    "optType": "",
                    "quoteCcy": "USDT",
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.01",
                    "uly": ""
                },
                {
                    "alias": "",
                    "baseCcy": "OKB",
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": "OKB-USDT",
                    "instType": "OPTION",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.000001",
                    "minSz": "0.1",
                    "optType": "",
                    "quoteCcy": "USDT",
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.001",
                    "uly": ""
                },
            ]
        }

        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str] = self.async_run_with_timeout(
            self.exchange.all_trading_pairs()
        )

        self.assertEqual(2, len(result))
        self.assertIn("BTC-USDT", result)
        self.assertIn("ETH-USDT", result)
        self.assertNotIn("OKB-USDT", result)

    @aioresponses()
    def test_fetch_trading_pairs_exception_raised(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = web_utils.rest_url(path_url=CONSTANTS.OKEX_INSTRUMENTS_PATH)
        url = url + "?instType=SPOT"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(
            self.exchange.all_trading_pairs()
        )

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.OKEX_TICKER_PATH)
        url = f"{url}?instId={self.base_asset}-{self.quote_asset}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.trading_pair,
                    "last": "9999.99",
                    "lastSz": "0.1",
                    "askPx": "9999.99",
                    "askSz": "11",
                    "bidPx": "8888.88",
                    "bidSz": "5",
                    "open24h": "9000",
                    "high24h": "10000",
                    "low24h": "8888.88",
                    "volCcy24h": "2222",
                    "vol24h": "2222",
                    "sodUtc0": "2222",
                    "sodUtc8": "2222",
                    "ts": "1597026383085"
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(result))
        self.assertEqual(9999.99, result[self.trading_pair])
