import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class TestGateIoExchange(unittest.TestCase):
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
        cls.api_secret = "someSecret"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = GateIoExchange(
            client_config_map=self.client_config_map,
            gate_io_api_key=self.api_key,
            gate_io_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair])

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
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

    @staticmethod
    def get_currency_data_mock() -> List:
        currency_data = [
            {
                "currency": "GT",
                "delisted": False,
                "withdraw_disabled": False,
                "withdraw_delayed": False,
                "deposit_disabled": False,
                "trade_disabled": False,
            }
        ]
        return currency_data

    def get_trading_rules_mock(self) -> List:
        trading_rules = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "tradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650,
            }
        ]
        return trading_rules

    def get_order_create_response_mock(self, cancelled: bool = False, exchange_order_id: str = "someExchId") -> Dict:
        order_create_resp_mock = {
            "id": exchange_order_id,
            "text": "t-123456",
            "create_time": "1548000000",
            "update_time": "1548000100",
            "create_time_ms": 1548000000123,
            "update_time_ms": 1548000100123,
            "currency_pair": f"{self.base_asset}_{self.quote_asset}",
            "status": "cancelled" if cancelled else "open",
            "type": "limit",
            "account": "spot",
            "side": "buy",
            "iceberg": "0",
            "amount": "1",
            "price": "5.00032",
            "time_in_force": "gtc",
            "left": "0.5",
            "filled_total": "2.50016",
            "fee": "0.005",
            "fee_currency": "ETH",
            "point_fee": "0",
            "gt_fee": "0",
            "gt_discount": False,
            "rebated_fee": "0",
            "rebated_fee_currency": "BTC",
        }
        return order_create_resp_mock

    def get_in_flight_order(self, client_order_id: str, exchange_order_id: str = "someExchId") -> InFlightOrder:
        order = InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("5.1"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.0
        )
        return order

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def get_user_balances_mock(self) -> List:
        user_balances = [
            {
                "currency": self.base_asset,
                "available": "968.8",
                "locked": "0",
            },
            {
                "currency": self.quote_asset,
                "available": "543.9",
                "locked": "0",
            },
        ]
        return user_balances

    def get_open_order_mock(self, exchange_order_id: str = "someExchId") -> List:
        open_orders = [
            {
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                "total": 1,
                "orders": [
                    {
                        "id": exchange_order_id,
                        "text": f"{CONSTANTS.HBOT_ORDER_ID}-{exchange_order_id}",
                        "create_time": "1548000000",
                        "update_time": "1548000100",
                        "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                        "status": "open",
                        "type": "limit",
                        "account": "spot",
                        "side": "buy",
                        "amount": "1",
                        "price": "5.00032",
                        "time_in_force": "gtc",
                        "left": "0.5",
                        "filled_total": "2.50016",
                        "fee": "0.005",
                        "fee_currency": "ETH",
                        "point_fee": "0",
                        "gt_fee": "0",
                        "gt_discount": False,
                        "rebated_fee": "0",
                        "rebated_fee_currency": "BTC",
                    }
                ],
            }
        ]
        return open_orders

    def get_order_trade_response(
            self, order: InFlightOrder, is_completely_filled: bool = False
    ) -> Dict[str, Any]:
        order_amount = order.amount
        if not is_completely_filled:
            order_amount = float(Decimal("0.5") * order_amount)
        base_asset, quote_asset = order.trading_pair.split("-")[0], order.trading_pair.split("-")[1]
        return [
            {
                "id": 5736713,
                "user_id": 1000001,
                "order_id": order.exchange_order_id,
                "currency_pair": order.trading_pair,
                "create_time": 1605176741,
                "create_time_ms": "1605176741123.456",
                "side": "buy" if order.trade_type == TradeType.BUY else "sell",
                "amount": str(order_amount),
                "role": "maker",
                "price": str(order.price),
                "fee": "0.00200000000000",
                "fee_currency": base_asset if order.trade_type == TradeType.BUY else quote_asset,
                "point_fee": "0",
                "gt_fee": "0",
                "text": order.client_order_id,
            }
        ]

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertEqual(self.expected_supported_order_types, supported_types)

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "tradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650
            },
            {
                "id": "SOME_PAIR",
                "base": "SOME",
                "quote": "PAIR",
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "untradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650
            }
        ]
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(ret))
        self.assertIn(self.trading_pair, ret)
        self.assertNotIn("SOME-PAIR", ret)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = [
            {
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                "last": "0.2959",
                "lowest_ask": "0.295918",
                "highest_bid": "0.295898",
                "change_percentage": "-1.72",
                "base_volume": "78497066.828007",
                "quote_volume": "23432064.936692",
                "high_24h": "0.309372",
                "low_24h": "0.286827",
            }
        ]
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        ticker_requests = [(key, value) for key, value in mock_api.requests.items()
                           if key[1].human_repr().startswith(url)]

        request_params = ticker_requests[0][1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["currency_pair"])

        self.assertEqual(ret[self.trading_pair], float(resp[0]["last"]))

    @aioresponses()
    def test_check_network_not_connected(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.NETWORK_CHECK_PATH_URL}"
        resp = ""
        for i in range(CONSTANTS.API_MAX_RETRIES + 1):
            mock_api.get(url, status=500, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED, msg=f"{ret}")

    @aioresponses()
    def test_check_network(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.NETWORK_CHECK_PATH_URL}"
        resp = self.get_currency_data_mock()
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_update_trading_rules_polling_loop(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = self.get_trading_rules_mock()
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_invalid(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "untradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650,
            }
        ]
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertEqual(0, len(self.exchange.trading_rules))

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "fee": "0.2",
                "trade_status": "tradable",
            }
        ]
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {resp[0]}. Skipping.")
        )

    @aioresponses()
    def test_create_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp), status=201)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["currency_pair"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(Decimal("1"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("5.1"), Decimal(request_data["price"]))
        self.assertEqual(order_id, request_data["text"])

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("1"), create_event.amount)
        self.assertEqual(Decimal("5.1"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["id"], create_event.exchange_order_id)

    @aioresponses()
    def test_create_limit_maker_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp), status=201)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT_MAKER,
                price=Decimal("5.1"),
            )
        )

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["currency_pair"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(Decimal("1"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("5.1"), Decimal(request_data["price"]))
        self.assertEqual(order_id, request_data["text"])

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
        self.assertEqual(Decimal("1"), create_event.amount)
        self.assertEqual(Decimal("5.1"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["id"], create_event.exchange_order_id)

    @aioresponses()
    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.get_price")
    def test_create_market_order(self, mock_api, get_price_mock):
        get_price_mock.return_value = Decimal(5.1)
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp), status=201)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("5.1"),
            )
        )

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["currency_pair"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("market", request_data["type"])
        self.assertEqual(Decimal("1") * Decimal("5.1"), Decimal(request_data["amount"]))
        self.assertEqual(order_id, request_data["text"])

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("1"), create_event.amount)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["id"], create_event.exchange_order_id)

    @aioresponses()
    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.get_price")
    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.get_price_for_volume")
    def test_create_market_order_price_is_nan(self, mock_api, get_price_mock, get_price_for_volume_mock):
        get_price_mock.return_value = None
        get_price_for_volume_mock.return_value = Decimal("5.1")
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp), status=201)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("5.1"),
            )
        )

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["currency_pair"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("market", request_data["type"])
        self.assertEqual(Decimal("1") * Decimal("5.1"), Decimal(request_data["amount"]))
        self.assertEqual(order_id, request_data["text"])

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("1"), create_event.amount)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["id"], create_event.exchange_order_id)

    @aioresponses()
    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.get_price")
    # @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.get_price_for_volume")
    def test_place_order_price_is_nan(self, mock_api, get_price_mock):
        get_price_mock.return_value = None
        # get_price_for_volume_mock.return_value = Decimal("5.1")
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp), status=201)
        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[],
            asks=[OrderBookRow(price=5.1, amount=20, update_id=1)],
            update_id=1,
        )
        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._place_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("nan"),
            )
        )
        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(Decimal("1") * Decimal("5.1"), Decimal(request_data["amount"]))

    @aioresponses()
    def test_create_order_when_order_is_instantly_closed(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        resp["status"] = "closed"
        mock_api.post(regex_url, body=json.dumps(resp))

        event_logger = EventLogger()
        self.exchange.add_listener(MarketEvent.BuyOrderCreated, event_logger)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("1"), create_event.amount)
        self.assertEqual(Decimal("5.1"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["id"], create_event.exchange_order_id)

    @aioresponses()
    def test_order_with_less_amount_than_allowed_is_not_created(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, exception=Exception("The request should never happen"))

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("0.0001"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.01. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @aioresponses()
    def test_create_order_fails(self, _, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock(cancelled=True)
        mock_api.post(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))

    @aioresponses()
    def test_create_order_request_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400)

        order_id = "OID1"
        self.async_run_with_timeout(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id=order_id,
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=exchange_order_id)}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock(cancelled=True)
        mock_api.delete(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, client_order_id))

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = cancel_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["currency_pair"])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {client_order_id}."
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

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=order.exchange_order_id)}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url,
                        status=400,
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to cancel order {order.client_order_id}"
            )
        )

    def test_cancel_order_without_exchange_order_id_marks_order_as_fail_after_retries(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._execute_cancel(
            trading_pair=order.trading_pair,
            order_id=order.client_order_id,
        ))

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "WARNING",
                f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet"
            )
        )

        # After the fourth time not finding the exchange order id the order should be marked as failed
        for i in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(self.exchange._execute_cancel(
                trading_pair=order.trading_pair,
                order_id=order.client_order_id,
            ))

        self.assertTrue(order.is_failure)

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
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

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=order1.exchange_order_id)}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self.get_order_create_response_mock(cancelled=True, exchange_order_id=order1.exchange_order_id)

        mock_api.delete(regex_url, body=json.dumps(response))

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=order2.exchange_order_id)}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url, status=400)

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
    def test_update_balances(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.USER_BALANCES_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = [
            {
                "currency": self.base_asset,
                "available": "968.8",
                "locked": "0",
            },
            {
                "currency": self.quote_asset,
                "available": "500",
                "locked": "300",
            },
        ]

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("968.8"), available_balances[self.base_asset])
        self.assertEqual(Decimal("500"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("968.8"), total_balances[self.base_asset])
        self.assertEqual(Decimal("800"), total_balances[self.quote_asset])

        response = [
            {
                "currency": self.base_asset,
                "available": "968.8",
                "locked": "0",
            },
        ]

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("968.8"), available_balances[self.base_asset])
        self.assertEqual(Decimal("968.8"), total_balances[self.base_asset])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        # Order Trade Updates
        order_trade_updates_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.MY_TRADES_PATH_URL}"
        regex_order_trade_updates_url = re.compile(
            f"^{order_trade_updates_url}".replace(".", r"\.").replace("?", r"\?"))
        order_trade_updates_resp = []
        mock_api.get(
            regex_order_trade_updates_url,
            body=json.dumps(order_trade_updates_resp)
        )

        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL}/"
                            f"{CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id)}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = self.get_order_create_response_mock(
            cancelled=False,
            exchange_order_id=order.exchange_order_id)
        order_status_resp["text"] = order.client_order_id
        order_status_resp["status"] = "closed"
        order_status_resp["left"] = "0"
        order_status_resp["finish_as"] = "filled"
        mock_api.get(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
        )

        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(order_status_url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["currency_pair"])

        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

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

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL}/"
                            f"{CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id)}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = self.get_order_create_response_mock(
            cancelled=False,
            exchange_order_id=order.exchange_order_id)
        order_status_resp["text"] = order.client_order_id
        order_status_resp["status"] = "closed"
        order_status_resp["finish_as"] = "cancelled"
        mock_api.get(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
        )
        # Simulate the order has been cancelled
        self.async_run_with_timeout(self.exchange._update_order_status())
        # self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertTrue(order.is_done)

    @aioresponses()
    def test_update_order_status_when_partilly_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL}/"
                            f"{CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id)}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = self.get_order_create_response_mock(
            cancelled=False,
            exchange_order_id=order.exchange_order_id)
        order_status_resp["text"] = order.client_order_id
        order_status_resp["status"] = "closed"
        order_status_resp["filled_total"] = "0.5"
        order_status_resp["finish_as"] = "open"
        mock_api.get(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
        )
        # Simulate the order has been cancelled
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.assertTrue(order.is_open)

    @aioresponses()
    def test_update_order_status_registers_order_not_found(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        # Order Trade Updates
        order_trade_updates_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.MY_TRADES_PATH_URL}"
        regex_order_trade_updates_url = re.compile(
            f"^{order_trade_updates_url}".replace(".", r"\.").replace("?", r"\?"))
        order_trade_updates_resp = []
        mock_api.get(
            regex_order_trade_updates_url,
            body=json.dumps(order_trade_updates_resp)
        )

        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL}/"
                            f"{CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id)}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_order_status_url, status=404)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

        self.assertTrue(
            self._is_logged(
                "WARNING",
                f"Error fetching status update for the active order {order.client_order_id}: Error executing request GET "
                f"{order_status_url}. HTTP status is 404. Error: ."
            )
        )

    @aioresponses()
    def test_update_order_status_processes_trade_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        # Order Trade Updates
        order_trade_updates_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.MY_TRADES_PATH_URL}"
        regex_order_trade_updates_url = re.compile(
            f"^{order_trade_updates_url}".replace(".", r"\.").replace("?", r"\?"))
        order_trade_updates_resp = self.get_order_trade_response(order=order, is_completely_filled=True)
        mock_api.get(
            regex_order_trade_updates_url,
            body=json.dumps(order_trade_updates_resp)
        )

        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL}/"
                            f"{CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id)}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = self.get_order_create_response_mock(
            cancelled=False,
            exchange_order_id=order.exchange_order_id)
        order_status_resp["text"] = order.client_order_id
        order_status_resp["status"] = "open"
        order_status_resp["left"] = "0"
        mock_api.get(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
        )

        self.async_run_with_timeout(self.exchange._update_order_status())
        self.assertTrue(order.completely_filled_event.is_set())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(order_trade_updates_url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["currency_pair"])
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

        self.assertTrue(order.is_open)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(order_trade_updates_resp[0]["amount"]), fill_event.amount)
        self.assertEqual(Decimal(order_trade_updates_resp[0]["price"]), fill_event.price)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                order_trade_updates_resp[0]["fee_currency"],
                Decimal(order_trade_updates_resp[0]["fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertEqual(str(order_trade_updates_resp[0]["id"]), fill_event.exchange_trade_id)
        self.assertEqual(1, fill_event.leverage)
        self.assertEqual(PositionAction.NIL.value, fill_event.position)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} "
                f"amounting to {order.executed_amount_base}/{order.amount} "
                f"{order.base_asset} has been filled at {Decimal('10000')} HBOT."
            )
        )

    def test_update_order_status_marks_order_with_no_exchange_id_as_not_found(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

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
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID,
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
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_user_stream_update_for_new_order_does_not_update_status(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "time": 1605175506,
            "channel": "spot.orders",
            "event": "update",
            "result": [
                {
                    "id": order.exchange_order_id,
                    "user": 123456,
                    "text": order.client_order_id,
                    "create_time": "1605175506",
                    "create_time_ms": "1605175506123",
                    "update_time": "1605175506",
                    "update_time_ms": "1605175506123",
                    "event": "put",
                    "currency_pair": self.ex_trading_pair,
                    "type": order.order_type.name.lower(),
                    "account": "spot",
                    "side": order.trade_type.name.lower(),
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "time_in_force": "gtc",
                    "left": str(order.amount),
                    "filled_total": "0",
                    "fee": "0",
                    "fee_currency": "USDT",
                    "point_fee": "0",
                    "gt_fee": "0",
                    "gt_discount": True,
                    "rebated_fee": "0",
                    "rebated_fee_currency": "USDT"
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertTrue(order.is_open)

    def test_user_stream_update_for_cancelled_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "time": 1605175506,
            "channel": "spot.orders",
            "event": "update",
            "result": [
                {
                    "id": order.exchange_order_id,
                    "user": 123456,
                    "text": order.client_order_id,
                    "create_time": "1605175506",
                    "create_time_ms": "1605175506123",
                    "update_time": "1605175506",
                    "update_time_ms": "1605175506123",
                    "event": "finish",
                    "currency_pair": self.ex_trading_pair,
                    "type": order.order_type.name.lower(),
                    "account": "spot",
                    "side": order.trade_type.name.lower(),
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "time_in_force": "gtc",
                    "left": str(order.amount),
                    "filled_total": "0",
                    "fee": "0",
                    "fee_currency": "USDT",
                    "point_fee": "0",
                    "gt_fee": "0",
                    "gt_discount": True,
                    "rebated_fee": "0",
                    "rebated_fee_currency": "USDT",
                    "finish_as": "cancelled",
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_partial_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]
        order.current_state = OrderState.OPEN

        event_message = {
            "time": 1605176741,
            "channel": "spot.usertrades",
            "event": "update",
            "result": [
                {
                    "id": 5736713,
                    "user_id": 1000001,
                    "order_id": order.exchange_order_id,
                    "currency_pair": self.ex_trading_pair,
                    "create_time": 1605176741,
                    "create_time_ms": "1605176741123.456",
                    "side": order.trade_type.name.lower(),
                    "amount": "0.5",
                    "role": "taker",
                    "price": "10000.00000000",
                    "fee": "0.00200000000000",
                    "fee_currency": self.quote_asset,
                    "point_fee": "0",
                    "gt_fee": "0",
                    "text": order.client_order_id
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.OPEN, order.current_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(event_message["result"][0]["price"]), fill_event.price)
        self.assertEqual(Decimal(event_message["result"][0]["amount"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                event_message["result"][0]["fee_currency"],
                Decimal(event_message["result"][0]["fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        self.assertTrue(
            self._is_logged("INFO", f"The {order.trade_type.name} order {order.client_order_id} amounting to "
                                    f"0.5/{order.amount} {order.base_asset} has been filled at {Decimal('10000.00000000')} HBOT.")
        )

    def test_user_stream_update_for_order_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        order_event_message = {
            "time": 1605175506,
            "channel": "spot.orders",
            "event": "update",
            "result": [
                {
                    "id": order.exchange_order_id,
                    "user": 123456,
                    "text": order.client_order_id,
                    "create_time": "1605175506",
                    "create_time_ms": "1605175506123",
                    "update_time": "1605175506",
                    "update_time_ms": "1605175506123",
                    "event": "finish",
                    "currency_pair": self.ex_trading_pair,
                    "type": order.order_type.name.lower(),
                    "account": "spot",
                    "side": order.trade_type.name.lower(),
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "time_in_force": "gtc",
                    "left": "0",
                    "filled_total": str(order.amount),
                    "fee": "0.00200000000000",
                    "fee_currency": self.quote_asset,
                    "point_fee": "0",
                    "gt_fee": "0",
                    "gt_discount": True,
                    "rebated_fee": "0",
                    "rebated_fee_currency": "USDT",
                    "finish_as": "filled",
                }
            ]
        }

        filled_event_message = {
            "time": 1605176741,
            "channel": "spot.usertrades",
            "event": "update",
            "result": [
                {
                    "id": 5736713,
                    "user_id": 1000001,
                    "order_id": order.exchange_order_id,
                    "currency_pair": self.ex_trading_pair,
                    "create_time": 1605176741,
                    "create_time_ms": "1605176741123.456",
                    "side": order.trade_type.name.lower(),
                    "amount": str(order.amount),
                    "role": "taker",
                    "price": "10035.00000000",
                    "fee": "0.00200000000000",
                    "fee_currency": self.quote_asset,
                    "point_fee": "0",
                    "gt_fee": "0",
                    "text": order.client_order_id
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [order_event_message, filled_event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

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
        self.assertEqual(Decimal(filled_event_message["result"][0]["price"]), fill_event.price)
        self.assertEqual(Decimal(filled_event_message["result"][0]["amount"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                filled_event_message["result"][0]["fee_currency"],
                Decimal(filled_event_message["result"][0]["fee"]))],
            fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * Decimal(filled_event_message["result"][0]["price"]),
                         buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_update_for_order_partially_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]
        order.current_state = OrderState.OPEN

        event_message = {
            "time": 1605175506,
            "channel": "spot.orders",
            "event": "update",
            "result": [
                {
                    "id": order.exchange_order_id,
                    "user": 123456,
                    "text": order.client_order_id,
                    "create_time": "1605175506",
                    "create_time_ms": "1605175506123",
                    "update_time": "1605175506",
                    "update_time_ms": "1605175506123",
                    "event": "finish",
                    "currency_pair": self.ex_trading_pair,
                    "type": order.order_type.name.lower(),
                    "account": "spot",
                    "side": order.trade_type.name.lower(),
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "time_in_force": "gtc",
                    "left": "0",
                    "filled_total": "0.5",
                    "fee": "0.00200000000000",
                    "fee_currency": self.quote_asset,
                    "point_fee": "0",
                    "gt_fee": "0",
                    "gt_discount": True,
                    "rebated_fee": "0",
                    "rebated_fee_currency": "USDT",
                    "finish_as": "filled",
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.OPEN, order.current_state)

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        event_message = {
            "time": 1605248616,
            "channel": "spot.balances",
            "event": "update",
            "result": [
                {
                    "timestamp": "1605248616",
                    "timestamp_ms": "1605248616123",
                    "user": "1000001",
                    "currency": self.base_asset,
                    "change": "100",
                    "total": "10500",
                    "available": "10000"
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("10500"), self.exchange.get_balance(self.base_asset))

    def test_user_stream_raises_cancel_exception(self):
        self.exchange._set_current_timestamp(1640780000)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout,
            self.exchange._user_stream_event_listener())

    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange._sleep")
    def test_user_stream_logs_errors(self, sleep_mock):
        self.exchange._set_current_timestamp(1640780000)

        incomplete_event = {
            "time": 1605248616,
            "channel": "spot.balances",
            "event": "update",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error in user stream listener loop."
            )
        )

    def test_initial_status_dict(self):
        self.exchange._set_trading_pair_symbol_map(None)

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)
