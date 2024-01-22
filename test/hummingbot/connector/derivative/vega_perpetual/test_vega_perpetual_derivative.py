import asyncio
import functools
import json
import test.hummingbot.connector.derivative.vega_perpetual.mock_requests as mock_requests
import test.hummingbot.connector.derivative.vega_perpetual.mock_ws as mock_ws
import time
import unittest
from asyncio import exceptions
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_api_order_book_data_source import (
    VegaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_derivative import VegaPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_base import NetworkStatus


class VegaPerpetualDerivativeUnitTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}{cls.quote_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.TESTNET_DOMAIN
        cls.public_key = "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece"  # noqa: mock
        cls.mnemonic = "liberty unfair next zero business small okay insane juice reject veteran random pottery model matter giant artist during six napkin pilot bike immune rigid"  # noqa: mock

        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = VegaPerpetualDerivative(
            client_config_map=self.client_config_map,
            vega_perpetual_public_key=self.public_key,
            vega_perpetual_seed_phrase=self.mnemonic,
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        # so we dont have to deal with throttling stuff
        self.exchange._has_updated_throttler = True

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        VegaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

        self.exchange._best_connection_endpoint = CONSTANTS.TESTNET_BASE_URL

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.exchange._user_stream_tracker.logger().setLevel(1)
        self.exchange._user_stream_tracker.logger().addHandler(self)
        self.exchange._user_stream_tracker.data_source.logger().setLevel(1)
        self.exchange._user_stream_tracker.data_source.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.mock_time_ns = time.time_ns()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        return url

    @property
    def symbols_url(self) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.SYMBOLS_URL, domain=self.domain)
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.PING_URL, domain=self.domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain)
        return url

    @property
    def orders_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_LIST_URL, domain=self.domain)
        return url

    @property
    def order_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.ORDER_URL, domain=self.domain)
        return url

    @property
    def blockchain_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.SERVER_BLOCK_TIME, domain=self.domain)
        return url

    @property
    def positions_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.POSITION_LIST_URL, domain=self.domain)
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.FUNDING_PAYMENTS_URL, domain=self.domain)
        return url

    @property
    def rate_history_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.FUNDING_RATE_URL, domain=self.domain)
        return url

    @property
    def risk_factors_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.MARKET_DATA_URL, domain=self.domain)
        return url

    @property
    def trades_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.TRADE_LIST_URL, domain=self.domain)
        return url

    @property
    def submit_transaction_url(self):
        url = web_utils.short_url(CONSTANTS.TRANSACTION_POST_URL, domain=self.domain)
        return url

    @property
    def last_trade_price_url(self):
        path_url = f"{CONSTANTS.TICKER_PRICE_URL}/COIN_ALPHA_HBOT_MARKET_ID/{CONSTANTS.RECENT_SUFFIX}"
        url = web_utils.rest_url(path_url, domain=self.domain)
        return url

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        VegaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _is_logged_contains(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_blockchain_timestamp_rest_mock(self) -> Dict[str, Any]:
        blockchain_timestamp_rest_response = {
            "timestamp": "1697015092507003000"
        }
        return blockchain_timestamp_rest_response

    # NOTE: This will be for both cancel and place
    def _get_submit_transaction_rest_response_generic_success_mock(self) -> Dict[str, Any]:
        submit_raw_transaction_rest_response = {
            "code": 0,
            "data": "",
            "height": "16228313",
            "log": "",
            "success": True,
            "txHash": "9BA8358800D4E4BDA7C6E30521452164B4F0F3F3F251C669118049B0CE89D560"  # noqa: mock
        }
        return submit_raw_transaction_rest_response

    # NOTE: This will be for both cancel and place
    def _get_submit_transaction_rest_response_generic_failure_mock(self) -> Dict[str, Any]:
        submit_raw_transaction_rest_response = {
            "code": 3,
            "message": "illegal base64 data at input byte 4",
            "details": []
        }
        return submit_raw_transaction_rest_response

    def _get_submit_transaction_rest_response_cancel_order_failure_mock(self) -> Dict[str, Any]:
        submit_raw_transaction_rest_response = {
            "code": 13,
            "message": "Internal error",
            "details": [
                {
                    "@type": "type.googleapis.com/vega.ErrorDetail",
                    "code": 10000,
                    "message": "tx already exists in cache",
                    "inner": ""
                }
            ]
        }
        return submit_raw_transaction_rest_response

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _setup_symbols(self, mock_api):
        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})
        task = self.ev_loop.create_task(self.exchange._populate_symbols())
        self.async_run_with_timeout(task)

    def _setup_markets(self, mock_api):
        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.all_symbols_url,
                     body=json.dumps(mock_requests._get_exchange_info_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._populate_exchange_info())
        self.async_run_with_timeout(task)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507003000)
    def test_make_blockchain_check_request(self, mock_api, mock_time):

        timestamp_resp = self._get_blockchain_timestamp_rest_mock()

        # we have to add this twice as the time sync url gets hit twice, once for a time
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        task = self.ev_loop.create_task(self.exchange._make_blockchain_check_request())
        ret = self.async_run_with_timeout(task)
        self.assertTrue(ret)

    @aioresponses()
    def test_check_network_old_block(self, mock_api):
        timestamp_resp = self._get_blockchain_timestamp_rest_mock()
        network_status_resp = mock_requests._get_network_requests_rest_mock()

        mock_api.get(self.network_status_url, body=json.dumps(network_status_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        task = self.ev_loop.create_task(self.exchange.check_network())

        ret = self.async_run_with_timeout(task)

        self.assertEqual(NetworkStatus.STOPPED, ret)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507006000)
    # @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_derivative.Vegexchange._user_stream_tracker._user_stream._ws_connected', True)
    def test_check_network_failed_blockchain_check_no_block(self, mock_api, mock_time):
        timestamp_resp = self._get_blockchain_timestamp_rest_mock()
        network_status_resp = mock_requests._get_network_requests_rest_mock()

        mock_api.get(self.network_status_url, body=json.dumps(network_status_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        # mock_api.get(self.blockchain_url, body=json.dumps(""))
        task = self.ev_loop.create_task(self.exchange.check_network())

        ret = self.async_run_with_timeout(task)

        self.assertEqual(NetworkStatus.STOPPED, ret)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507006000)
    def test_check_network_failed_blockchain_check_bad_data(self, mock_api, mock_time):
        timestamp_resp = self._get_blockchain_timestamp_rest_mock()
        network_status_resp = mock_requests._get_network_requests_rest_mock()

        mock_api.get(self.network_status_url, body=json.dumps(network_status_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(""))
        task = self.ev_loop.create_task(self.exchange.check_network())

        ret = self.async_run_with_timeout(task)

        self.assertEqual(NetworkStatus.NOT_CONNECTED, ret)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507003000)
    def test_check_network_fail(self, mock_api, mock_time):
        # this will 404 on the time request
        # timestamp_resp = self._get_blockchain_timestamp_rest_mock()
        # mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        # mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))

        task = self.ev_loop.create_task(self.exchange.check_network())

        ret = self.async_run_with_timeout(task)

        self.assertEqual(NetworkStatus.STOPPED, ret)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507003000)
    def test_check_network(self, mock_api, mock_time):
        timestamp_resp = self._get_blockchain_timestamp_rest_mock()
        network_status_resp = mock_requests._get_network_requests_rest_mock()

        mock_api.get(self.network_status_url, body=json.dumps(network_status_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        mock_api.get(self.blockchain_url, body=json.dumps(timestamp_resp))
        task = self.ev_loop.create_task(self.exchange.check_network())

        ret = self.async_run_with_timeout(task)

        self.assertEqual(NetworkStatus.CONNECTED, ret)

    @aioresponses()
    def test_stop_network(self, mock_api):

        task = self.ev_loop.create_task(self.exchange.stop_network())
        self.async_run_with_timeout(task, 10)

    @aioresponses()
    def test_get_collateral_token(self, mock_api):
        self._setup_markets(mock_api)
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.ex_trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.ex_trading_pair)

        self.assertEqual(buy_collateral_token, "HBOT")
        self.assertEqual(sell_collateral_token, "HBOT")

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    def test_supported_position_modes(self):
        linear_connector = self.exchange
        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    @aioresponses()
    @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth.VegaPerpetualAuth.sign_payload', return_value="FAKE_SIGNATURE".encode('utf-8'))
    def test_place_order(self, mock_api, mock_signature):
        self._setup_markets(mock_api)

        mock_api.post(self.submit_transaction_url,
                      body=json.dumps(mock_requests.get_transaction_success_mock()),
                      headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._place_order(
            order_id="FAKE_ORDER_ID",
            trading_pair=self.ex_trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("2000"),
            position_action=PositionAction.OPEN))
        self.async_run_with_timeout(task)

    @aioresponses()
    @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth.VegaPerpetualAuth.sign_payload', return_value="FAKE_SIGNATURE".encode('utf-8'))
    def test_place_cancel(self, mock_api, mock_signature):
        self._setup_markets(mock_api)
        o = InFlightOrder(client_order_id= "FAKE_CLIENT_ID",
                          trading_pair=self.ex_trading_pair,
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id="FAKE_EXCHANGE_ID",
                          initial_state=OrderState.OPEN)
        self.exchange._order_tracker.start_tracking_order(o)

        mock_api.post(self.submit_transaction_url,
                      body=json.dumps(mock_requests.get_transaction_success_mock()),
                      headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._place_cancel(
            order_id="FAKE_ORDER_ID",
            tracked_order=o))
        self.async_run_with_timeout(task)

    @aioresponses()
    @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth.VegaPerpetualAuth.sign_payload', return_value="FAKE_SIGNATURE".encode('utf-8'))
    def test_place_cancel_missing_exchange_order_id(self, mock_api, mock_signature):
        self._setup_markets(mock_api)
        o = InFlightOrder(client_order_id= "FAKE_CLIENT_ID",
                          trading_pair=self.ex_trading_pair,
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id="FAKE_CLIENT_ID",
                          initial_state=OrderState.CREATED)

        mock_api.post(self.submit_transaction_url,
                      body=json.dumps(mock_requests.get_transaction_success_mock()),
                      headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._place_cancel(
            order_id="FAKE_CLIENT_ID",
            tracked_order=o))
        self.async_run_with_timeout(task)

    # @aioresponses()
    # @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth.VegaPerpetualAuth.sign_payload', return_value="FAKE_SIGNATURE".encode('utf-8'))
    # @patch('hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils.get_current_server_time', return_value=1000000000.00)
    # def test_place_cancel_missing_exchange_order_id_tx_failed(self, mock_api, mock_signature, mock_server_time):
    #     self._setup_markets(mock_api)
    #     o = InFlightOrder(client_order_id= "FAKE_CLIENT_ID",
    #                       trading_pair=self.ex_trading_pair,
    #                       order_type= OrderType.LIMIT,
    #                       trade_type= TradeType.BUY,
    #                       amount= Decimal(1.0),
    #                       creation_timestamp= 10000.0,
    #                       exchange_order_id="FAKE_CLIENT_ID",
    #                       initial_state=OrderState.CREATED)

    #     mock_api.post(self.submit_transaction_url,
    #                   body=json.dumps(mock_requests.get_transaction_failure_mock()),
    #                   headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

    #     task = self.ev_loop.create_task(self.exchange._place_cancel(
    #         order_id="FAKE_CLIENT_ID",
    #         tracked_order=o))
    #     self.async_run_with_timeout(task)

    @aioresponses()
    def test_set_leverage(self, mock_api):
        self._setup_markets(mock_api)

        mock_api.get(self.risk_factors_url + "/COIN_ALPHA_HBOT_MARKET_ID/risk/factors",
                     body=json.dumps(mock_requests.get_risk_factors_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._set_trading_pair_leverage(self.trading_pair, 30))
        succes, msg = self.async_run_with_timeout(task)

        self.assertEqual(succes, True)

    @aioresponses()
    @patch('time.time_ns', return_value=1697015092507003000)
    def test_last_fee_payment(self, mock_api, mock_time):
        self._setup_markets(mock_api)

        mock_api.get(self.funding_payment_url + "?partyId=f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                     body=json.dumps(mock_requests._get_user_last_funding_payment_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        start_timestamp = int(time.time_ns() - (self.exchange.funding_fee_poll_interval * 1e+9 * 2))
        mock_api.get(self.rate_history_url + f"/COIN_ALPHA_HBOT_MARKET_ID?dateRange.startTimestamp={start_timestamp}",
                     body=json.dumps(mock_requests.get_funding_periods()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._fetch_last_fee_payment(self.ex_trading_pair))

        timestamp, funding_rate, payment = self.async_run_with_timeout(task)

        self.assertEqual(timestamp, float(1697724166.111149))
        self.assertEqual(funding_rate, Decimal("-0.0014109983417459"))
        self.assertEqual(payment, Decimal("0.00000000000470078"))

    @aioresponses()
    def test_update_balances(self, mock_api):
        self._setup_markets(mock_api)

        position_url = f"{self.positions_url}?filter.marketIds=COIN_ALPHA_HBOT_MARKET_ID&filter.partyIds=f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece"  # noqa: mock
        mock_api.get(position_url,
                     body=json.dumps(mock_requests._get_user_positions_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.balance_url + "?filter.partyIds=f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                     body=json.dumps(mock_requests._get_user_balances_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        self.exchange._exchange_info = None
        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.all_symbols_url,
                     body=json.dumps(mock_requests._get_exchange_info_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._update_balances())

        self.async_run_with_timeout(task)

        bal1 = self.exchange._account_balances["HBOT"]
        expected1 = Decimal("1.5E-10")

        self.assertEqual(expected1, bal1)

        bal2 = self.exchange._account_balances["COINALPHA"]
        expected2 = Decimal("5000.00")
        self.assertEqual(expected2, bal2)

    @aioresponses()
    def test_all_trade_updates_for_order(self, mock_api):
        self._setup_markets(mock_api)
        o = InFlightOrder(client_order_id= "FAKE_CLIENT_ID",
                          trading_pair=self.trading_pair,
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id="FAKE_EXCHANGE_ID",
                          initial_state=OrderState.CREATED)
        self.exchange._order_tracker.start_tracking_order(o)
        self.exchange._exchange_order_id_to_hb_order_id["FAKE_EXCHANGE_ID"] = o.client_order_id

        mock_api.get(self.trades_url + f"?partyIds=f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece&orderIds={o.exchange_order_id}",  # noqa: mock
                     body=json.dumps(mock_requests._get_user_trades_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._all_trade_updates_for_order(o))

        trade_update = self.async_run_with_timeout(task)

        self.assertIsNotNone(trade_update)
        self.assertTrue(len(trade_update) > 0)
        self.assertIsInstance(trade_update[0], TradeUpdate)

    @aioresponses()
    def test_request_order_status_with_code(self, mock_api):
        self._setup_markets(mock_api)
        o = InFlightOrder(client_order_id="FAKE_CLIENT_ID",
                          trading_pair=self.trading_pair,
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id="FAKE_EXCHANGE_ID",
                          initial_state=OrderState.CREATED)

        mock_api.get(self.order_url + f"/{o.exchange_order_id}",
                     body=json.dumps(mock_requests._get_user_orders_with_code_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        self.exchange._order_tracker.start_tracking_order(o)

        # task = self.ev_loop.create_task(self.exchange._request_order_status(exchange_order_id="FAKE_EXCHANGE_ID"))

        # NOTE: This below makes it work when commented out (we'll return nothing)
        self.exchange._exchange_order_id_to_hb_order_id["BUYER_ORDER_ID"] = o.client_order_id
        mock_api.get(self.orders_url + f"?filter.reference={o.client_order_id}",
                     body=json.dumps(mock_requests._get_user_orders_with_code_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        # task = self.ev_loop.create_task(self.exchange._request_order_status(tracked_order=o))

    @aioresponses()
    def test_request_order_status(self, mock_api):
        self._setup_markets(mock_api)
        o = InFlightOrder(client_order_id="FAKE_CLIENT_ID",
                          trading_pair=self.ex_trading_pair,
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id=None,
                          initial_state=OrderState.CREATED)
        self.exchange._order_tracker.start_tracking_order(o)
        # NOTE: This below makes it work when commented out (we'll return nothing)
        self.exchange._exchange_order_id_to_hb_order_id["BUYER_ORDER_ID"] = o.client_order_id
        mock_api.get(self.orders_url + f"?filter.reference={o.client_order_id}",
                     body=json.dumps(mock_requests._get_user_orders_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._request_order_status(tracked_order=o))

        order_update = self.async_run_with_timeout(task)

        self.assertIsInstance(order_update, OrderUpdate)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_error(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.exchange._user_stream_tracker.data_source._connector._best_connection_endpoint = "wss://test.com"

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        error_payload = mock_ws.ws_connect_error()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(error_payload))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected data in user stream"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_invalid_data(self, ws_connect_mock):

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.exchange._user_stream_tracker.data_source._connector._best_connection_endpoint = "wss://test.com"
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        error_payload = mock_ws.ws_invalid_data()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(error_payload))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected data in user stream"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.mocking_assistant.add_websocket_aiohttp_exception(ws_connect_mock.return_value, exception=Exception("test exception"))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged_contains(
            "ERROR",
            "Websocket closed"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_cancel_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.exchange._user_stream_tracker.data_source._connector._best_connection_endpoint = "wss://test.com"
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.mocking_assistant.add_websocket_aiohttp_exception(ws_connect_mock.return_value, exception=asyncio.CancelledError)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged_contains(
            "ERROR",
            "Websocket closed"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_user_stream_event_listener_raises_cancelled_error(self, ws_connect_mock):

        task = self.ev_loop.create_task(self.exchange._user_stream_tracker.start())
        self.assertRaises(exceptions.TimeoutError, self.async_run_with_timeout, task)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_account_snapshot(self, mock_api, ws_connect_mock):

        self._setup_symbols(mock_api)
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        account_update = mock_ws.account_snapshot_update()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        bal1 = self.exchange._account_balances["COINALPHA"]
        expected1 = Decimal(3500)
        self.assertEqual(bal1, expected1)

        bal2 = self.exchange._account_balances["HBOT"]
        expected2 = Decimal(1)
        self.assertEqual(bal2, expected2)

    @aioresponses()
    def test_ws_trade(self, mock_api):

        self._setup_markets(mock_api)
        client_order_id = "REFERENCE_ID"
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id="TRDER.ID_BUYER",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        self.exchange._exchange_order_id_to_hb_order_id["ORDER.ID_BUYER"] = client_order_id

        mock_data = mock_ws.trades_update()
        mock_data["channel_id"] = "trades"

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: mock_data)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        # ensure we were see that we were filled
        tracked_order: InFlightOrder = self.exchange._order_tracker.all_fillable_orders.get(client_order_id, None)
        if tracked_order is None:
            self.assertTrue(False, "Order was not tracked")
            return

        self.assertEqual(tracked_order.executed_amount_base, Decimal("0.03"))

    @aioresponses()
    def test_ws_trade_seller(self, mock_api):

        self._setup_markets(mock_api)
        client_order_id = "REFERENCE_ID"
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id="TRDER.ID_SELLER",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        self.exchange._exchange_order_id_to_hb_order_id["ORDER.ID_SELLER"] = client_order_id

        mock_data = mock_ws.trades_update()
        mock_data["channel_id"] = "trades"

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: mock_data)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        # ensure we were see that we were filled
        tracked_order: InFlightOrder = self.exchange._order_tracker.all_fillable_orders.get(client_order_id, None)
        if tracked_order is None:
            self.assertTrue(False, "Order was not tracked")
            return

        self.assertEqual(tracked_order.executed_amount_base, Decimal("0.00"))

    @aioresponses()
    def test_ws_position(self, mock_api):

        self._setup_markets(mock_api)

        mock_data = mock_ws.position_update_status()
        mock_data["channel_id"] = "positions"

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: mock_data)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        # ensure we did not track this order
        self.assertEqual(len(self.exchange._perpetual_trading.account_positions), 0)

    @aioresponses()
    def test_ws_order_unknown(self, mock_api):

        self._setup_markets(mock_api)

        mock_data = mock_ws.orders_update()
        mock_data["channel_id"] = "orders"

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: mock_data)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        # ensure we did not track this order
        self.assertEqual(len(self.exchange._order_tracker.all_fillable_orders), 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_account_update(self, mock_api, ws_connect_mock):

        self._setup_symbols(mock_api)

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        account_update = mock_ws.account_update()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        bal1 = self.exchange._account_balances["HBOT"]
        expected1 = Decimal(1)
        self.assertEqual(bal1, expected1)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_update_order(self, mock_api, ws_connect_mock):
        self._setup_symbols(mock_api)
        self._setup_markets(mock_api)

        self.exchange.start_tracking_order(
            order_id="REFERENCE_ID",
            exchange_order_id="TEST_ORDER_ID",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        mock_api.get(self.orders_url + "?filter.liveOnly=true&filter.partyIds=f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                     body=json.dumps(mock_requests._get_user_orders_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._update_order_status())
        self.async_run_with_timeout(task)

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("REFERENCE_ID" in in_flight_orders)
        self.assertEqual("REFERENCE_ID", in_flight_orders["REFERENCE_ID"].client_order_id)

    @aioresponses()
    def test_populate_exchange_info(self, mock_api):

        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.all_symbols_url,
                     body=json.dumps(mock_requests._get_exchange_info_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._populate_exchange_info())
        exchange_info = self.async_run_with_timeout(task)

        self.assertIn("COIN_ALPHA_HBOT_MARKET_ID", exchange_info)

        for key, m in exchange_info.items():
            self.assertIsNotNone(m.id)
            self.assertIsNotNone(m.symbol)

    @aioresponses()
    def test_populate_symbols(self, mock_api):
        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})
        task = self.ev_loop.create_task(self.exchange._populate_symbols())
        self.async_run_with_timeout(task)

        self.assertIn("HBOT_ASSET_ID", self.exchange._assets_by_id)
        self.assertIn("COINALPHA_ASSET_ID", self.exchange._assets_by_id)

    def test_do_housekeeping(self):
        self.exchange._exchange_order_id_to_hb_order_id["FAKE_EXCHANGE_ID"] = "FAKE_CLIENT_ID"

        self.exchange._exchange_order_id_to_hb_order_id["FAKE_EXCHANGE_ID_BAD"] = "FAKE_CLIENT_ID_BAD"

        o = InFlightOrder(client_order_id= "FAKE_CLIENT_ID",
                          trading_pair= "FAKE_ID",
                          order_type= OrderType.LIMIT,
                          trade_type= TradeType.BUY,
                          amount= Decimal(1.0),
                          creation_timestamp= 10000.0,
                          exchange_order_id="FAKE_EXCHANGE_ID")
        self.exchange._order_tracker.start_tracking_order(o)
        self.exchange._do_housekeeping()

        self.assertIn("FAKE_EXCHANGE_ID", self.exchange._exchange_order_id_to_hb_order_id)

        self.assertNotIn("FAKE_EXCHANGE_ID_BAD", self.exchange._exchange_order_id_to_hb_order_id)

    @aioresponses()
    def test_funding_fee_poll_interval(self, mock_api):
        self._setup_markets(mock_api)
        self.assertEqual(300, self.exchange.funding_fee_poll_interval)

    @aioresponses()
    def test_start_network(self, mock_api):
        self._setup_markets(mock_api)

        network_status_resp = mock_requests._get_network_requests_rest_mock()

        mock_api.get(self.network_status_url, body=json.dumps(network_status_resp))

        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.all_symbols_url,
                     body=json.dumps(mock_requests._get_exchange_info_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange.start_network())
        self.async_run_with_timeout(task)

        self.assertGreater(len(self.exchange._assets_by_id), 0)
        self.assertGreater(len(self.exchange._exchange_info), 0)
        self.assertIn("COINALPHA_ASSET_ID", self.exchange._assets_by_id)
        self.assertIn("COIN_ALPHA_HBOT_MARKET_ID", self.exchange._exchange_info)

    @aioresponses()
    def test_get_last_traded_price(self, mock_api):
        self._setup_markets(mock_api)

        mock_api.get(self.last_trade_price_url,
                     body=json.dumps(mock_requests._get_last_trade()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.exchange._get_last_traded_price(self.ex_trading_pair))
        last_price = self.async_run_with_timeout(task)
        self.assertEqual(last_price, 29.04342)

    @aioresponses()
    def test_format_trading_rules(self, mock_api):
        self._setup_markets(mock_api)
        task = self.ev_loop.create_task(self.exchange._format_trading_rules(self.exchange._exchange_info))

        trading_rules = self.async_run_with_timeout(task)

        self.assertIsInstance(trading_rules, List)
        self.assertTrue(len(trading_rules) > 0)
        self.assertIsInstance(trading_rules[0], TradingRule)

    def test_constants(self):
        # really unneeded but?
        self.assertEqual(self.exchange.client_order_id_max_length, CONSTANTS.MAX_ORDER_ID_LEN)
        self.assertEqual(self.exchange.client_order_id_prefix, CONSTANTS.BROKER_ID)
        self.assertEqual(self.exchange.trading_rules_request_path, CONSTANTS.EXCHANGE_INFO_URL)
        self.assertEqual(self.exchange.check_network_request_path, CONSTANTS.PING_URL)

        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(None))
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(None))
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(None))
        self.assertFalse(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.exchange._update_trading_fees()

    @aioresponses()
    def test_collateral_tokens(self, mock_api):
        self._setup_markets(mock_api)
        self.assertEqual(self.exchange.get_buy_collateral_token(self.ex_trading_pair), "HBOT")
        self.assertEqual(self.exchange.get_sell_collateral_token(self.ex_trading_pair), "HBOT")

    @aioresponses()
    def test_get_fee(self, mock_api):
        self._setup_markets(mock_api)
        fee = self.exchange._get_fee(base_currency="COINALPHA", quote_currency="HBOT", order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(1), is_maker= True)
        self.assertEqual(fee.percent, Decimal("0.0002"))
