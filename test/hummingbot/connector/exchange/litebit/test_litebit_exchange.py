import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.litebit import litebit_constants as CONSTANTS, litebit_web_utils as web_utils
from hummingbot.connector.exchange.litebit.litebit_exchange import LitebitExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class LitebitExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKETS_PATH)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.GET_TICKERS_PATH)
        url = f"{url}?market={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.GET_TIME_PATH)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.GET_MARKETS_PATH)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_PATH)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.GET_BALANCES_PATH)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                'market': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'status': 'active',
                'step_size': '0.00000001',
                'tick_size': '0.01',
                'minimum_amount_quote': '5.00',
                'base_asset': self.base_asset,
                'quote_asset': self.quote_asset
            },
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "open": "46015.21",
            "last": str(self.expected_latest_price),
            "volume": "27837.51739250",
            "low": "43291.79",
            "high": "46478.14",
            "bid": "44743.95",
            "ask": "44795.47"
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {
                'market': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'status': 'active',
                'step_size': '0.00000001',
                'tick_size': '0.01',
                'minimum_amount_quote': '5.00',
                'base_asset': self.base_asset,
                'quote_asset': self.quote_asset
            },
            {
                'market': self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                'status': 'maintenance',
                'step_size': '0.00000001',
                'tick_size': '0.01',
                'minimum_amount_quote': '5.00',
                'base_asset': "INVALID",
                'quote_asset': "PAIR"
            },
        ]

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"timestamp": 1234567890}

    @property
    def trading_rules_request_mock_response(self):
        return [
            {
                'market': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'status': 'active',
                'step_size': '0.00000001',
                'tick_size': '0.01',
                'minimum_amount_quote': '5.00',
                'base_asset': self.base_asset,
                'quote_asset': self.quote_asset
            },
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [{
            "market": "BTC-EUR",
            "tick_size": "a",
        }]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "uuid": self.expected_exchange_order_id,
            "amount": "0.00100000",
            "amount_filled": "0.00000000",
            "amount_quote": None,
            "amount_quote_filled": "0.00",
            "fee": "0.00",
            "price": "45000.00",
            "side": "buy",
            "type": "limit",
            "status": "open",
            "filled_status": "not_filled",
            "cancel_status": None,
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614598,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": None
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {'available': '2000', 'reserved': '0.00000000', 'total': '2000.00000000', 'asset': self.quote_asset},
            {'available': '10.0', 'reserved': '5.0', 'total': '15.0', 'asset': self.base_asset},
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {'available': '10.0', 'reserved': '5.0', 'total': '15.0', 'asset': self.base_asset},
        ]

    @property
    def balance_event_websocket_update(self):
        return None

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response[0]["step_size"]),
            min_price_increment=Decimal(self.trading_rules_request_mock_response[0]["tick_size"]),
            min_base_amount_increment=Decimal(self.trading_rules_request_mock_response[0]["step_size"]),
            min_notional_size=Decimal(self.trading_rules_request_mock_response[0]["minimum_amount_quote"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "39425691-8209-4134-8b6e-d763bb1c7bcb"

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "9beba3ae-4755-4f06-82be-60b2a3452926"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return LitebitExchange(
            client_config_map=client_config_map,
            litebit_api_key="testAPIKey",
            litebit_secret_key="testSecret",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(OrderType.LIMIT.name.lower(), request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["client_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["orders"][0])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["market"])
        self.assertEqual(order.exchange_order_id, request_params["uuid"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["market"])
        self.assertEqual(order.exchange_order_id, str(request_params["order_uuid"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDERS_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDERS_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "event": "order",
            "data": {
                "uuid": order.exchange_order_id, "amount": str(order.amount),
                "amount_filled": "0.00000000", "amount_quote": None, "amount_quote_filled": "0.00",
                "fee": "0.00", "price": str(order.price), "side": order.trade_type.name.lower(), "type": "limit",
                "status": "open", "filled_status": "not_filled", "cancel_status": None, "stop": None,
                "stop_price": None, "post_only": False, "time_in_force": "gtc", "created_at": 1638967614598,
                "updated_at": 1638967614598, "expire_at": None,
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "client_id": order.client_order_id
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "event": "order",
            "data": {
                "uuid": order.exchange_order_id, "amount": str(order.amount),
                "amount_filled": "0.00000000", "amount_quote": None, "amount_quote_filled": "0.00", "fee": "0.00",
                "price": str(order.price), "side": order.trade_type.name.lower(), "type": "limit", "status": "closed",
                "filled_status": "not_filled", "cancel_status": "cancelled_user",
                "stop": None, "stop_price": None, "post_only": False, "time_in_force": "gtc",
                "created_at": 1638967614598, "updated_at": 1638967614598, "expire_at": None,
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "client_id": order.client_order_id
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "event": "order",
            "data": {
                "uuid": order.exchange_order_id,
                "amount": str(order.amount),
                "amount_filled": str(order.amount),
                "amount_quote": None,
                "amount_quote_filled": str(order.amount * order.price + self.expected_fill_fee.flat_fees[0].amount),
                "fee": "0.11",
                "price": str(order.price),
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "status": "closed",
                "filled_status": "filled",
                "cancel_status": None,
                "stop": None,
                "stop_price": None,
                "post_only": False,
                "time_in_force": "gtc",
                "created_at": 1638967614598,
                "updated_at": 1638967614707,
                "expire_at": None,
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "client_id": order.client_order_id
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "event": "fill",
            "data": {
                "uuid": self.expected_fill_trade_id,
                "order_uuid": order.exchange_order_id,
                "amount": str(order.amount),
                "price": str(order.price),
                "amount_quote": str(order.amount * order.price + self.expected_fill_fee.flat_fees[0].amount),
                "side": order.trade_type.name.lower(),
                "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "liquidity": "taker",
                "timestamp": 1622123573863
            }
        }

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.private_rest_url(CONSTANTS.GET_TIME_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"timestamp": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["timestamp"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = web_utils.private_rest_url(CONSTANTS.GET_TIME_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": 10000, "message": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.GET_TIME_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

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
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "uuid": order.exchange_order_id,
            "amount": str(order.amount),
            "amount_filled": "0.00000000",
            "amount_quote": None,
            "amount_quote_filled": "0.00",
            "fee": "0.00",
            "price": "10000.0",
            "side": "buy",
            "type": "limit",
            "status": "closed",
            "filled_status": "not_filled",
            "cancel_status": "cancelled_self_trade_prevention",
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614598,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": order.client_order_id
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["market"])
        self.assertEqual(order.exchange_order_id, request_params["uuid"])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={order_status['updated_at'] * 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = self.order_event_for_canceled_order_websocket_update(order)
        event_message["data"]["cancel_status"] = "cancelled_self_trade_prevention"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

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

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError(
            "Error executing request POST https://api.exchange.litebit.eu/v1/order. HTTP status is 400. "
            "Error: {'code': 50000, 'message': 'Your request was rejected, because it was received "
            "outside the allowed time window.'}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError(
            "Error executing request POST https://api.exchange.litebit.eu/v1/order. HTTP status is 400. "
            "Error: {'code': 10007, 'message': 'Invalid time window.'}")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("LITEBIT-TIMESTAMP", request_headers)
        self.assertIn("LITEBIT-SIGNATURE", request_headers)
        self.assertIn("LITEBIT-API-KEY", request_headers)
        self.assertEqual("testAPIKey", request_headers["LITEBIT-API-KEY"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return [
            {"uuid": order.exchange_order_id}
        ]

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "uuid": order.exchange_order_id,
            "amount": str(order.amount),
            "amount_filled": str(order.amount),
            "amount_quote": None,
            "amount_quote_filled": str(order.price + Decimal(2)),
            "fee": "0.11",
            "price": str(order.price),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "status": "closed",
            "filled_status": "filled",
            "cancel_status": None,
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614707,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": order.client_order_id
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "uuid": order.exchange_order_id or "dummyOrdId",
            "amount": str(order.amount),
            "amount_filled": "0.00000000",
            "amount_quote": None,
            "amount_quote_filled": "0.00",
            "fee": "0.00",
            "price": str(order.price),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "status": "closed",
            "filled_status": "not_filled",
            "cancel_status": "cancelled_user",
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614598,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": order.client_order_id
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "uuid": self.expected_exchange_order_id,
            "amount": str(order.amount),
            "amount_filled": "0.00000000",
            "amount_quote": None,
            "amount_quote_filled": "0.00",
            "fee": "0.00",
            "price": str(order.price),
            "side": order.trade_type.name.lower(),
            "type": order.order_type.name.lower(),
            "status": "open",
            "filled_status": "not_filled",
            "cancel_status": None,
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614598,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": order.client_order_id
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "uuid": self.expected_exchange_order_id,
            "amount": str(order.amount),
            "amount_filled": str(self.expected_partial_fill_amount),
            "amount_quote": None,
            "amount_quote_filled": str(self.expected_partial_fill_amount * order.price),
            "fee": "0.00",
            "price": str(order.price),
            "side": order.trade_type.name.lower(),
            "type": order.order_type.name.lower(),
            "status": "open",
            "filled_status": "partially_filled",
            "cancel_status": None,
            "stop": None,
            "stop_price": None,
            "post_only": False,
            "time_in_force": "gtc",
            "created_at": 1638967614598,
            "updated_at": 1638967614598,
            "expire_at": None,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "client_id": order.client_order_id
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "uuid": self.expected_fill_trade_id,
                "order_uuid": order.exchange_order_id,
                "amount": str(self.expected_partial_fill_amount),
                "price": str(self.expected_partial_fill_price),
                "amount_quote": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                "side": "buy",
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "liquidity": "taker",
                "timestamp": 1622123573863
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "uuid": self.expected_fill_trade_id,
                "order_uuid": order.exchange_order_id,
                "amount": str(order.amount),
                "price": str(order.price),
                "amount_quote": str(order.amount * order.price + self.expected_fill_fee.flat_fees[0].amount),
                "side": "buy",
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "liquidity": "taker",
                "timestamp": 1622123573863
            }
        ]
