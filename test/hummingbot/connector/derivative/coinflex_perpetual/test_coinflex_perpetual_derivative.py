import asyncio
import functools
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, NamedTuple, Optional
from unittest.mock import AsyncMock, patch

import pandas as pd
import ujson
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_api_order_book_data_source import (
    CoinflexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_derivative import CoinflexPerpetualDerivative
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils import get_new_client_order_id
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, MarketOrderFailureEvent, OrderCancelledEvent, OrderFilledEvent


class CoinflexPerpetualDerivativeUnitTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "coinflex_perpetual_testnet"

        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = CoinflexPerpetualDerivative(
            client_config_map=self.client_config_map,
            coinflex_perpetual_api_key="testAPIKey",
            coinflex_perpetual_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.symbol: self.trading_pair
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._client_order_tracker.logger().setLevel(1)
        self.exchange._client_order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

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

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.symbol: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def _validate_auth_credentials_for_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="params"
        )

    def _validate_auth_credentials_for_post_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple,
                                                                   params_key: str):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("Timestamp", request_headers)
        self.assertIn("Signature", request_headers)
        self.assertIn("Nonce", request_headers)
        self.assertIn("AccessKey", request_headers)
        self.assertEqual("testAPIKey", request_headers["AccessKey"])

    def _get_regex_url(self,
                       endpoint,
                       return_url=False,
                       endpoint_api_version=None,
                       public=False):
        prv_or_pub = web_utils.public_rest_url if public else web_utils.private_rest_url
        url = prv_or_pub(endpoint, domain=self.domain, endpoint_api_version=endpoint_api_version)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?").replace("{}", r".*"))
        if return_url:
            return url, regex_url
        return regex_url

    def _get_mock_order_data(self,
                             order,
                             status="OrderMatched",
                             price="10000.0",
                             amount="1.0",
                             is_matched=True,
                             trade_id="448528458527567630",
                             fee_asset=None,
                             fill_base_amount="1.0",
                             fill_price="10000.0",
                             fee_paid="-0.00440786"):
        order_data = {
            "status": status,
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "marketCode": self.symbol,
            "side": order.trade_type.name,
            "orderType": "LIMIT",
            "price": order.price,
            "quantity": order.amount,
            "remainQuantity": "0.0",
            "timeInForce": "GTC",
            "orderOpenedTimestamp": "1499827319559",
            "orderClosedTimestamp": "1499827319559",
        }
        if is_matched:
            order_data["matchIds"] = [{}]
            order_data["matchIds"][0][trade_id] = {
                "matchQuantity": fill_base_amount,
                "matchPrice": fill_price,
                "timestamp": "1499827319559",
                "orderMatchType": "TAKER",
            }
            order_data["fees"] = {
                f"{fee_asset}": fee_paid
            }

        return {
            "data": [order_data]
        }

    def _get_mock_user_stream_order_data(self,
                                         order=None,
                                         trade_id=-1,
                                         client_order_id=None,
                                         status="OPEN",
                                         side="BUY",
                                         price="1000.00000000",
                                         amount="1.00000000",
                                         is_matched=False,
                                         fill_base_amount="0.00000000",
                                         fill_price="0.00000000",
                                         fee_asset=None,
                                         fee_paid="0"):

        order_data = {
            "clientOrderId": client_order_id or order.client_order_id,
            "orderId": int(order.exchange_order_id if order and order.exchange_order_id else 1),
            "timestamp": 1499405658658,
            "status": status,
            "side": side if not order else order.trade_type.name,
            "price": price if not order else order.price,
            "quantity": amount if not order else order.amount,
        }
        if is_matched:
            order_data["matchId"] = trade_id
            order_data["matchQuantity"] = fill_base_amount
            order_data["matchPrice"] = fill_price
            order_data["fees"] = fee_paid
            order_data["feeInstrumentId"] = fee_asset

        return {
            "table": "order",
            "data": [order_data]
        }

    def _get_mock_trading_rule_data(self,
                                    margin_asset = None,
                                    min_order_size = "0.001",
                                    min_price_increment = "1",
                                    invalid=False):
        margin_asset = margin_asset or self.quote_asset

        trading_rule = {
            "marketId": "2001000000000",
            "marketCode": self.symbol,
            "name": f"{self.base_asset}/{margin_asset} Perp",
            "referencePair": f"{self.base_asset}/{margin_asset}",
            "base": f"{self.base_asset}",
            "counter": f"{margin_asset}",
            "type": "FUTURE",
            "tickSize": f"{min_price_increment}",
            "qtyIncrement": f"{min_order_size}",
            "marginCurrency": f"{margin_asset}",
            "contractValCurrency": f"{self.base_asset}",
            "upperPriceBound": "41580",
            "lowerPriceBound": "38380",
            "marketPrice": "39980",
            "markPrice": None,
            "listingDate": 1593316800000,
            "endDate": 0,
            "marketPriceLastUpdated": 1645265706110,
            "markPriceLastUpdated": 0
        }

        if invalid:
            trading_rule = {"type": "SPOT"}

        return {
            "event": "markets",
            "timestamp": 1565246363776,
            "data": [trading_rule]
        }

    def _get_mock_balance_data(self,
                               asset="USDT",
                               free="23.72469206",
                               total="23.72469206",
                               with_second=False):
        balances = [
            {
                "instrumentId": asset,
                "available": free,
                "total": total
            }
        ]

        if with_second:
            balances.append({
                "instrumentId": "BUSD",
                "available": "100.12345678",
                "total": "103.12345678"
            })
        return {
            "table": "balance",
            "data": balances
        }

    def _get_snapshot_response(self, update_id=1027024):
        resp = {
            "event": "depthL1000",
            "timestamp": update_id,
            "data": [{
                "bids": [
                    [
                        "4.00000000",
                        "431.00000000"
                    ]
                ],
                "asks": [
                    [
                        "4.00000200",
                        "12.00000000"
                    ]
                ],
                "marketCode": self.symbol,
                "timestamp": update_id,
            }]
        }
        return resp

    def _get_mock_login_message(self):
        resp = {
            "tag": "1234567890",
            "event": "login",
            "success": True,
            "timestamp": "1234567890"
        }
        return resp

    def _get_mock_ticker_data(self):
        return [{
            "last": "100.0",
            "open24h": "38719",
            "high24h": "38840",
            "low24h": "36377",
            "volume24h": "3622970.9407847790",
            "currencyVolume24h": "96.986",
            "openInterest": "0",
            "marketCode": "COINALPHA-HBOT",
            "timestamp": "1645546950025",
            "lastQty": "0.086",
            "markPrice": "37645",
            "lastMarkPrice": "37628",
        }]

    def _funding_info_response(self):
        mock_response = [{
            "instrumentId": self.symbol,
            "fundingRate": "0.00010000",
            "timestamp": "2022-04-11 21:00:03",
        }]

        return mock_response

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = {
            "data": [
                {
                    "instrumentId": self.symbol,
                    "quantity": "1",
                    "entryPrice": "10",
                    "markPrice": "11",
                    "positionPnl": "1",
                    "leverage": "1",
                }
            ]
        }
        return positions

    def _get_ws_event_single_position_dict(self) -> Dict[str, Any]:

        return {
            "table": "position",
            "data": self._get_position_risk_api_endpoint_single_position_list()["data"]
        }

    def _get_income_history_dict(self) -> List:
        income_history = {
            "data": [{
                "payment": 1,
                "marketCode": self.symbol,
                "timestamp": self.start_timestamp,
            }]
        }
        return income_history

    def empty_err_msg(self):
        return {'errors': None, 'status': None}

    @aioresponses()
    def test_existing_account_position_detected_on_positions_update(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=ujson.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair, self.symbol)

    @aioresponses()
    def test_account_position_updated_on_positions_update(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=ujson.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        positions["data"][0]["quantity"] = "2"
        req_mock.get(regex_url, body=ujson.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    def test_new_account_position_detected_on_positions_update(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)

        req_mock.get(regex_url, body=ujson.dumps({"data": []}))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=ujson.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    def test_closed_account_position_removed_on_positions_update(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=ujson.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions["data"][0]["quantity"] = "0"
        req_mock.get(regex_url, body=ujson.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_new_account_position_detected_on_stream_event(self, mock_api, ws_connect_mock):

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        position_update = self._get_ws_event_single_position_dict()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(position_update))

        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=ujson.dumps(positions))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_account_position_updated_on_stream_event(self, mock_api, ws_connect_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=ujson.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        account_update = self._get_ws_event_single_position_dict()
        account_update["data"][0]["quantity"] = "2"
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_closed_account_position_removed_on_stream_event(self, mock_api, ws_connect_mock):
        regex_url = self._get_regex_url(CONSTANTS.POSITION_INFORMATION_URL)
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=ujson.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)

        account_update = self._get_ws_event_single_position_dict()
        account_update["data"][0]["quantity"] = "0"
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertEqual(len(self.exchange.account_positions), 0)

    def test_set_position_mode_cannot_change(self):
        self.assertIsNone(self.exchange.position_mode)
        self.exchange.set_position_mode(PositionMode.HEDGE)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    def test_format_trading_rules(self):
        margin_asset = self.quote_asset
        min_order_size = 1
        min_price_increment = 2
        mocked_response = self._get_mock_trading_rule_data(
            margin_asset, min_order_size, min_price_increment
        )

        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_order_size, trading_rule.min_base_amount_increment)
        self.assertEqual(margin_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(margin_asset, trading_rule.sell_order_collateral_token)

    def test_get_collateral_token(self):
        margin_asset = self.quote_asset
        mocked_response = self._get_mock_trading_rule_data(margin_asset)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.assertEqual(margin_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(margin_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                             trade_id=1,
                                                             is_matched=True,
                                                             status="PARTIAL_FILL",
                                                             fill_base_amount="0.1",
                                                             fill_price="10000",
                                                             fee_asset="HBOT",
                                                             fee_paid="20")

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["data"][0]["feeInstrumentId"], Decimal(partial_fill["data"][0]["fees"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = self._get_mock_user_stream_order_data(order=order,
                                                              trade_id=2,
                                                              is_matched=True,
                                                              status="FILLED",
                                                              fill_base_amount="0.9",
                                                              fill_price="10000",
                                                              fee_asset="HBOT",
                                                              fee_paid="30")

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["data"][0]["feeInstrumentId"], Decimal(complete_fill["data"][0]["fees"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_sell_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                             trade_id=1,
                                                             is_matched=True,
                                                             status="PARTIAL_FILL",
                                                             fill_base_amount="0.1",
                                                             fill_price="10000",
                                                             fee_asset=self.quote_asset,
                                                             fee_paid="20")

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["data"][0]["feeInstrumentId"], Decimal(partial_fill["data"][0]["fees"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = self._get_mock_user_stream_order_data(order=order,
                                                              trade_id=2,
                                                              is_matched=True,
                                                              status="FILLED",
                                                              fill_base_amount="0.9",
                                                              fill_price="10000",
                                                              fee_asset="HBOT",
                                                              fee_paid="30")

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["data"][0]["feeInstrumentId"], Decimal(complete_fill["data"][0]["fees"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))

    def test_order_fill_event_ignored_for_repeated_trade_id(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                             trade_id=1,
                                                             is_matched=True,
                                                             status="PARTIAL_FILL",
                                                             fill_base_amount="0.1",
                                                             fill_price="10000",
                                                             fee_asset=self.quote_asset,
                                                             fee_paid="20")

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["data"][0]["feeInstrumentId"], Decimal(partial_fill["data"][0]["fees"]))], fill_event.trade_fee.flat_fees
        )

        repeated_partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                                      trade_id=1,
                                                                      is_matched=True,
                                                                      status="PARTIAL_FILL",
                                                                      fill_base_amount="0.1",
                                                                      fill_price="10000",
                                                                      fee_asset=self.quote_asset,
                                                                      fee_paid="20")

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: repeated_partial_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_fee_is_zero_when_not_included_in_fill_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                             trade_id=1,
                                                             is_matched=True,
                                                             status="PARTIAL_FILL",
                                                             fill_base_amount="0.1",
                                                             fill_price="10000")

        task = self.ev_loop.create_task(self.exchange._process_user_stream_event(event_message=partial_fill))
        self.async_run_with_timeout(task)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))

    def test_order_event_with_cancelled_status_marks_order_as_cancelled(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order,
                                                             trade_id=1,
                                                             is_matched=True,
                                                             status="CANCELED_BY_USER",
                                                             fill_base_amount="0.1",
                                                             fill_price="10000",
                                                             fee_asset=self.quote_asset,
                                                             fee_paid="20")

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        self.assertTrue(self._is_logged(
            "INFO",
            f"Successfully canceled order {order.client_order_id}."
        ))

    def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.test_task)

    def test_user_stream_event_queue_error_is_logged(self):
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error")
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged("NETWORK", "Unknown error. Retrying after 1 seconds."))

    @patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.0)
    def test_user_stream_event_order_not_created_error(self):
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            order_id="OID1",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order)

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                              lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged("ERROR", f"Failed to get exchange order id for order: {order.__dict__}"))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error in user stream listener loop: "))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_derivative."
           "CoinflexPerpetualDerivative.current_timestamp")
    def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )
        inflight_order = self.exchange.in_flight_orders.get("OID1")

        order = self._get_mock_order_data(order=inflight_order,
                                          status="PARTIAL_FILL",
                                          fill_base_amount="0.5")

        regex_url = self._get_regex_url(CONSTANTS.ORDER_STATUS_URL, endpoint_api_version="v2.1")

        req_mock.get(regex_url, body=ujson.dumps(order))

        self.async_run_with_timeout(self.exchange._update_order_status())

        in_flight_orders = self.exchange._client_order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        # Processing an order update SHOULD impact trade fill information
        self.assertEqual(Decimal("0.5"), in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal("5000"), in_flight_orders["OID1"].executed_amount_quote)

        self.assertEqual(1499827319.559, in_flight_orders["OID1"].last_update_timestamp)

        self.assertEqual(1, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    def test_update_order_status_when_cancelled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_STATUS_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = self._get_mock_order_data(order, status="OrderClosed", is_matched=False)

        mock_response = order_status
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.symbol, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
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
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_STATUS_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = self._get_mock_order_data(order, status="REJECT_CANCEL_ORDER_ID_NOT_FOUND", is_matched=False)

        mock_response = order_status
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.symbol, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        expected_err = (
            f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
            f" update_timestamp={int(order_status['data'][0]['orderClosedTimestamp']) * 1e-3}, new_state={repr(OrderState.FAILED)}, "
            f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
            "misc_updates=None)"
        )
        self.assertTrue(self._is_logged("INFO", expected_err))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.constants.API_MAX_RETRIES", new=int(1))
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_update_order_status_when_unauthorised(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_STATUS_URL, return_url=True, endpoint_api_version="v2.1")

        for i in range(2):
            mock_api.get(regex_url, status=401)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.symbol, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        expected_error = {"errors": "Unauthorized", "status": 401}
        self.assertTrue(
            self._is_logged(
                "NETWORK",
                f"Error fetching status update for the order {order.client_order_id}: {expected_error}.")
        )

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.constants.API_MAX_RETRIES", new=int(2))
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_update_order_status_marks_order_as_failure_after_three_not_found(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_STATUS_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = {"data": [{
            "success": "false",
            "message": CONSTANTS.ORDER_NOT_FOUND_ERRORS[0]
        }]}

        for i in range(2 * self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            mock_api.get(regex_url, body=ujson.dumps(order_status))

        for i in range(self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        expected_error = {
            **order_status,
            "errors": CONSTANTS.ORDER_NOT_FOUND_ERRORS[0]
        }
        self.assertTrue(
            self._is_logged(
                "NETWORK",
                f"Error fetching status update for the order {order.client_order_id}, marking as not found: {expected_error}.")
        )

    def test_set_leverage_reports_warning(self):
        leverage = 21

        self.exchange.set_leverage(self.trading_pair, leverage)

        self.assertTrue(self._is_logged("WARNING",
                                        "CoinFLEX does not support setting leverage."))

    @aioresponses()
    def test_fetch_funding_payment_successful(self, req_mock):
        income_history = self._get_income_history_dict()
        regex_url_income_history = self._get_regex_url(CONSTANTS.GET_INCOME_HISTORY_URL)
        req_mock.get(regex_url_income_history, body=ujson.dumps(income_history))

        req_mock.get(self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_URL),
                     status=200,
                     body=ujson.dumps(self._get_mock_ticker_data()))

        funding_info = self._funding_info_response()
        regex_url_funding_info = self._get_regex_url(CONSTANTS.MARK_PRICE_URL)
        req_mock.get(regex_url_funding_info, body=ujson.dumps(funding_info))

        # Fetch from exchange with REST API - safe_ensure_future, not immediately
        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        req_mock.get(regex_url_income_history, body=ujson.dumps(income_history))

        # Fetch once received
        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        self.assertTrue(len(self.funding_payment_completed_logger.event_log) == 1)

        funding_info_logged = self.funding_payment_completed_logger.event_log[0]

        self.assertTrue(funding_info_logged.trading_pair == f"{self.base_asset}-{self.quote_asset}")

        self.assertEqual(funding_info_logged.funding_rate, Decimal(funding_info[0]["fundingRate"]))
        self.assertEqual(funding_info_logged.amount, income_history["data"][0]["payment"])

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_fetch_funding_payment_failed(self, req_mock, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url_income_history = self._get_regex_url(CONSTANTS.GET_INCOME_HISTORY_URL)
        req_mock.get(regex_url_income_history, exception=Exception)

        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        self.assertTrue(self._is_logged(
            "ERROR",
            f"Unexpected error occurred fetching funding payment for {self.trading_pair}. Error: {self.empty_err_msg()}"
        ))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mocked_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_URL)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["OID1"]
        order1.current_state = OrderState.OPEN

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        self.assertIn("OID2", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["OID2"]
        order2.current_state = OrderState.OPEN

        self.exchange.start_tracking_order(
            order_id="OID3",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        self.assertIn("OID3", self.exchange.in_flight_orders)
        order3 = self.exchange.in_flight_orders["OID3"]

        cancel_response = self._get_mock_order_data(order=order1,
                                                    status="CANCELED_BY_USER")
        mocked_api.delete(regex_url, body=ujson.dumps(cancel_response))
        for x in range(CONSTANTS.API_MAX_RETRIES * 2):
            mocked_api.delete(regex_url, status=400)

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._client_order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual(3, len(cancellation_results))
        self.assertIn(CancellationResult(order1.client_order_id, True), cancellation_results)
        self.assertIn(CancellationResult(order2.client_order_id, False), cancellation_results)
        self.assertIn(CancellationResult(order3.client_order_id, False), cancellation_results)

        cancel_event: OrderCancelledEvent = order_cancelled_events[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"There was an error when requesting cancelation of order {order2.client_order_id}"
            )
        )

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_cancel_all_exception(self, req_mock, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_URL)
        req_mock.delete(regex_url, exception=Exception())

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        tracked_order = self.exchange._client_order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "ERROR",
            "There was an error when requesting cancelation of order OID1"
        ))

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

    @aioresponses()
    def test_create_order_successful(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.ORDER_CREATE_URL)

        create_response = {
            "data": [{
                "timestamp": int(self.start_timestamp),
                "status": "OPEN",
                "orderId": "8886774"
            }]
        }

        req_mock.post(regex_url, body=ujson.dumps(create_response))

        margin_asset = self.quote_asset
        mocked_response = self._get_mock_trading_rule_data(margin_asset)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("10000")))

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

    @aioresponses()
    def test_create_order_exception(self, req_mock):
        regex_url = self._get_regex_url(CONSTANTS.ORDER_CREATE_URL)

        req_mock.post(regex_url, exception=Exception())

        margin_asset = self.quote_asset
        mocked_response = self._get_mock_trading_rule_data(margin_asset)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        # The order amount is quantizied
        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Error submitting order to Coinflex Perpetuals for 10000.000 {self.trading_pair} "
            f"1010."
        ))

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

    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 4

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_balances(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)

        response = self._get_mock_balance_data(with_second=True)

        mock_api.get(regex_url, body=ujson.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("23.72469206"), available_balances["USDT"])
        self.assertEqual(Decimal("100.12345678"), available_balances["BUSD"])
        self.assertEqual(Decimal("23.72469206"), total_balances["USDT"])
        self.assertEqual(Decimal("103.12345678"), total_balances["BUSD"])
