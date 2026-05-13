import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS, backpack_web_utils as web_utils
from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class BackpackExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.exchange._domain)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "baseSymbol": self.base_asset,
                "createdAt": "2025-01-21T06:34:54.691858",
                "filters": {
                    "price": {
                        "borrowEntryFeeMaxMultiplier": None,
                        "borrowEntryFeeMinMultiplier": None,
                        "maxImpactMultiplier": "1.03",
                        "maxMultiplier": "1.25",
                        "maxPrice": None,
                        "meanMarkPriceBand": {
                            "maxMultiplier": "1.03",
                            "minMultiplier": "0.97"
                        },
                        "meanPremiumBand": None,
                        "minImpactMultiplier": "0.97",
                        "minMultiplier": "0.75",
                        "minPrice": "0.01",
                        "tickSize": "0.01"
                    },
                    "quantity": {
                        "maxQuantity": None,
                        "minQuantity": "0.01",
                        "stepSize": "0.01"
                    }
                },
                "fundingInterval": None,
                "fundingRateLowerBound": None,
                "fundingRateUpperBound": None,
                "imfFunction": None,
                "marketType": "SPOT",
                "mmfFunction": None,
                "openInterestLimit": "0",
                "orderBookState": "Open",
                "positionLimitWeight": None,
                "quoteSymbol": self.quote_asset,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "visible": True
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            "firstPrice": "0.8914",
            "high": "0.8914",
            "lastPrice": self.expected_latest_price,
            "low": "0.8769",
            "priceChange": "-0.0124",
            "priceChangePercent": "-0.013911",
            "quoteVolume": "831.1761",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "trades": "11",
            "volume": "942"
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        valid_pair = self.all_symbols_request_mock_response[0]
        invalid_pair = valid_pair.copy()
        invalid_pair["symbol"] = self.exchange_symbol_for_tokens("INVALID", "PAIR")
        invalid_pair["marketType"] = "PERP"
        response = [valid_pair, invalid_pair]
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return "pong"

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        erroneous_trading_rule = self.all_symbols_request_mock_response[0].copy()
        del erroneous_trading_rule["filters"]
        return [erroneous_trading_rule]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            'clientId': 868620826,
            'createdAt': 1507725176595,
            'executedQuantity': '0',
            'executedQuoteQuantity': '0',
            'id': self.expected_exchange_order_id,
            'orderType': 'Limit',
            'postOnly': False,
            'price': '140.99',
            'quantity': '0.01',
            'reduceOnly': None,
            'relatedOrderId': None,
            'selfTradePrevention': 'RejectTaker',
            'side': 'Ask',
            'status': 'New',
            'stopLossLimitPrice': None,
            'stopLossTriggerBy': None,
            'stopLossTriggerPrice': None,
            'strategyId': None,
            'symbol': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            'takeProfitLimitPrice': None,
            'takeProfitTriggerBy': None,
            'takeProfitTriggerPrice': None,
            'timeInForce': 'GTC',
            'triggerBy': None,
            'triggerPrice': None,
            'triggerQuantity': None,
            'triggeredAt': None
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            self.base_asset: {
                'available': '10',
                'locked': '5',
                'staked': '0'
            },
            self.quote_asset: {
                'available': '2000',
                'locked': '0',
                'staked': '0'
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            self.base_asset: {
                'available': '10',
                'locked': '5',
                'staked': '0'
            }
        }

    @property
    def balance_event_websocket_update(self):
        return {}

    async def test_user_stream_balance_update(self):
        """
        Backpack does not provide balance updates through websocket.
        Balance updates are handled via REST API polling.
        """
        pass

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        filters = self.trading_rules_request_mock_response[0]["filters"]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(filters["quantity"]["minQuantity"]),
            min_price_increment=Decimal(filters["price"]["tickSize"]),
            min_base_amount_increment=Decimal(filters["quantity"]["stepSize"]),
            min_notional_size=Decimal("0")
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

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
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        return BackpackExchange(
            backpack_api_key="testAPIKey",
            backpack_api_secret="sKmC5939f6W9/viyhwyaNHa0f7j5wSMvZsysW5BB9L4=",  # Valid 32-byte Ed25519 key
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(self._get_side(order), request_data["side"])
        self.assertEqual(BackpackExchange.backpack_order_type(OrderType.LIMIT), request_data["orderType"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, str(request_data["clientId"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["symbol"])
        self.assertEqual(order.client_order_id, str(request_data["clientId"]))

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["clientId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.exchange_order_id, str(request_params["orderId"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": "RESOURCE_NOT_FOUND", "message": "Not Found"}
        mock_api.delete(regex_url, status=400, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": "RESOURCE_NOT_FOUND", "message": "Not Found"}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "data": {
                "e": "orderAccepted",
                "E": 1694687692980000,
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "c": order.client_order_id,
                "S": self._get_side(order),
                "o": order.order_type.name.upper(),
                "f": "GTC",
                "q": str(order.amount),
                "Q": str(order.amount * order.price),
                "p": str(order.price),
                "P": "21",
                "B": "LastPrice",
                # "a": "30", # Only present if the order has a take-profit trigger price set
                # "b": "10", # Only present if the order has a stop loss trigger price set.
                "j": "30",
                "k": "10",
                # "d": "MarkPrice", # Only present if the order has a take profit trigger price set.
                # "g": "IndexPrice", # Only present if the order has a stop loss trigger price set.
                # "Y": "10", # Only present if the order is a trigger order.
                "X": "New",
                # "R": "PRICE_BAND", # Order expiry reason. Only present if the event is a orderExpired event.
                "i": order.exchange_order_id,
                # "t": 567, # Only present if the event is a orderFill event.
                # "l": "1.23", # Only present if the event is a orderFill event.
                "z": "321",
                "Z": "123",
                # "L": "20", # Only present if the event is a orderFill event.
                # "m": True, # Only present if the event is a orderFill event.
                # "n": "23", # Only present if the event is a orderFill event.
                # "N": "USD", # Only present if the event is a orderFill event.
                "V": "RejectTaker",
                "T": 1694687692989999,
                "O": "USER",
                "I": "1111343026156135",
                "H": 6023471188,
                "y": True,
            },
            "stream": "account.orderUpdate"
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        order_event = self.order_event_for_new_order_websocket_update(order)
        order_event["data"]["X"] = "Cancelled"
        order_event["data"]["e"] = "orderCancelled"
        return order_event

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        order_event = self.order_event_for_new_order_websocket_update(order)
        order_event["data"]["X"] = "Filled"
        order_event["data"]["e"] = "orderFill"
        order_event["data"]["t"] = 378752121  # Trade ID
        order_event["data"]["l"] = str(order.amount)
        order_event["data"]["L"] = str(order.price)
        order_event["data"]["m"] = self._is_maker(order)
        order_event["data"]["n"] = str(self.expected_fill_fee.flat_fees[0].amount)
        order_event["data"]["N"] = self.expected_fill_fee.flat_fees[0].token
        order_event["data"]["Z"] = str(order.amount)
        return order_event

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = 1640000003000

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=500)

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
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
        # Use flexible regex to match URL with any parameter order
        url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")

        response = {"code": "INVALID_ORDER", "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["symbol"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

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

        event_message = {
            "data": {
                "e": "triggerFailed",
                "E": 1694687692980000,
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "c": order.client_order_id,
                "S": self._get_side(order),
                "o": order.order_type.name.upper(),
                "f": "GTC",
                "q": str(order.amount),
                "Q": str(order.amount * order.price),
                "p": str(order.price),
                "X": "TriggerFailed",
                "i": order.exchange_order_id,
                "z": "0",
                "Z": "0",
                "V": "RejectTaker",
                "T": 1694687692989999,
                "O": "USER",
                "I": "1111343026156135",
                "H": 6023471188,
                "y": True,
            },
            "stream": "account.orderUpdate"
        }

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

        # Test buy order - should return uint32 order ID with prefix
        result_buy = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )

        # Verify the order ID starts with the prefix and is a valid numeric string
        self.assertTrue(result_buy.startswith(CONSTANTS.HBOT_ORDER_ID_PREFIX))
        self.assertTrue(result_buy.isdigit())
        # Verify it can be converted to int (uint32 compatible)
        order_id_int = int(result_buy)
        self.assertGreater(order_id_int, 0)
        self.assertLess(order_id_int, 2**32)  # Must fit in uint32

        # Test sell order - should also return uint32 order ID with prefix
        result_sell = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )

        # Verify the order ID starts with the prefix and is a valid numeric string
        self.assertTrue(result_sell.startswith(CONSTANTS.HBOT_ORDER_ID_PREFIX))
        self.assertTrue(result_sell.isdigit())
        # Verify it can be converted to int (uint32 compatible)
        order_id_int = int(result_sell)
        self.assertGreater(order_id_int, 0)
        self.assertLess(order_id_int, 2**32)  # Must fit in uint32

        # Verify buy and sell return different IDs
        self.assertNotEqual(result_buy, result_sell)

    def test_time_synchronizer_related_request_error_detection(self):
        # Test with Backpack's timestamp error format
        exception = IOError("Error executing request POST https://api.backpack.exchange/api/v1/order. HTTP status is 400. "
                            "Error: {'code':'INVALID_CLIENT_REQUEST','message':'Invalid timestamp: must be within 10 minutes of current time'}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        # Test with lowercase timestamp keyword
        exception = IOError("Error executing request POST https://api.backpack.exchange/api/v1/order. HTTP status is 400. "
                            "Error: {'code':'INVALID_CLIENT_REQUEST','message':'timestamp is outside of the recvWindow'}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        # Test with different error code (should not match)
        exception = IOError("Error executing request POST https://api.backpack.exchange/api/v1/order. HTTP status is 400. "
                            "Error: {'code':'INVALID_ORDER','message':'Invalid timestamp: must be within 10 minutes of current time'}")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        # Test with correct code but no timestamp keyword (should not match)
        exception = IOError("Error executing request POST https://api.backpack.exchange/api/v1/order. HTTP status is 400. "
                            "Error: {'code':'INVALID_CLIENT_REQUEST','message':'Other error'}")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": "SERVICE_UNAVAILABLE", "message": "Unknown error, please check your request or try again later."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="1001",  # Must be numeric string since Backpack uses int(order_id)
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_failure(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        # Backpack uses string error codes and "message" field, not Binance's numeric codes and "msg"
        mock_response = {"code": "SERVICE_UNAVAILABLE", "message": "Service Unavailable."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="1002",  # Must be numeric string since Backpack uses int(order_id)
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

        mock_response = {"code": "INTERNAL_ERROR", "message": "Internal error; unable to process your request. Please try again."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="1003",  # Must be numeric string since Backpack uses int(order_id)
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

    def test_format_trading_rules_notional_but_no_min_notional_present(self):
        exchange_info = self.all_symbols_request_mock_response
        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))
        self.assertEqual(result[0].min_notional_size, Decimal("0"))

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        # Backpack uses header-based authentication, not param-based
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-API-Key", request_headers)
        self.assertIn("X-Timestamp", request_headers)
        self.assertIn("X-Window", request_headers)
        self.assertIn("X-Signature", request_headers)
        self.assertIn("X-BROKER-ID", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-API-Key"])

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "clientId": order.client_order_id,
            "createdAt": order.creation_timestamp,
            "executedQuantity": '0',
            "executedQuoteQuantity": '0',
            "id": '26919130763',
            "orderType": "Limit" if self._is_maker(order) else "Market",
            "postOnly": order.order_type == OrderType.LIMIT_MAKER,
            "price": str(order.price),
            "quantity": str(order.amount),
            "reduceOnly": None,
            "relatedOrderId": None,
            "selfTradePrevention": 'RejectTaker',
            "side": self._get_side(order),
            "status": 'New',
            "stopLossLimitPrice": None,
            "stopLossTriggerBy": None,
            "stopLossTriggerPrice": None,
            "strategyId": None,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "takeProfitLimitPrice": None,
            "takeProfitTriggerBy": None,
            "takeProfitTriggerPrice": None,
            "timeInForce": 'GTC',
            "triggerBy": None,
            "triggerPrice": None,
            "triggerQuantity": None,
            "triggeredAt": None
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        order_cancelation_response = self._order_status_request_open_mock_response(order)
        order_cancelation_response["status"] = "Cancelled"
        return order_cancelation_response

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        order_completely_filled_response = self._order_status_request_open_mock_response(order)
        order_completely_filled_response["executedQuantity"] = str(order.executed_amount_base)
        order_completely_filled_response["executedQuoteQuantity"] = str(order.executed_amount_quote)
        order_completely_filled_response["status"] = "Filled"
        return order_completely_filled_response

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        order_partially_filled_response = self._order_status_request_open_mock_response(order)
        order_partially_filled_response["executedQuantity"] = str(self.expected_partial_fill_amount)
        executed_quote_quantity = str(self.expected_partial_fill_amount * self.expected_partial_fill_price)
        order_partially_filled_response["executedQuoteQuantity"] = executed_quote_quantity
        order_partially_filled_response["status"] = "PartiallyFilled"
        return order_partially_filled_response

    def _order_fill_template(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "clientId": order.client_order_id,
            "fee": str(self.expected_fill_fee.flat_fees[0].amount),
            "feeSymbol": self.expected_fill_fee.flat_fees[0].token,
            "isMaker": self._is_maker(order),
            "orderId": order.exchange_order_id,
            "price": str(order.price),
            "quantity": str(order.amount),
            "side": self._get_side(order),
            "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            "systemOrderType": None,
            "timestamp": "2017-07-12T08:05:49.590Z",
            "tradeId": self.expected_fill_trade_id
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        order_fill = self._order_fill_template(order)
        return [order_fill]

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        partial_order_fill = self._order_fill_template(order)
        partial_order_fill["quantity"] = str(self.expected_partial_fill_amount)
        partial_order_fill["price"] = str(self.expected_partial_fill_price)
        return [partial_order_fill]

    @staticmethod
    def _is_maker(order: InFlightOrder):
        return order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @staticmethod
    def _get_side(order: InFlightOrder):
        return "Bid" if order.trade_type == TradeType.BUY else "Ask"

    async def test_user_stream_logs_errors(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="111",
            exchange_order_id="112",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        incomplete_event = {
            "data": {
                "i": "112",
                "c": "111",
                "e": "orderFill",
                "E": 1694687692980000,
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "X": "orderFilled",
            },
            "stream": "account.orderUpdate"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        with patch(f"{type(self.exchange).__module__}.{type(self.exchange).__qualname__}._sleep"):
            try:
                await (self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass
        await asyncio.sleep(0.1)

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error in user stream listener loop."
            )
        )

    def test_real_time_balance_update_disabled(self):
        """
        Test that Backpack exchange has real_time_balance_update set to False
        since it doesn't support balance updates via websocket.
        """
        self.assertFalse(self.exchange.real_time_balance_update)

    @aioresponses()
    def test_update_balances_removes_old_assets(self, mock_api):
        """
        Test that _update_balances removes assets that are no longer present in the response.
        """
        # Set initial balances
        self.exchange._account_balances["OLD_TOKEN"] = Decimal("50")
        self.exchange._account_available_balances["OLD_TOKEN"] = Decimal("40")

        url = self.balance_url
        response = {
            "SOL": {
                "available": "100.5",
                "locked": "10.0"
            }
        }

        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        # OLD_TOKEN should be removed
        self.assertNotIn("OLD_TOKEN", available_balances)
        self.assertNotIn("OLD_TOKEN", total_balances)

        # SOL should be present
        self.assertEqual(Decimal("100.5"), available_balances["SOL"])
        self.assertEqual(Decimal("110.5"), total_balances["SOL"])

    @aioresponses()
    def test_update_balances_handles_empty_response(self, mock_api):
        """
        Test that _update_balances handles empty balance response correctly.
        When account_info is empty/falsy, balances are not updated.
        """
        # Set initial balances
        self.exchange._account_balances["SOL"] = Decimal("100")
        self.exchange._account_available_balances["SOL"] = Decimal("90")

        url = self.balance_url
        response = {}

        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        # With empty response, balances should remain unchanged
        self.assertEqual(Decimal("90"), available_balances["SOL"])
        self.assertEqual(Decimal("100"), total_balances["SOL"])

    def test_user_stream_update_with_missing_client_order_id(self):
        """
        Test that websocket updates work correctly when client_order_id field is missing (None).
        The order should be found by exchange_order_id fallback.
        """
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

        # Event message with missing 'c' field (client_order_id)
        event_message = {
            "data": {
                "e": "orderCancelled",
                "E": 1694687692980000,
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                # "c": missing intentionally
                "S": self._get_side(order),
                "o": order.order_type.name.upper(),
                "f": "GTC",
                "q": str(order.amount),
                "Q": str(order.amount * order.price),
                "p": str(order.price),
                "X": "Cancelled",
                "i": order.exchange_order_id,  # Should use this to find the order
                "z": "0",
                "Z": "0",
                "V": "RejectTaker",
                "T": 1694687692989999,
                "O": "USER",
                "I": "1111343026156135",
                "H": 6023471188,
                "y": True,
            },
            "stream": "account.orderUpdate"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        # Order should be canceled successfully even without client_order_id in the message
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

    def test_user_stream_fill_update_with_missing_client_order_id(self):
        """
        Test that fill updates work correctly when client_order_id field is None.
        """
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="100235",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID2"]

        # Fill event with missing 'c' field
        event_message = {
            "data": {
                "e": "orderFill",
                "E": 1694687692980000,
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                # "c": missing
                "S": self._get_side(order),
                "o": order.order_type.name.upper(),
                "f": "GTC",
                "q": str(order.amount),
                "Q": str(order.amount * order.price),
                "p": str(order.price),
                "X": "Filled",
                "i": order.exchange_order_id,
                "t": 378752121,  # Trade ID
                "l": str(order.amount),
                "L": str(order.price),
                "z": str(order.amount),
                "Z": str(order.amount * order.price),
                "m": False,
                "n": "0.01",
                "N": self.quote_asset,
                "V": "RejectTaker",
                "T": 1694687692989999,
                "O": "USER",
                "I": "1111343026156135",
                "H": 6023471188,
                "y": True,
            },
            "stream": "account.orderUpdate"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        # Order should be filled successfully
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)
        self.assertEqual(order.executed_amount_base, order.amount)
