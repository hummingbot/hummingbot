import asyncio
import json
from operator import truediv
import quopri
import re
from socket import socket
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from urllib import request
from socket import gaierror

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter

# Polkadex Classes
from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange
from hummingbot.connector.exchange.polkadex.polkadex_exchange import fee_levied_asset
from hummingbot.connector.exchange.polkadex.polkadex_order_book_data_source import PolkadexOrderbookDataSource
from hummingbot.connector.exchange.polkadex.polkadex_payload import create_order


class PolkadexExchangeUnitTests(unittest.TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "PDEX"
        cls.quote_asset = "1"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant
        self.resume_test_event = asyncio.Event()
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        # Polkadex Connector
        self.connector = PolkadexExchange(
            client_config_map=client_config_map,
            polkadex_seed_phrase="empower open normal dream vendor day catch flee entry monitor like april",
            trading_pairs=["HBOT-PDEX"]
        )
        # Polkadex OrderBookDataSource
        self.data_source = PolkadexOrderbookDataSource(
            trading_pairs=[],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            api_key=" ")

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 20):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_last_traded_price(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "getRecentTrades": {
                    "items": [{
                        "p": 20
                    }]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message: float = self.async_run_with_timeout(
            self.connector._get_last_traded_price(self.trading_pair)
        )

        # self.assertEqual(20.0, order_book_message)

    # Need response from `get_all_markets`
    @aioresponses()
    def test_initialize_trading_pair_symbols(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "getAllMarkets": {
                    "items": [
                        {
                            "market": "PDEX-1",
                            "max_trade_amount": "1000000000000000",
                            "min_qty": "1000000000000",
                            "min_trade_amount": "1000000000000"
                        }
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._initialize_trading_pair_symbol_map()
        )

    # Need query from user.py in graphql
    @aioresponses()
    def test_update_balances(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        resp = {
            "data": {
                "getAllBalancesByMainAccount": {
                    "items": [
                        {
                            "a": "1",
                            "f": "94000000000000",
                            "p": "0",
                            "r": "6000000000000"
                        },
                        {
                            "a": "PDEX",
                            "f": "99000000000000",
                            "p": "0",
                            "r": "1000000000000"
                        }
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._update_balances()
        )

    # Need to query user.py in graphql
    @aioresponses()
    def test_update_order_status(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._update_order_status()
        )

    @aioresponses()
    def test_update_order_status_tracked_orders(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="0x98157fdd3bacbc07d26c0b2ba271e76612241e83556968a9fcb54bd626698131"
        )
        self.connector.in_flight_orders[order.client_order_id] = order
        self.connector._last_poll_timestamp = 0
        # self.connector.current_timestamp = 40
        tracked_orders = list(self.connector.in_flight_orders.values())
        # self.assertEqual(len(tracked_orders),1)
        # self.assertEqual(self.connector._last_poll_timestamp > self.connector.current_timestamp, True)
        mock_api.post(raw_url, body=json.dumps(resp))
        resp = {
            "data": {
                "findOrderByMainAccount": {
                    "afp": "0",
                    "cid": "0x14c7ed1b5c973ab484f74271e78fd19d34737ef80dfd4660b1df0aefdaa6ef17",
                    "fee": "0",
                    "fq": "0",
                    "id": "0x10d67cc2914f306b3d73d026f72ad5dabd465b49fcb40cd5828bb6cf264fe620",
                    "m": "PDEX-1",
                    "ot": "LIMIT",
                    "q": "1",
                    "p": "8",
                    "s": "Ask",
                    "sid": "0",
                    "st": "OPEN",
                    "t": "1662612081000",
                    "u": "esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk"
                }
            }
        }

        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._update_order_status()
        )

    @aioresponses()
    def test_update_order_status_exchange_id_none(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id=None
        )
        self.connector.in_flight_orders[order.client_order_id] = order
        self.connector._last_poll_timestamp = 0
        # self.connector.current_timestamp = 40
        tracked_orders = list(self.connector.in_flight_orders.values())
        # self.assertEqual(len(tracked_orders),1)
        # self.assertEqual(self.connector._last_poll_timestamp > self.connector.current_timestamp, True)
        mock_api.post(raw_url, body=json.dumps(resp))
        resp = {
            "data": {
                "findOrderByMainAccount": None
            }
        }

        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._update_order_status()
        )

    @aioresponses()
    def test_update_order_status_exchange_result_none(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="0x98157fdd3bacbc07d26c0b2ba271e76612241e83556968a9fcb54bd626698131"
        )
        self.connector.in_flight_orders[order.client_order_id] = order
        self.connector._last_poll_timestamp = 0
        # self.connector.current_timestamp = 40
        tracked_orders = list(self.connector.in_flight_orders.values())
        # self.assertEqual(len(tracked_orders),1)
        # self.assertEqual(self.connector._last_poll_timestamp > self.connector.current_timestamp, True)
        mock_api.post(raw_url, body=json.dumps(resp))
        resp = {
            "data": {
                "findOrderByMainAccount": None
            }
        }

        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._update_order_status()
        )

    @aioresponses()
    def test_cancel_order(self, mock_api):
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e"
        )
        self.connector.user_proxy_address = "esrJNKDP4tvAkGMC9Su2VYTAycU2nrQy8qt4dFhdXwV19Yh1K"
        order_book_message = self.async_run_with_timeout(
            self.connector._place_cancel(order_id="123", tracked_order=order)
        )
        self.assertEqual(order_book_message, False)

    @aioresponses()
    def test_cancel_order_exchange_order_id_none(self, mock_api):
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id=None
        )
        # self.connector.user_proxy_address = "esrJNKDP4tvAkGMC9Su2VYTAycU2nrQy8qt4dFhdXwV19Yh1K"
        order_book_message = self.async_run_with_timeout(
            self.connector._place_cancel(order_id="123", tracked_order=order)
        )
        # self.assertEqual(order_book_message, True)

    @aioresponses()
    def test_place_order(self, mock_api):
        order = InFlightOrder(
            client_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )

        order_book_message = self.async_run_with_timeout(
            self.connector._place_order(order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
                                        trading_pair=self.trading_pair, amount=Decimal("1000.0"),
                                        trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("1000.0"))
        )
        print("Order Book message recv after order: ", order_book_message)
        # self.assertEqual(1, 0)

    def test_fee_levied_asset(self):
        base = fee_levied_asset(side="Bid", base="HBOT", quote="PDEX")
        quote = fee_levied_asset(side="Ask", base="HBOT", quote="PDEX")
        self.assertEqual(base, "HBOT")
        self.assertEqual(quote, "PDEX")

    def test_initialize_Trading_pair_symbols_from_exchange_info(self):
        with self.assertRaises(NotImplementedError):
            self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info={"Error": "404"})


    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "getAllMarkets": {
                    "items": [
                        {
                            "base_asset_precision": "8",
                            "market": "PDEX-5",
                            "max_order_price": "10000",
                            "max_order_qty": "10000",
                            "min_order_price": "1.0E-4",
                            "min_order_qty": "0.001",
                            "price_tick_size": "1.0E-6",
                            "qty_step_size": "0.001",
                            "quote_asset_precision": "8"
                        },
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        mock_api.post(raw_url, body=json.dumps(resp))
        self.async_run_with_timeout(
            self.connector._update_trading_rules()
        )

    def test_c_stop_tracking_order(self):
        with self.assertRaises(NotImplementedError):
            self.connector.c_stop_tracking_order(order_id="123")

    @aioresponses()
    def test_cancel_order_exchange_id_not_none(self, mock_api):
        order = InFlightOrder(
            client_order_id="HBOTBPX1118318974b805f4676d66446",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="0x1f6853a78a1629c15fc3db2da3c902169ddd7a72f243d0b753a06f4ec62556a5"
        )
        #szzsvapgkjdurfl7ijvc3vtbba
        # szzsvapgkjdurfl7ijvc3vtbba
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "cancel_order": "True"
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        mock_api.get(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._place_cancel(order_id="123", tracked_order=order)
        )

    @aioresponses()
    def test_cancel_order_could_not_encode_cancel_request(self, mock_api):
        order = InFlightOrder(
            client_order_id="HBOTBPX1118318974b805f4676d66446",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="HBOTBPX1118318974b805f4676d66446"
        )
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "cancel_order": "True"
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        mock_api.get(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._place_cancel(order_id="123", tracked_order=order)
        )

    @aioresponses()
    def test_cancel_order_could_not_sign_cancel_request(self, mock_api):
        order = InFlightOrder(
            client_order_id="123",
            trading_pair="PDEX-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            exchange_order_id="0x1f6853a78a1629c15fc3db2da3c902169ddd7a72f243d0b753a06f4ec62556a5"
        )
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "cancel_order": "True"
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        mock_api.get(raw_url, body=json.dumps(resp))
        order_book_message = self.async_run_with_timeout(
            self.connector._place_cancel(order_id="123", tracked_order=order)
        )

    @aioresponses()
    def test_place_order_with_account(self, mock_api):
        order = InFlightOrder(
            client_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )

        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        resp = {
            "data": {
                "place_order": "True"
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))

        order_book_message = self.async_run_with_timeout(
            self.connector._place_order(order_id="HBOTBPX1118318974b805f4676d66446", trading_pair=str("PDEX-1"),
                                        amount=Decimal("1.0"), trade_type=TradeType.BUY, order_type=OrderType.LIMIT,
                                        price=Decimal("1.0"))
        )
        print("order_book_message recv after placing order: ", order_book_message)

    @aioresponses()
    def test_place_order_could_not_encode(self, mock_api):
        order = InFlightOrder(
            client_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )

        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))

        order_book_message = self.async_run_with_timeout(
            self.connector._place_order(order_id="123", trading_pair=str("PDEX-1"), amount=Decimal("1.0"),
                                        trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("1.0"))
        )

    @aioresponses()
    def test_place_order_with_account_could_not_gql(self, mock_api):
        order = InFlightOrder(
            client_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )

        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))

        order_book_message = self.async_run_with_timeout(
            self.connector._place_order(order_id="HBOTBPX1118318974b805f4676d66446", trading_pair=str("PDEX-1"),
                                        amount=Decimal("1.0"), trade_type=TradeType.BUY, order_type=OrderType.LIMIT,
                                        price=Decimal("1.0"))
        )

    def test_order_update_callback(self):
        msg = {
            "type": "SetOrder",
            "event_id": 10,
            "client_order_id": "0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            "avg_filled_price": 10,
            "fee": 100,
            "filled_quantity": 100,
            "status": "OPEN",
            "id": 0,
            "user": "5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
            "pair": {"base_asset":"polkadex","quote_asset":{"asset":1}},
            "side": "Ask",
            "order_type": "LIMIT",
            "qty": 10,
            "price": 10,
            "nonce": 100
        }

        request = {
            "data": {
                "websocket_streams": {
                    "data":
                        msg
                }
            }
        }
        order = InFlightOrder(
            client_order_id="0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.connector.in_flight_orders[order.client_order_id] = order
        # self.in_flight_orders.get(message["client_order_id"])
        self.connector.order_update_callback(msg)
        # assert(1==2)

    def test_balance_update_callback(self):
        msg = {
            "type": "SetBalance",
            "event_id": 0,
            "user": "5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
            "asset": "polkadex",
            "free": 0,
            "pending_withdrawal": 0,
            "reserved": 0
        }

        request = {
            "data": {
                "websocket_streams": {
                    "data":
                        msg
                }
            }
        }
        self.connector.balance_update_callback(msg)

    """ def test_handle_websocket_message(self):
        msg = {
            "type": "SetBalance",
            "event_id": 0,
            "user": "5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
            "asset": "polkadex",
            "free": 0,
            "pending_withdrawal": 0,
            "reserved": 0
        }

        request = {
            "data": {
                "websocket_streams": {
                    "data": msg
                }
            }
        }
        print("request 1: ", request)
        self.connector.handle_websocket_message(request)
        msg = {
            "type": "SetOrder",
            "event_id": 10,
            "client_order_id": "0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
            "avg_filled_price": 10,
            "fee": 100,
            "filled_quantity": 100,
            "status": "OPEN",
            "id": 0,
            "user": "5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
            "pair": {"base_asset": "polkadex", "quote_asset": {"asset": 1}},
            "side": "Ask",
            "order_type": "LIMIT",
            "qty": 10,
            "price": 10,
            "nonce": 100
        }

        request = {
            "data": {
                "websocket_streams": {
                    "data": msg
                }
            }
        }
        print("request 2: ", request)
        self.connector.handle_websocket_message(request) """
        # assert (1, 2)

    @aioresponses()
    def test_user_stream_event_listener(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "findUserByProxyAccount": {
                    "items": [
                        "{eid=1, hash_key=proxy-esqacydQWhJ9D7Wg5G7VZfPYGd6uM6X7kk8Jq3fyNDh2HvYrk, range_key=esoGSWG1uQFx1HPLpdZgsNRZBdtPLtpkSUruL1ZFqjLH3e9B4}"
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        """ with self.assertRaises(gaierror):
            order_book_message = self.async_run_with_timeout(
                self.connector._user_stream_event_listener()
            ) """

    @aioresponses()
    def test_check_network(self, mock_api):
        order_book_message = self.async_run_with_timeout(
            self.connector.check_network()
        )

    @aioresponses()
    def test_update_time_synchronizer(self, mock_api):
        order_book_message = self.async_run_with_timeout(
            self.connector._update_time_synchronizer()
        )

    def test_connector_properties(self):
        self.assertEqual(self.connector.client_order_id_prefix, "HBOT")
        self.assertEqual(self.connector.client_order_id_max_length, 32)
        self.assertEqual(self.connector.is_trading_required, True)
        self.assertEqual(self.connector.is_cancel_request_in_exchange_synchronous, True)
        self.assertEqual(self.connector.supported_order_types(), [OrderType.LIMIT, OrderType.MARKET])

        with self.assertRaises(NotImplementedError):
            self.connector.trading_pairs_request_path

        with self.assertRaises(NotImplementedError):
            self.connector.check_network_request_path



