import asyncio
import json
from decimal import Decimal
from functools import partial
from typing import Awaitable
from unittest import TestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_exchange import CoinzoomExchange
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.connector.trading_rule import TradingRule

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import TradeType, OrderType


class CoinzoomExchangeTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "testKey"
        cls.api_secret_key = "testSecretKey"
        cls.username = "testUsername"

    def setUp(self) -> None:
        super().setUp()
        self.exchange = CoinzoomExchange(
            coinzoom_api_key=self.api_key,
            coinzoom_secret_key=self.api_secret_key,
            coinzoom_username=self.username,
            trading_pairs=[self.trading_pair]
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _register_sent_request(requests_list, url, **kwargs):
        requests_list.append((url, kwargs))

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        resp = {}
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancelled_error(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        mock_api.get(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(coroutine=self.exchange.check_network())

    @aioresponses()
    def test_check_network_not_connected_for_error_status(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        resp = {}
        mock_api.get(url, status=405, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['SYMBOL']}"
        resp = [{
            "symbol": "ETH/USDT",
            "baseCurrencyCode": "ETH",
            "termCurrencyCode": "USDT",
            "minTradeAmt": 0.001,
            "maxTradeAmt": 400,
            "maxPricePrecision": 2,
            "maxQuantityPrecision": 5,
            "issueOnly": False
        }, {
            "symbol": "BTC/USDT",
            "baseCurrencyCode": "BTC",
            "termCurrencyCode": "USDT",
            "minTradeAmt": 0.0001,
            "maxTradeAmt": 30,
            "maxPricePrecision": 2,
            "maxQuantityPrecision": 6,
            "issueOnly": False
        }]
        mock_api.get(url, status=200, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertIn("BTC-USDT", self.exchange.trading_rules)
        self.assertIn("ETH-USDT", self.exchange.trading_rules)

        rule = self.exchange.trading_rules["BTC-USDT"]
        self.assertEqual(Decimal("0.0001"), rule.min_order_size)
        self.assertEqual(Decimal(30), rule.max_order_size)
        self.assertEqual(Decimal("1e-2"), rule.min_price_increment)
        self.assertEqual(Decimal("0.0001"), rule.min_base_amount_increment)
        self.assertEqual(Decimal(2), rule.max_price_significant_digits)

    @aioresponses()
    def test_create_order(self, mock_api):
        sent_messages = []
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_CREATE']}"
        resp = "Exchange-OID-1"
        mock_api.post(url, body=json.dumps(resp), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="OID-1",
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(1000)
        ))

        self.assertTrue(resp, self.exchange.in_flight_orders["OID-1"].exchange_order_id)

        sent_message = json.loads(sent_messages[0][1]["data"])
        self.assertEqual(f"{self.base_asset}/{self.quote_asset}", sent_message["symbol"])
        self.assertEqual(OrderType.LIMIT.name, sent_message["orderType"])
        self.assertEqual(TradeType.BUY.name, sent_message["orderSide"])
        self.assertEqual(Decimal(1), Decimal(sent_message["quantity"]))
        self.assertEqual(Decimal(1000), Decimal(sent_message["price"]))
        self.assertEqual(Constants.HBOT_BROKER_ID, sent_message["originType"])
        self.assertEqual("true", sent_message["payFeesWithZoomToken"])

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        sent_messages = []
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE']}"
        resp = {}
        mock_api.post(url, body=json.dumps(resp), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.exchange.start_tracking_order(
            order_id="OID-1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(50000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
        )
        self.exchange.in_flight_orders["OID-1"].update_exchange_order_id("E-OID-1")

        result: CancellationResult = self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, "OID-1"))

        self.assertEqual("OID-1", result.order_id)
        self.assertTrue(result.success)
        self.assertNotIn("OID-1", self.exchange.in_flight_orders)

        sent_message = json.loads(sent_messages[0][1]["data"])
        self.assertEqual("E-OID-1", sent_message["orderId"])
        self.assertEqual(f"{self.base_asset}/{self.quote_asset}", sent_message["symbol"])

    @aioresponses()
    def test_execute_cancel_ignores_local_orders(self, mock_api):
        sent_messages = []
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE']}"
        # To ensure the request is not sent we associate an exception to it
        mock_api.post(url, exception=Exception(), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.exchange.start_tracking_order(
            order_id="OID-1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(50000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
        )

        result: CancellationResult = self.async_run_with_timeout(
            self.exchange._execute_cancel(self.trading_pair, "OID-1"))

        self.assertEqual("OID-1", result.order_id)
        self.assertFalse(result.success)
        self.assertIn("OID-1", self.exchange.in_flight_orders)
        self.assertEqual(0, len(sent_messages))
