import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, NamedTuple, Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.hashkey import hashkey_constants as CONSTANTS, hashkey_web_utils as web_utils
from hummingbot.connector.exchange.hashkey.hashkey_api_order_book_data_source import HashkeyAPIOrderBookDataSource
from hummingbot.connector.exchange.hashkey.hashkey_exchange import HashkeyExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class TestHashkeyExchange(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "ETH"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = HashkeyExchange(
            self.client_config_map,
            self.api_key,
            self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        HashkeyAPIOrderBookDataSource._trading_pair_symbol_map = {
            CONSTANTS.DEFAULT_DOMAIN: bidict(
                {self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        HashkeyAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "timezone": "UTC",
            "serverTime": "1703696385826",
            "brokerFilters": [],
            "symbols": [
                {
                    "symbol": "ETHUSD",
                    "symbolName": "ETHUSD",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetName": "ETH",
                    "baseAssetPrecision": "0.0001",
                    "quoteAsset": "USD",
                    "quoteAssetName": "USD",
                    "quotePrecision": "0.0000001",
                    "retailAllowed": True,
                    "piAllowed": True,
                    "corporateAllowed": True,
                    "omnibusAllowed": True,
                    "icebergAllowed": False,
                    "isAggregate": False,
                    "allowMargin": False,
                    "filters": [
                        {
                            "minPrice": "0.01",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.01",
                            "filterType": "PRICE_FILTER"
                        },
                        {
                            "minQty": "0.005",
                            "maxQty": "53",
                            "stepSize": "0.0001",
                            "filterType": "LOT_SIZE"
                        },
                        {
                            "minNotional": "10",
                            "filterType": "MIN_NOTIONAL"
                        },
                        {
                            "minAmount": "10",
                            "maxAmount": "10000000",
                            "minBuyPrice": "0",
                            "filterType": "TRADE_AMOUNT"
                        },
                        {
                            "maxSellPrice": "0",
                            "buyPriceUpRate": "0.2",
                            "sellPriceDownRate": "0.2",
                            "filterType": "LIMIT_TRADING"
                        },
                        {
                            "buyPriceUpRate": "0.2",
                            "sellPriceDownRate": "0.2",
                            "filterType": "MARKET_TRADING"
                        },
                        {
                            "noAllowMarketStartTime": "0",
                            "noAllowMarketEndTime": "0",
                            "limitOrderStartTime": "0",
                            "limitOrderEndTime": "0",
                            "limitMinPrice": "0",
                            "limitMaxPrice": "0",
                            "filterType": "OPEN_QUOTE"
                        }
                    ]
                }
            ],
            "options": [],
            "contracts": [],
            "coins": [
                {
                    "orgId": "9001",
                    "coinId": "BTC",
                    "coinName": "BTC",
                    "coinFullName": "Bitcoin",
                    "allowWithdraw": True,
                    "allowDeposit": True,
                    "chainTypes": [
                        {
                            "chainType": "Bitcoin",
                            "withdrawFee": "0",
                            "minWithdrawQuantity": "0.0005",
                            "maxWithdrawQuantity": "0",
                            "minDepositQuantity": "0.0001",
                            "allowDeposit": True,
                            "allowWithdraw": True
                        }
                    ]
                },
                {
                    "orgId": "9001",
                    "coinId": "ETH",
                    "coinName": "ETH",
                    "coinFullName": "Ethereum",
                    "allowWithdraw": True,
                    "allowDeposit": True,
                    "chainTypes": [
                        {
                            "chainType": "ERC20",
                            "withdrawFee": "0",
                            "minWithdrawQuantity": "0",
                            "maxWithdrawQuantity": "0",
                            "minDepositQuantity": "0.0075",
                            "allowDeposit": True,
                            "allowWithdraw": True
                        }
                    ]
                },
                {
                    "orgId": "9001",
                    "coinId": "USD",
                    "coinName": "USD",
                    "coinFullName": "USD",
                    "allowWithdraw": True,
                    "allowDeposit": True,
                    "chainTypes": []
                }
            ]
        }
        return exchange_rules

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _validate_auth_credentials_present(self, request_call_tuple: NamedTuple):
        request_headers = request_call_tuple.kwargs["headers"]
        request_params = request_call_tuple.kwargs["params"]
        self.assertIn("Content-Type", request_headers)
        self.assertIn("X-HK-APIKEY", request_headers)
        self.assertEqual("application/x-www-form-urlencoded", request_headers["Content-Type"])
        self.assertIn("signature", request_params)

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        resp = {
            "serverTime": 1703695619183
        }
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, ret)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        mock_api.get(url, status=500)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)

        mock_api.get(url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

        resp = self.get_exchange_rules_mock()
        mock_api.get(url, body=json.dumps(resp))
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange._trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        exchange_rules = {
            "timezone": "UTC",
            "serverTime": "1703696385826",
            "brokerFilters": [],
            "symbols": [
                {
                    "symbol": "ETHUSD",
                    "symbolName": "ETHUSD",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetName": "ETH",
                    "baseAssetPrecision": "0.0001",
                    "quoteAsset": "USD",
                    "quoteAssetName": "USD",
                    "quotePrecision": "0.0000001",
                    "retailAllowed": True,
                    "piAllowed": True,
                    "corporateAllowed": True,
                    "omnibusAllowed": True,
                    "icebergAllowed": False,
                    "isAggregate": False,
                    "allowMargin": False,
                    "filters": []
                }
            ],
            "options": [],
            "contracts": [],
        }
        mock_api.get(url, body=json.dumps(exchange_rules))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {self.ex_trading_pair}. Skipping.")
        )

    def test_initial_status_dict(self):
        HashkeyAPIOrderBookDataSource._trading_pair_symbol_map = {}

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

    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self):
        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.000"), fee.percent)  # default fee

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 9

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
        )

        self.assertEqual(result, expected_client_order_id)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "accountId": "32423423423",
            "symbol": "ETHUSD",
            "symbolName": "ETHUSD",
            "clientOrderId": "2343242342",
            "orderId": "23423432423",
            "transactTime": "1703708477519",
            "price": "2222",
            "origQty": "0.04",
            "executedQty": "0.03999",
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "LIMIT",
            "side": "BUY",
            "reqAmount": "0",
            "concentration": ""
        }
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))
        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["symbol"])
        self.assertEqual("BUY", request_params["side"])
        self.assertEqual("LIMIT", request_params["type"])
        self.assertEqual(Decimal("100"), Decimal(request_params["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_params["price"]))
        self.assertEqual("OID1", request_params["newClientOrderId"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order OID1 for {Decimal('100.000000')} {self.trading_pair} "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_limit_maker_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "accountId": "32423423423",
            "symbol": "ETHUSD",
            "symbolName": "ETHUSD",
            "clientOrderId": "2343242342",
            "orderId": "23423432423",
            "transactTime": "1703708477519",
            "price": "2222",
            "origQty": "0.04",
            "executedQty": "0.03999",
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "LIMIT_MAKER",
            "side": "BUY",
            "reqAmount": "0",
            "concentration": ""
        }

        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))
        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT_MAKER,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = order_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_data["symbol"])
        self.assertEqual(TradeType.BUY.name, request_data["side"])
        self.assertEqual("LIMIT_MAKER", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual("OID1", request_data["newClientOrderId"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT_MAKER BUY order OID1 for {Decimal('100.000000')} {self.trading_pair} "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.hashkey.hashkey_exchange.HashkeyExchange.get_price")
    def test_create_market_order_successfully(self, mock_api, get_price_mock):
        get_price_mock.return_value = Decimal(1000)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.MARKET_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        creation_response = {
            "accountId": "32423423423",
            "symbol": "ETHUSD",
            "symbolName": "ETHUSD",
            "clientOrderId": "2343242342",
            "orderId": "23423432423",
            "transactTime": "1703708477519",
            "price": "0",
            "origQty": "0.04",
            "executedQty": "0.03999",
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "MARKET",
            "side": "BUY",
            "reqAmount": "0",
            "concentration": ""
        }
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))
        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.SELL,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.MARKET))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = order_request[1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_data["symbol"])
        self.assertEqual(TradeType.SELL.name, request_data["side"])
        self.assertEqual("MARKET", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual("OID1", request_data["newClientOrderId"])
        self.assertNotIn("price", request_data)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created MARKET SELL order OID1 for {Decimal('100.000000')} {self.trading_pair} "
                f"at {None}."
            )
        )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))
        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))
        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.0001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("0.0001")))
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID2",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.01. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "accountId": "10086",
            "symbol": self.ex_trading_pair,
            "clientOrderId": "1703710745976",
            "orderId": order.exchange_order_id,
            "transactTime": "1703710747523",
            "price": float(order.price),
            "origQty": float(order.amount),
            "executedQty": "0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        }

        mock_api.delete(regex_url,
                        body=json.dumps(response),
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(client_order_id="OID1", trading_pair=self.trading_pair)
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(cancel_request[1][0])

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url,
                        status=400,
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(client_order_id="OID1", trading_pair=self.trading_pair)
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to cancel order {order.client_order_id}"
            )
        )

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "accountId": "10086",
            "symbol": self.ex_trading_pair,
            "clientOrderId": order1.client_order_id,
            "orderId": order1.exchange_order_id,
            "transactTime": "1620811601728",
            "price": float(order1.price),
            "origQty": float(order1.amount),
            "executedQty": "0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        }

        mock_api.delete(regex_url, body=json.dumps(response))

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
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
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "serverTime": 1703740249709
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())
        self.assertEqual(response['serverTime'] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "code": "-1",
            "msg": "error"
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ACCOUNTS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "balances": [
                {
                    "asset": "HKD",
                    "assetId": "HKD",
                    "assetName": "HKD",
                    "total": "2",
                    "free": "2",
                    "locked": "0"
                },
                {
                    "asset": "USD",
                    "assetId": "USD",
                    "assetName": "USD",
                    "total": "3505",
                    "free": "3505",
                    "locked": "0"
                }
            ],
            "userId": "10086"
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("2"), available_balances["HKD"])
        self.assertEqual(Decimal("3505"), available_balances["USD"])

        response = response = {
            "balances": [
                {
                    "asset": "HKD",
                    "assetId": "HKD",
                    "assetName": "HKD",
                    "total": "2",
                    "free": "1",
                    "locked": "0"
                },
                {
                    "asset": "USD",
                    "assetId": "USD",
                    "assetName": "USD",
                    "total": "3505",
                    "free": "3000",
                    "locked": "0"
                }
            ],
            "userId": "10086"
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("USDT", available_balances)
        self.assertNotIn("USDT", total_balances)
        self.assertEqual(Decimal("3000"), available_balances["USD"])
        self.assertEqual(Decimal("3505"), total_balances["USD"])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              10 - 1)

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "accountId": "10086",
            "exchangeId": "301",
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "clientOrderId": order.client_order_id,
            "orderId": order.exchange_order_id,
            "price": "50",
            "origQty": "1",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "cumulativeQuoteQty": "0",
            "avgPrice": "0",
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": order.trade_type.name,
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": "1703710747523",
            "updateTime": "1703710888400",
            "isWorking": True,
            "reqAmount": "0"
        }

        mock_api.get(regex_url, body=json.dumps(order_status))

        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

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
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              10 - 1)

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "accountId": "10086",
            "exchangeId": "301",
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "clientOrderId": order.client_order_id,
            "orderId": order.exchange_order_id,
            "price": "50",
            "origQty": "1",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "cumulativeQuoteQty": "0",
            "avgPrice": "0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": order.trade_type.name,
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": "1703710747523",
            "updateTime": "1703710888400",
            "isWorking": True,
            "reqAmount": "0"
        }

        mock_api.get(regex_url, body=json.dumps(order_status))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              10 - 1)

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "accountId": "10086",
            "exchangeId": "301",
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "clientOrderId": order.client_order_id,
            "orderId": order.exchange_order_id,
            "price": "50",
            "origQty": "1",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "cumulativeQuoteQty": "0",
            "avgPrice": "0",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": order.trade_type.name,
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": "1703710747523",
            "updateTime": "1703710888400",
            "isWorking": True,
            "reqAmount": "0"
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              10 - 1)

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

        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=404)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

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
            "e": "executionReport",        # Event type
            "E": 1499405658658,            # Event time
            "s": order.trading_pair,       # Symbol
            "c": order.client_order_id,    # Client order ID
            "S": order.trade_type.name,    # Side
            "o": "LIMIT",                  # Order type
            "f": "GTC",                    # Time in force
            "q": "1.00000000",             # Order quantity
            "p": "0.10264410",             # Order price
            "reqAmt": "1000",	           # Requested cash amount (To be released)
            "X": "NEW",                    # Current order status
            "d": "1234567890123456789",    # Execution ID
            "i": order.exchange_order_id,  # Order ID
            "l": "0.00000000",             # Last executed quantity
            "r": "0",                      # unfilled quantity
            "z": "0.00000000",             # Cumulative filled quantity
            "L": "0.00000000",             # Last executed price
            "V": "26105.5",                # average executed price
            "n": "0",                      # Commission amount
            "N": None,                     # Commission asset
            "u": True,                     # Is the trade normal, ignore for now
            "w": True,                     # Is the order working? Stops will have
            "m": False,                    # Is this trade the maker side?
            "O": 1499405658657,            # Order creation time
            "Z": "0.00000000"              # Cumulative quote asset transacted quantity
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [[event_message], asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name.upper()} {order.trade_type.name.upper()} order "
                f"{order.client_order_id} for {order.amount} {order.trading_pair} "
                f"at {Decimal('10000')}."
            )
        )

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
            "e": "executionReport",        # Event type
            "E": 1499405658658,            # Event time
            "s": order.trading_pair,       # Symbol
            "c": order.client_order_id,    # Client order ID
            "S": order.trade_type.name,    # Side
            "o": "LIMIT",                  # Order type
            "f": "GTC",                    # Time in force
            "q": "1.00000000",             # Order quantity
            "p": "0.10264410",             # Order price
            "reqAmt": "1000",	           # Requested cash amount (To be released)
            "X": "CANCELED",               # Current order status
            "d": "1234567890123456789",    # Execution ID
            "i": order.exchange_order_id,  # Order ID
            "l": "0.00000000",             # Last executed quantity
            "r": "0",                      # unfilled quantity
            "z": "0.00000000",             # Cumulative filled quantity
            "L": "0.00000000",             # Last executed price
            "V": "26105.5",                # average executed price
            "n": "0",                      # Commission amount
            "N": None,                     # Commission asset
            "u": True,                     # Is the trade normal, ignore for now
            "w": True,                     # Is the order working? Stops will have
            "m": False,                    # Is this trade the maker side?
            "O": 1499405658657,            # Order creation time
            "Z": "0.00000000"              # Cumulative quote asset transacted quantity
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [[event_message], asyncio.CancelledError]
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

        event_message = {
            "e": "executionReport",        # Event type
            "E": 1499405658658,            # Event time
            "s": order.trading_pair,       # Symbol
            "c": order.client_order_id,    # Client order ID
            "S": order.trade_type.name,    # Side
            "o": "LIMIT",                  # Order type
            "f": "GTC",                    # Time in force
            "q": order.amount,             # Order quantity
            "p": order.price,              # Order price
            "reqAmt": "1000",	           # Requested cash amount (To be released)
            "X": "PARTIALLY_FILLED",       # Current order status
            "d": "1234567890123456789",    # Execution ID
            "i": order.exchange_order_id,  # Order ID
            "l": "0.50000000",             # Last executed quantity
            "r": "0",                      # unfilled quantity
            "z": "0.50000000",             # Cumulative filled quantity
            "L": "0.10250000",             # Last executed price
            "V": "26105.5",                # average executed price
            "n": "0.003",                  # Commission amount
            "N": self.base_asset,          # Commission asset
            "u": True,                     # Is the trade normal, ignore for now
            "w": True,                     # Is the order working? Stops will have
            "m": False,                    # Is this trade the maker side?
            "O": 1499405658657,            # Order creation time
            "Z": "473.199"                 # Cumulative quote asset transacted quantity
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [[event_message], asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(event_message["L"]), fill_event.price)
        self.assertEqual(Decimal(event_message["l"]), fill_event.amount)

        self.assertEqual([TokenAmount(amount=Decimal(event_message["n"]), token=(event_message["N"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        self.assertTrue(
            self._is_logged("INFO", f"The {order.trade_type.name} order {order.client_order_id} amounting to "
                                    f"{fill_event.amount}/{order.amount} {order.base_asset} has been filled "
                                    f"at {Decimal('0.10250000')} {self.quote_asset}.")
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

        event_message = {
            "e": "executionReport",        # Event type
            "E": 1499405658658,            # Event time
            "s": order.trading_pair,       # Symbol
            "c": order.client_order_id,    # Client order ID
            "S": order.trade_type.name,    # Side
            "o": "LIMIT",                  # Order type
            "f": "GTC",                    # Time in force
            "q": order.amount,             # Order quantity
            "p": order.price,              # Order price
            "reqAmt": "1000",	           # Requested cash amount (To be released)
            "X": "FILLED",                 # Current order status
            "d": "1234567890123456789",    # Execution ID
            "i": order.exchange_order_id,  # Order ID
            "l": order.amount,             # Last executed quantity
            "r": "0",                      # unfilled quantity
            "z": "0.50000000",             # Cumulative filled quantity
            "L": order.price,              # Last executed price
            "V": "26105.5",                # average executed price
            "n": "0.003",                  # Commission amount
            "N": self.base_asset,          # Commission asset
            "u": True,                     # Is the trade normal, ignore for now
            "w": True,                     # Is the order working? Stops will have
            "m": False,                    # Is this trade the maker side?
            "O": 1499405658657,            # Order creation time
            "Z": "473.199"                 # Cumulative quote asset transacted quantity
        }

        filled_event = {
            "e": "ticketInfo",                # Event type
            "E": "1668693440976",             # Event time
            "s": self.ex_trading_pair,        # Symbol
            "q": "0.001639",                     # quantity
            "t": "1668693440899",             # time
            "p": "441.0",                     # price
            "T": "899062000267837441",        # ticketId
            "o": "899048013515737344",        # orderId
            "c": "1621910874883",             # clientOrderId
            "O": "899062000118679808",        # matchOrderId
            "a": "10086",                     # accountId
            "A": 0,                           # ignore
            "m": True,                        # isMaker
            "S": order.trade_type.name        # side  SELL or BUY
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [[event_message], [filled_event], asyncio.CancelledError]
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
        match_price = Decimal(event_message["L"])
        match_size = Decimal(event_message["l"])
        self.assertEqual(match_price, fill_event.price)
        self.assertEqual(match_size, fill_event.amount)
        self.assertEqual([TokenAmount(amount=Decimal(event_message["n"]), token=(event_message["N"]))],
                         fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * match_price, buy_event.quote_asset_amount)
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

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        event_message = [{
            "e": "outboundAccountInfo",   # Event type
            "E": 1629969654753,           # Event time
            "T": True,                    # Can trade
            "W": True,                    # Can withdraw
            "D": True,                    # Can deposit
            "B": [                        # Balances changed
                {
                    "a": self.base_asset,     # Asset
                    "f": "10000",             # Free amount
                    "l": "500"         # Locked amount
                }
            ]
        }]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances["ETH"])
        self.assertEqual(Decimal("10500"), self.exchange.get_balance("ETH"))

    def test_user_stream_raises_cancel_exception(self):
        self.exchange._set_current_timestamp(1640780000)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout,
            self.exchange._user_stream_event_listener())

    @patch("hummingbot.connector.exchange.hashkey.hashkey_exchange.HashkeyExchange._sleep")
    def test_user_stream_logs_errors(self, _):
        self.exchange._set_current_timestamp(1640780000)

        incomplete_event = {
            "e": "outboundAccountInfo",
            "E": "1629969654753",
            "T": True,
            "W": True,
            "D": True,
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
