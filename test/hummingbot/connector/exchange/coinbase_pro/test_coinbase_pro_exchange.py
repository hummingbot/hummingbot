import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, List

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_exchange import CoinbaseProExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderType,
    SellOrderCreatedEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class TestCoinbaseProExchange(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret = "shht"
        cls.api_passphrase = "somePhrase"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []

        self.exchange = CoinbaseProExchange(
            self.api_key, self.api_secret, self.api_passphrase, trading_pairs=[self.trading_pair]
        )
        self.event_listener = EventLogger()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_trading_rules_initialization(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}"
        alt_pair = "BTC-USDT"
        resp = self.get_products_response_mock(alt_pair)
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

    def simulate_execute_buy_order(self, mock_api, order_id):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_orders_response_mock(order_id)
        mock_api.post(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            )
        )

    def get_account_mock(
        self, base_balance: float, base_available: float, quote_balance: float, quote_available: float
    ) -> List:
        account_mock = [
            {
                "id": "7fd0abc0-e5ad-4cbb-8d54-f2b3f43364da",
                "currency": self.base_asset,
                "balance": str(base_balance),
                "available": str(base_available),
                "hold": "0.0000000000000000",
                "profile_id": "8058d771-2d88-4f0f-ab6e-299c153d4308",
                "trading_enabled": True
            },
            {
                "id": "7fd0abc0-e5ad-4cbb-8d54-f2b3f43364da",
                "currency": self.quote_asset,
                "balance": str(quote_balance),
                "available": str(quote_available),
                "hold": "0.0000000000000000",
                "profile_id": "8058d771-2d88-4f0f-ab6e-299c153d4308",
                "trading_enabled": True
            }
        ]
        return account_mock

    def get_products_response_mock(self, other_pair: str) -> List:
        products_mock = [
            {
                "id": self.trading_pair,
                "base_currency": self.base_asset,
                "quote_currency": self.quote_asset,
                "base_min_size": "0.00100000",
                "base_max_size": "280.00000000",
                "quote_increment": "0.01000000",
                "base_increment": "0.00000001",
                "display_name": f"{self.base_asset}/{self.quote_asset}",
                "min_market_funds": "10",
                "max_market_funds": "1000000",
                "margin_enabled": False,
                "post_only": False,
                "limit_only": False,
                "cancel_only": False,
                "status": "online",
                "status_message": "",
                "auction_mode": True,
            },
            {
                "id": other_pair,
                "base_currency": other_pair.split("-")[0],
                "quote_currency": other_pair.split("-")[1],
                "base_min_size": "0.00100000",
                "base_max_size": "280.00000000",
                "quote_increment": "0.01000000",
                "base_increment": "0.00000001",
                "display_name": other_pair.replace("-", "/"),
                "min_market_funds": "10",
                "max_market_funds": "1000000",
                "margin_enabled": False,
                "post_only": False,
                "limit_only": False,
                "cancel_only": False,
                "status": "online",
                "status_message": "",
                "auction_mode": True,
            }
        ]
        return products_mock

    def get_orders_response_mock(self, order_id: str) -> Dict:
        orders_mock = {
            "id": order_id,
            "price": "10.00000000",
            "size": "1.00000000",
            "product_id": self.trading_pair,
            "profile_id": "8058d771-2d88-4f0f-ab6e-299c153d4308",
            "side": "buy",
            "type": "limit",
            "time_in_force": "GTC",
            "post_only": True,
            "created_at": "2020-03-11T20:48:46.622052Z",
            "fill_fees": "0.0000000000000000",
            "filled_size": "0.00000000",
            "executed_value": "0.0000000000000000",
            "status": "open",
            "settled": False
        }
        return orders_mock

    @aioresponses()
    def test_check_network_not_connected(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.TIME_PATH_URL}"
        resp = ""
        mock_api.get(url, status=500, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.TIME_PATH_URL}"
        resp = {}
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_update_fee_percentage(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.FEES_PATH_URL}"
        resp = {
            "maker_fee_rate": "0.0050",
            "taker_fee_rate": "0.0050",
            "usd_volume": "43806.92"
        }
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_fee_percentage())

        self.assertEqual(Decimal(resp["maker_fee_rate"]), self.exchange.maker_fee_percentage)
        self.assertEqual(Decimal(resp["taker_fee_rate"]), self.exchange.taker_fee_percentage)

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ACCOUNTS_PATH_URL}"
        resp = self.get_account_mock(
            base_balance=2,
            base_available=1,
            quote_balance=4,
            quote_available=3,
        )
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        expected_available_balances = {self.base_asset: Decimal("1"), self.quote_asset: Decimal("3")}
        self.assertEqual(expected_available_balances, self.exchange.available_balances)
        expected_balances = {self.base_asset: Decimal("2"), self.quote_asset: Decimal("4")}
        self.assertEqual(expected_balances, self.exchange.get_all_balances())

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}"
        alt_pair = "BTC-USDT"
        resp = self.get_products_response_mock(alt_pair)
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rules = self.exchange.trading_rules

        self.assertEqual(2, len(trading_rules))
        self.assertIn(self.trading_pair, trading_rules)
        self.assertIn(alt_pair, trading_rules)
        self.assertIsInstance(trading_rules[self.trading_pair], TradingRule)
        self.assertIsInstance(trading_rules[alt_pair], TradingRule)

    @aioresponses()
    def test_execute_buy(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)

        some_order_id = "someID"
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_orders_response_mock(some_order_id)
        mock_api.post(regex_url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)
        self.exchange.add_listener(MarketEvent.OrderFilled, self.event_listener)

        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id=some_order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            )
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, BuyOrderCreatedEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_buy_handles_errors(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)

        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, exception=RuntimeError)

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)
        self.exchange.add_listener(MarketEvent.OrderFailure, self.event_listener)

        some_order_id = "someID"
        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id=some_order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            )
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, MarketOrderFailureEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertNotIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_sell(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)

        some_order_id = "someID"
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_orders_response_mock(some_order_id)
        mock_api.post(regex_url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.SellOrderCreated, self.event_listener)
        self.exchange.add_listener(MarketEvent.OrderFilled, self.event_listener)

        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id=some_order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            )
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, SellOrderCreatedEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_sell_handles_errors(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)

        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, exception=RuntimeError)

        self.exchange.add_listener(MarketEvent.SellOrderCreated, self.event_listener)
        self.exchange.add_listener(MarketEvent.OrderFailure, self.event_listener)

        some_order_id = "someID"
        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id=some_order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            )
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, MarketOrderFailureEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertNotIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)
        some_order_id = "someID"
        self.simulate_execute_buy_order(mock_api, some_order_id)

        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}/{some_order_id}"
        resp = some_order_id
        mock_api.delete(url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.OrderCancelled, self.event_listener)

        self.async_run_with_timeout(self.exchange.execute_cancel(self.trading_pair, some_order_id))

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, OrderCancelledEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertNotIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel_order_does_not_exist(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)
        some_order_id = "someID"
        self.simulate_execute_buy_order(mock_api, some_order_id)

        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}/{some_order_id}"
        mock_api.delete(url, exception=IOError("order not found"))

        self.exchange.add_listener(MarketEvent.OrderCancelled, self.event_listener)

        self.async_run_with_timeout(self.exchange.execute_cancel(self.trading_pair, some_order_id))

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertIsInstance(event, OrderCancelledEvent)
        self.assertEqual(some_order_id, event.order_id)
        self.assertNotIn(some_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_get_order(self, mock_api):
        self.simulate_trading_rules_initialization(mock_api)
        some_order_id = "someID"
        self.simulate_execute_buy_order(mock_api, some_order_id)

        url = f"{CONSTANTS.REST_URL}{CONSTANTS.ORDERS_PATH_URL}/{some_order_id}"
        resp = self.get_orders_response_mock(some_order_id)
        mock_api.get(url, body=json.dumps(resp))
