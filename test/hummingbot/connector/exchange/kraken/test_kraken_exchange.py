import asyncio
import json
import re
import unittest
from decimal import Decimal
from functools import partial
from typing import Awaitable, Dict

from aioresponses import aioresponses
from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange

from hummingbot.connector.exchange.kraken.kraken_in_flight_order import KrakenInFlightOrderNotCreated
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS
from hummingbot.core.clock import Clock, ClockMode

from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    TradeType,
    OrderType,
    MarketEvent,
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class KrakenExchangeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.event_listener = EventLogger()
        not_a_real_secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="
        self.exchange = KrakenExchange(
            kraken_api_key="someKey",
            kraken_secret_key=not_a_real_secret,
            trading_pairs=[self.trading_pair],
        )
        self.start_time = 1
        self.clock = Clock(clock_mode=ClockMode.BACKTEST, start_time=self.start_time)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_trading_rules_initialized(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ASSET_PAIRS_PATH_URL}"
        resp = self.get_asset_pairs_mock()
        mocked_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_trading_rules(), timeout=2)

    @staticmethod
    def register_sent_request(requests_list, url, **kwargs):
        requests_list.append((url, kwargs))

    def get_asset_pairs_mock(self) -> Dict:
        asset_pairs = {
            "error": [],
            "result": {
                f"X{self.base_asset}{self.quote_asset}": {
                    "altname": f"{self.base_asset}{self.quote_asset}",
                    "wsname": f"{self.base_asset}/{self.quote_asset}",
                    "aclass_base": "currency",
                    "base": f"{self.base_asset}",
                    "aclass_quote": "currency",
                    "quote": f"{self.quote_asset}",
                    "lot": "unit",
                    "pair_decimals": 5,
                    "lot_decimals": 8,
                    "lot_multiplier": 1,
                    "leverage_buy": [
                        2,
                        3,
                    ],
                    "leverage_sell": [
                        2,
                        3,
                    ],
                    "fees": [
                        [
                            0,
                            0.26
                        ],
                        [
                            50000,
                            0.24
                        ],
                    ],
                    "fees_maker": [
                        [
                            0,
                            0.16
                        ],
                        [
                            50000,
                            0.14
                        ],
                    ],
                    "fee_volume_currency": "ZUSD",
                    "margin_call": 80,
                    "margin_stop": 40,
                    "ordermin": "0.005"
                },
            }
        }
        return asset_pairs

    def get_balances_mock(self, base_asset_balance: float, quote_asset_balance: float) -> Dict:
        balances = {
            "error": [],
            "result": {
                self.base_asset: str(base_asset_balance),
                self.quote_asset: str(quote_asset_balance),
                "USDT": "171288.6158",
            }
        }
        return balances

    def get_open_orders_mock(self, quantity: float, price: float, order_type: str) -> Dict:
        open_orders = {
            "error": [],
            "result": {
                "open": {
                    "OQCLML-BW3P3-BUCMWZ": self.get_order_status_mock(quantity, price, order_type, status="open"),
                }
            }
        }
        return open_orders

    def get_query_orders_mock(
        self, exchange_id: str, quantity: float, price: float, order_type: str, status: str
    ) -> Dict:
        query_orders = {
            "error": [],
            "result": {
                exchange_id: self.get_order_status_mock(quantity, price, order_type, status)
            }
        }
        return query_orders

    def get_order_status_mock(self, quantity: float, price: float, order_type: str, status: str) -> Dict:
        order_status = {
            "refid": None,
            "userref": 0,
            "status": status,
            "opentm": 1616666559.8974,
            "starttm": 0,
            "expiretm": 0,
            "descr": {
                "pair": f"{self.base_asset}{self.quote_asset}",
                "type": order_type,
                "ordertype": "limit",
                "price": str(price),
                "price2": "0",
                "leverage": "none",
                "order": f"buy {quantity} {self.base_asset}{self.quote_asset} @ limit {price}",
                "close": ""
            },
            "vol": str(quantity),
            "vol_exec": "0",
            "cost": str(price * quantity),
            "fee": "0.00000",
            "price": str(price),
            "stopprice": "0.00000",
            "limitprice": "0.00000",
            "misc": "",
            "oflags": "fciq",
            "trades": [
                "TCCCTY-WE2O6-P3NB37"
            ]
        }
        return order_status

    def get_order_placed_mock(self, exchange_id: str, quantity: float, price: float, order_type: str) -> Dict:
        order_placed = {
            "error": [],
            "result": {
                "descr": {
                    "order": f"{order_type} {quantity} {self.base_asset}{self.quote_asset}"
                             f" @ limit {price} with 2:1 leverage",
                },
                "txid": [
                    exchange_id
                ]
            }
        }
        return order_placed

    @aioresponses()
    def test_get_asset_pairs(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ASSET_PAIRS_PATH_URL}"
        resp = self.get_asset_pairs_mock()
        mocked_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.exchange.get_asset_pairs())

        self.assertIn(self.trading_pair, ret)
        self.assertEqual(
            ret[self.trading_pair], resp["result"][f"X{self.base_asset}{self.quote_asset}"]  # shallow comparison is ok
        )

    @aioresponses()
    def test_update_balances(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ASSET_PAIRS_PATH_URL}"
        resp = self.get_asset_pairs_mock()
        mocked_api.get(url, body=json.dumps(resp))

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.BALANCE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_balances_mock(base_asset_balance=10, quote_asset_balance=20)
        mocked_api.post(regex_url, body=json.dumps(resp))

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.OPEN_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_open_orders_mock(quantity=1, price=2, order_type="buy")
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertEqual(self.exchange.available_balances[self.quote_asset], Decimal("18"))

    @aioresponses()
    def test_update_order_status_order_closed(self, mocked_api):
        order_id = "someId"
        exchange_id = "someExchangeId"

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.QUERY_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_query_orders_mock(exchange_id, quantity=1, price=2, order_type="buy", status="closed")
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=2,
            amount=1,
            order_type=OrderType.LIMIT,
            userref=1,
        )
        self.exchange.add_listener(MarketEvent.BuyOrderCompleted, self.event_listener)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertEqual(len(self.event_listener.event_log), 1)
        self.assertTrue(isinstance(self.event_listener.event_log[0], BuyOrderCompletedEvent))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.TIME_PATH_URL}"
        resp = {"status": 200, "result": []}
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancelled_error(self, mock_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.TIME_PATH_URL}"
        mock_api.get(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(coroutine=self.exchange.check_network())

    @aioresponses()
    def test_check_network_not_connected_for_error_status(self, mock_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.TIME_PATH_URL}"
        resp = {"status": 405, "result": []}
        mock_api.get(url, status=405, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_get_open_orders_with_userref(self, mocked_api):
        sent_messages = []
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.OPEN_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_open_orders_mock(quantity=1, price=2, order_type="buy")
        mocked_api.post(regex_url, body=json.dumps(resp), callback=partial(self.register_sent_request, sent_messages))
        userref = 1

        ret = self.async_run_with_timeout(self.exchange.get_open_orders_with_userref(userref))

        self.assertEqual(len(sent_messages), 1)

        sent_message = sent_messages[0][1]["data"]

        self.assertEqual(sent_message["userref"], userref)
        self.assertEqual(ret, resp["result"])  # shallow comparison ok

    @aioresponses()
    def test_get_order(self, mocked_api):
        sent_messages = []
        order_id = "someId"
        exchange_id = "someExchangeId"

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.QUERY_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_query_orders_mock(exchange_id, quantity=1, price=2, order_type="buy", status="closed")
        mocked_api.post(regex_url, body=json.dumps(resp), callback=partial(self.register_sent_request, sent_messages))

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=2,
            amount=1,
            order_type=OrderType.LIMIT,
            userref=1,
        )
        ret = self.async_run_with_timeout(self.exchange.get_order(client_order_id=order_id))

        self.assertEqual(len(sent_messages), 1)

        sent_message = sent_messages[0][1]["data"]

        self.assertEqual(sent_message["txid"], exchange_id)
        self.assertEqual(ret, resp["result"])  # shallow comparison ok

    @aioresponses()
    def test_execute_buy(self, mocked_api):
        self.exchange.start(self.clock, self.start_time)
        self.simulate_trading_rules_initialized(mocked_api)

        order_id = "someId"
        exchange_id = "someExchangeId"
        userref = 1
        quantity = 1
        price = 2

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ADD_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_placed_mock(exchange_id, quantity, price, order_type="buy")
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)
        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id,
                self.trading_pair,
                amount=Decimal(quantity),
                order_type=OrderType.LIMIT,
                price=Decimal(price),
                userref=userref,
            )
        )

        self.assertEqual(len(self.event_listener.event_log), 1)
        self.assertTrue(isinstance(self.event_listener.event_log[0], BuyOrderCreatedEvent))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_sell(self, mocked_api):
        order_id = "someId"
        exchange_id = "someExchangeId"
        userref = 1
        quantity = 1
        price = 2

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ADD_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_placed_mock(exchange_id, quantity, price, order_type="sell")
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.exchange.start(self.clock, self.start_time)
        self.simulate_trading_rules_initialized(mocked_api)
        self.exchange.add_listener(MarketEvent.SellOrderCreated, self.event_listener)
        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id,
                self.trading_pair,
                amount=Decimal(quantity),
                order_type=OrderType.LIMIT,
                price=Decimal(price),
                userref=userref,
            )
        )

        self.assertEqual(len(self.event_listener.event_log), 1)
        self.assertTrue(isinstance(self.event_listener.event_log[0], SellOrderCreatedEvent))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel(self, mocked_api):
        order_id = "someId"
        exchange_id = "someExchangeId"

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {
            "error": [],
            "result": {
                "count": 1
            }
        }
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=2,
            amount=1,
            order_type=OrderType.LIMIT,
            userref=1,
        )
        self.exchange.in_flight_orders[order_id].update_exchange_order_id(exchange_id)
        self.exchange.in_flight_orders[order_id].last_state = "pending"
        self.exchange.add_listener(MarketEvent.OrderCancelled, self.event_listener)
        ret = self.async_run_with_timeout(self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertEqual(len(self.event_listener.event_log), 1)
        self.assertTrue(isinstance(self.event_listener.event_log[0], OrderCancelledEvent))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(ret["origClientOrderId"], order_id)

    def test_execute_cancel_ignores_local_orders(self):
        order_id = "someId"
        exchange_id = "someExchangeId"

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=2,
            amount=1,
            order_type=OrderType.LIMIT,
            userref=1,
        )

        with self.assertRaises(KrakenInFlightOrderNotCreated):
            self.async_run_with_timeout(self.exchange.execute_cancel(self.trading_pair, order_id))
