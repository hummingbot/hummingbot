import ast
import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict, List, NamedTuple, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch  # AsyncMock,

import ujson
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.latoken.latoken_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.latoken import latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource
from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange
from hummingbot.connector.exchange.latoken.latoken_utils import DEFAULT_FEES
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus


class LatokenExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.exchange._domain)

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PAIR_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        cls.exchange_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.exchange = LatokenExchange(
            client_config_map=client_config_map,
            latoken_api_key="latoken_api_key",
            latoken_api_secret="latoken_api_secret",
            domain=self.domain,
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({f"{self.base_asset}/{self.quote_asset}": self.trading_pair})
        }
        self.exchange._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}/{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _simulate_create_symbol_map(self, mock_api):
        base, quote = self.trading_pair.split('-')
        ticker_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        currency_url = web_utils.public_rest_url(path_url=CONSTANTS.CURRENCY_PATH_URL, domain=self.domain)
        pair_url = web_utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)
        ticker_list: List[Dict] = [
            {"symbol": f"{base}/{quote}", "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset, "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0},
            {"symbol": "NECC/USDT", "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0}
        ]
        mock_api.get(ticker_url, body=json.dumps(ticker_list))
        currency_list: List[Dict] = [
            {"id": self.base_asset, "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": base, "tag": base, "description": "", "logo": "", "decimals": 18,
             "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0},
            {"id": self.quote_asset, "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": quote, "tag": quote, "description": "", "logo": "",
             "decimals": 8, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Natural Eco Carbon Coin", "tag": "NECC", "description": "",
             "logo": "", "decimals": 18, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Tether USD ", "tag": "USDT", "description": "", "logo": "",
             "decimals": 6, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0}
        ]
        mock_api.get(currency_url, body=json.dumps(currency_list))
        # this list is truncated
        pair_list: List[Dict] = [
            {"id": "30a1032d-1e3e-4c28-8ca7-b60f3406fc3e", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset,
             "priceTick": "0.000000010000000000", "priceDecimals": 8,
             "quantityTick": "1.000000000000000000", "quantityDecimals": 0,
             "costDisplayDecimals": 8, "created": 1599249032243, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""},
            {"id": "3140357b-e0da-41b2-b8f4-20314c46325b", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
             "priceTick": "0.000010000000000000", "priceDecimals": 5,
             "quantityTick": "0.100000000000000000", "quantityDecimals": 1,
             "costDisplayDecimals": 5, "created": 1576052642564, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""}
        ]

        mock_api.get(pair_url, body=json.dumps(pair_list))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

    def _validate_auth_credentials_for_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_for_post_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple,
                                                                   params_key: str):
        json_object = request_call_tuple.kwargs[params_key]
        if json_object is not None:
            request_params = ast.literal_eval(json_object._value.decode("UTF-8"))
            if request_params is not None:
                if 'baseCurrency' in request_params:  # placeorder
                    self.assertIn("timestamp", request_params)
                elif len(request_params) == 1 and "id" in request_params:  # cancelorder
                    self.assertIn("id", request_params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-LA-SIGNATURE", request_headers)
        self.assertIn("X-LA-APIKEY", request_headers)
        self.assertEqual("latoken_api_key", request_headers["X-LA-APIKEY"])

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps({}))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(status, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        exchange_order_id = "12345678-1234-1244-1244-123456789012"
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "id": exchange_order_id,
            "message": "cancellation request successfully submitted",
            "status": "SUCCESS",
            "error": "",
            "errors": {}
        }

        mock_api.post(regex_url, body=json.dumps(response), callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])
        # request_params = cancel_request[1][0].kwargs["data"]
        # self.assertEqual(exchange_order_id, request_params["id"])
        # self.assertEqual(order.client_order_id, request_params["origClientOrderId"])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order.client_order_id}."
            )
        )

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to cancel order {order.client_order_id}",
            )
        )

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        exchange_order_id = "4XXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  # startswith 4!!!
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["OID1"]

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID2", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["OID2"]

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "id": exchange_order_id,
            "message": "cancellation request successfully submitted",
            "status": "SUCCESS",
            "error": "",
            "errors": {}
        }

        mock_api.post(regex_url, body=json.dumps(response))
        mock_api.post(regex_url, status=400)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["serverTime"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_balances(self, mock_api):
        # url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, domain=self.exchange._domain)
        # regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        #
        # response = {"serverTime": 1640000003000}
        #
        # mock_api.get(regex_url,
        #              body=json.dumps(response))
        #
        # url = web_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        # regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        #
        # response = {"serverTime": 1640000003000}
        #
        # mock_api.get(regex_url,
        #              body=json.dumps(response))

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response_balances = [
            {"id": "1e200836-a037-4475-825e-f202dd0b0e92",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "available": "10",
             "blocked": "5"},
            {"id": "1e200836-a037-4475-825e-f202dd0b0e93",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "0d02fdfc-9555-4cd9-8398-006003033a9e",
             "available": "2000",
             "blocked": "0"}
        ]

        mock_api.get(regex_url, body=json.dumps(response_balances))

        first_currency_url = web_utils.private_rest_url(f"{CONSTANTS.CURRENCY_PATH_URL}/{response_balances[0]['currency']}", self.domain)
        first_currency_regex_url = re.compile(f"^{first_currency_url}".replace(".", r"\.").replace("?", r"\?"))
        first_currency = {"id": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
                          "type": "CURRENCY_TYPE_CRYPTO", "name": "Bitcoin", "tag": "BTC", "description": "",
                          "logo": "", "decimals": 8,
                          "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
                          "minTransferAmount": 0}
        mock_api.get(first_currency_regex_url, body=json.dumps(first_currency))

        second_currency_url = web_utils.private_rest_url(f"{CONSTANTS.CURRENCY_PATH_URL}/{response_balances[1]['currency']}", self.domain)
        second_currency_regex_url = re.compile(f"^{second_currency_url}".replace(".", r"\.").replace("?", r"\?"))
        second_currency = {"id": "0d02fdfc-9555-4cd9-8398-006003033a9e", "status": "CURRENCY_STATUS_ACTIVE",
                           "type": "CURRENCY_TYPE_CRYPTO", "name": "LITECOIN", "tag": "LTC", "description": "",
                           "logo": "", "decimals": 8, "created": 1572912000000, "tier": 1,
                           "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0}
        mock_api.get(second_currency_regex_url, body=json.dumps(second_currency))

        self.async_run_with_timeout(self.exchange._update_balances(), timeout=10)

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        second_response_balances = [
            {"id": "1e200836-a037-4475-825e-f202dd0b0e92",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "available": "10",
             "blocked": "5"},
        ]

        mock_api.get(regex_url, body=json.dumps(second_response_balances))
        mock_api.get(first_currency_regex_url, body=json.dumps(first_currency))
        self.async_run_with_timeout(self.exchange._update_balances(), timeout=10)

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        client_order_id = "OID1"
        exchange_order_id = "100234"
        untracked_client_order_id = "UNTRACKED_OID1"
        untracked_exchange_order_id = "UNTRACKED_100234"
        price = "100.0"
        amount = "10"
        change_type = "ORDER_CHANGE_TYPE_FILLED"
        status = "ORDER_STATUS_PLACED"

        filled = "10"
        delta_filled = filled
        cost = "32.000000000000000000"
        fee = '0.00098999'

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
        )
        order = self.exchange.in_flight_orders[client_order_id]
        self._simulate_create_symbol_map(mock_api)
        event_message_order_update = {'cmd': 'MESSAGE',
                                      'headers': {'destination': '/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/order',
                                                  'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa',
                                                  'content-length': '654',
                                                  'subscription': str(CONSTANTS.SUBSCRIPTION_ID_ORDERS)},
                                      'body': '{"payload":[{"id":"' + exchange_order_id + '","user":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","changeType":"' + change_type + '","status":"' + status + '","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + client_order_id + '","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","filled":"' + filled + '","deltaFilled":"' + delta_filled + '","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        untracked_event_message_order_update = {'cmd': 'MESSAGE',
                                                'headers': {
                                                    'destination': '/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/order',
                                                    'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa',
                                                    'content-length': '654',
                                                    'subscription': str(CONSTANTS.SUBSCRIPTION_ID_ORDERS)},
                                                'body': '{"payload":[{"id":"' + untracked_exchange_order_id + '","user":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","changeType":"' + change_type + '","status":"' + status + '","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + untracked_client_order_id + '","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","filled":"' + filled + '","deltaFilled":"' + delta_filled + '","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        event_message_trade_update = {'cmd': 'MESSAGE',
                                      'headers': {'destination': '/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/trade',
                                                  'message-id': '85c53805-5f2a-4aa7-8c44-d93b011a306e',
                                                  'content-length': '389',
                                                  'subscription': str(CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE)},
                                      'body': '{"payload":[{"id":"b0cf76d4-192c-42f0-a0df-a5215fccc1e1","timestamp":1653320002582,"baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","direction":"TRADE_DIRECTION_BUY","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","order":"' + exchange_order_id + '","fee":"' + fee + '","makerBuyer":true}],"nonce":1,"timestamp":1653320002602}'}

        untracked_event_message_trade_update = {'cmd': 'MESSAGE',
                                                'headers': {
                                                    'destination': '/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/trade',
                                                    'message-id': '85c53805-5f2a-4aa7-8c44-d93b011a306e',
                                                    'content-length': '389',
                                                    'subscription': str(CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE)},
                                                'body': '{"payload":[{"id":"NOT_SEEN_BEFORE_TRADE_ID","timestamp":1653320002582,"baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","direction":"TRADE_DIRECTION_BUY","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","order":"' + untracked_exchange_order_id + '","fee":"' + fee + '","makerBuyer":true}],"nonce":1,"timestamp":1653320002602}'}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message_order_update, untracked_event_message_order_update,
                                      event_message_trade_update, untracked_event_message_trade_update,
                                      asyncio.CancelledError]

        self.exchange._user_stream_tracker._user_stream = mock_queue

        trade_fill = ujson.loads(event_message_trade_update["body"])["payload"][0]
        trade_fill_non_tracked_order = ujson.loads(untracked_event_message_trade_update["body"])["payload"][0]
        self.exchange.add_exchange_order_ids_from_market_recorder(
            {trade_fill_non_tracked_order["order"]: untracked_client_order_id})

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["quantity"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(order.quote_asset, Decimal(trade_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)

        # fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        # self.assertEqual(float(trade_fill_non_tracked_order["timestamp"]) * 1e-3, fill_event.timestamp)
        # self.assertEqual(untracked_client_order_id, fill_event.order_id)
        # self.assertEqual(self.trading_pair, fill_event.trading_pair)
        # self.assertEqual(TradeType.BUY, fill_event.trade_type)
        # self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        # self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        # self.assertEqual(Decimal(trade_fill_non_tracked_order["quantity"]), fill_event.amount)
        # self.assertEqual(0.0, fill_event.trade_fee.percent)
        # self.assertEqual([
        #     TokenAmount(
        #         self.trading_pair.split('-')[-1],
        #         Decimal(trade_fill_non_tracked_order["fee"]))],
        #     fill_event.trade_fee.flat_fees)
        # self.assertTrue(self._is_logged(
        #     "INFO",
        #     f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        # ))

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_CLOSED",
            # "changeType": "ORDER_CHANGE_TYPE_FILLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "1.0",  # note that filled == quantity filled!!
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))
        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_update_order_status_when_cancelled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[client_order_id]

        url = web_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_CANCELLED",
            "changeType": "ORDER_CHANGE_TYPE_CANCELLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "230.0",
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        # request_params = order_request[1][0].kwargs["params"]
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_REJECTED",
            # "changeType": "ORDER_CHANGE_TYPE_CANCELLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "230.0",
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        # request_params = order_request[1][0].kwargs["params"]
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={float(order_status['timestamp'])* 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

    @aioresponses()
    def test_update_order_status_marks_order_as_failure_after_retries(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[client_order_id]

        url = web_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=401)

        for i in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        pair_url = web_utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)

        pair_list: List[Dict] = [
            {"id": "30a1032d-1e3e-4c28-8ca7-b60f3406fc3e", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset,
             "priceTick": "0.000000010000000000", "priceDecimals": 8,
             "quantityTick": "1.000000000000000000", "quantityDecimals": 0,
             "costDisplayDecimals": 8, "created": 1599249032243,
             # "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""},
            # {"id": "3140357b-e0da-41b2-b8f4-20314c46325b", "status": "PAIR_STATUS_ACTIVE",
            #  "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
            #  "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
            #  "priceTick": "0.000010000000000000", "priceDecimals": 5,
            #  "quantityTick": "0.100000000000000000", "quantityDecimals": 1,
            #  "costDisplayDecimals": 5, "created": 1576052642564, "minOrderQuantity": "0",
            #  "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
            #  "externalSymbol": ""}
        ]

        mock_api.get(pair_url, body=json.dumps(pair_list))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {pair_list[0]}. Skipping.")
        )

    @aioresponses()
    def test_user_stream_balance_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        base, _ = self.trading_pair.split('-')
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/account',
                                     'message-id': 'eb428773-8eaa-40ae-a3e3-b6eb2d1454ae', 'content-length': '3597',
                                     'subscription': str(CONSTANTS.SUBSCRIPTION_ID_ACCOUNT)},
                         'body': '{"payload":[{"id":"6b4d1e11-1d0b-418c-a660-b9a30ef56529","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1648225456689,"currency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","available":"10.000000000000000000","blocked":"1.000000000000000000","user":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}],"nonce":0,"timestamp":1650265966821}'}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]

        body = ujson.loads(event_message["body"])
        currency_url = web_utils.public_rest_url(path_url=f"{CONSTANTS.CURRENCY_PATH_URL}/{body['payload'][0]['currency']}", domain=self.domain)
        currency_list: Dict = {"id": "d8ae67f2-f954-4014-98c8-64b1ac334c64",
                               "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
                               "type": "CURRENCY_TYPE_CRYPTO", "name": base, "tag": base, "description": "", "logo": "",
                               "decimals": 18,
                               "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN",
                               "minTransferAmount": 0}

        mock_api.get(currency_url, body=json.dumps(currency_list))
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[base])
        self.assertEqual(Decimal("11"), self.exchange.get_balance(base))

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = [
            InFlightOrder(
                client_order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                creation_timestamp=1640001112.223
            ),
            InFlightOrder(
                client_order_id="OID2",
                exchange_order_id="EOID2",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                initial_state=OrderState.CANCELED,
                creation_timestamp=1640001112.223
            ),
            InFlightOrder(
                client_order_id="OID3",
                exchange_order_id="EOID3",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                initial_state=OrderState.FILLED,
                creation_timestamp=1640001112.223
            ),
            InFlightOrder(
                client_order_id="OID4",
                exchange_order_id="EOID4",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                initial_state=OrderState.FAILED,
                creation_timestamp=1640001112.223)
        ]

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
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
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self, mock_api):
        fee_schema_url = web_utils.private_rest_url(
            path_url=f"{CONSTANTS.FEES_PATH_URL}/{self.trading_pair.replace('-', '/')}", domain=self.domain)
        fee_schema = {
            "makerFee": "0.002200000000000000",
            "takerFee": "0.002800000000000000",
            "type": "FEE_SCHEME_TYPE_PERCENT_QUOTE",
            "take": "FEE_SCHEME_TAKE_PROPORTION"
        }

        mock_api.get(fee_schema_url, body=json.dumps(fee_schema))

        self.async_run_with_timeout(self.exchange._update_trading_fees())
        base, quote = self.trading_pair.split('-')
        fee = self.exchange.get_fee(
            base_currency=base,
            quote_currency=quote,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.0028"), fee.percent)

        fee = self.exchange.get_fee(
            base_currency=base,
            quote_currency=quote,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
            is_maker=True
        )

        self.assertEqual(Decimal("0.0022"), fee.percent)

        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, fee.percent)
