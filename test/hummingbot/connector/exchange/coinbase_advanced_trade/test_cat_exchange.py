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
from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS, cat_web_utils as web_utils
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_data_converters import (
    cat_product_to_trading_rule,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeCancelOrdersResponse,
    CoinbaseAdvancedTradeGetMarketTradesResponse,
    CoinbaseAdvancedTradeGetOrderResponse,
    CoinbaseAdvancedTradeGetProductResponse,
    CoinbaseAdvancedTradeListAccountsResponse,
    CoinbaseAdvancedTradeListFillsResponse,
    CoinbaseAdvancedTradeListProductsResponse,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_cumulative_trade import (
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange import CoinbaseAdvancedTradeExchange
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import (
    get_timestamp_from_exchange_time,
    set_exchange_time_from_timestamp,
)
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderCancelledEvent, OrderFilledEvent


class CoinbaseAdvancedTradeExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ALL_PAIRS_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.PAIR_TICKER_24HR_EP.format(product_id=f"{self.base_asset}-{self.quote_asset}"),
            domain=CONSTANTS.DEFAULT_DOMAIN)
        url = f"{url}?limit=1"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ALL_PAIRS_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_LIST_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        url = f"{url}?limit=250"
        return url

    @property
    def all_symbols_request_mock_response(self):
        test_substitute = {
            "products": [
                {
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": self.base_asset,
                }
            ]
        }
        return CoinbaseAdvancedTradeListProductsResponse.dict_sample_from_json_docstring(test_substitute)

    @property
    def latest_prices_request_mock_response(self):
        test_substitute = {
            "trades": [
                {
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "price": str(self.expected_latest_price),
                }
            ]
        }
        return CoinbaseAdvancedTradeGetMarketTradesResponse.dict_sample_from_json_docstring(test_substitute)

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        test_substitute = {
            "products": [
                {
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": self.base_asset,
                },
                {
                    "product_id": self.exchange_symbol_for_tokens("INVALID", self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": "INVALID",
                }
            ]
        }
        return "INVALID-PAIR", CoinbaseAdvancedTradeListProductsResponse.dict_sample_from_json_docstring(
            test_substitute)

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "data": {
                "iso": "2015-06-23T18:02:51Z",
                "epoch": 1435082571
            }
        }

    @property
    def trading_rules_request_mock_response(self):
        test_substitute = {
            "products": [
                {
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": self.base_asset,
                },
                {
                    "product_id": self.exchange_symbol_for_tokens("BTC", self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": "BTC",
                },
            ],
            "num_products": 2,
        }
        return CoinbaseAdvancedTradeListProductsResponse.dict_sample_from_json_docstring(test_substitute)

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "products": [
                {
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_currency_id": self.quote_asset,
                    "base_currency_id": self.base_asset,
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "order_id": self.expected_exchange_order_id,
            "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "BUY",
            "client_order_id": "OID1"
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        test_substitutes = {
            "accounts":
                [
                    {
                        "uuid": "1",
                        "currency": self.base_asset,
                        "available_balance": {
                            "value": "10",
                            "currency": self.base_asset
                        },
                        "hold": {
                            "value": "15",
                            "currency": self.base_asset
                        }
                    },
                    {
                        "uuid": "2",
                        "currency": self.quote_asset,
                        "available_balance": {
                            "value": "2000",
                            "currency": self.quote_asset
                        },
                        "hold": {
                            "value": "2000",
                            "currency": self.quote_asset
                        }
                    }
                ],
            "has_next": False,
            "cursor": "0",
            "size": 2
        }
        return CoinbaseAdvancedTradeListAccountsResponse.dict_sample_from_json_docstring(test_substitutes)

    @property
    def balance_request_mock_response_only_base(self):
        test_substitutes = {
            "accounts":
                [
                    {
                        "uuid": "1",
                        "currency": self.base_asset,
                        "available_balance": {
                            "value": "10",
                            "currency": self.base_asset
                        },
                        "hold": {
                            "value": "15",
                            "currency": self.base_asset
                        }
                    },
                ],
            "has_next": False,
            "cursor": "0",
            "size": 1
        }
        return CoinbaseAdvancedTradeListAccountsResponse.dict_sample_from_json_docstring(test_substitutes)

    @property
    def balance_event_websocket_update(self):
        return {}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return cat_product_to_trading_rule(
            CoinbaseAdvancedTradeGetProductResponse(**self.trading_rules_request_mock_response["products"][0]))

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        # Coinbase Advanced Trade does not return trading rules for invalid pairs.
        return "Error getting all trading pairs from Coinbase Advanced Trade."

    @property
    def expected_exchange_order_id(self):
        return 28

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

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
            percent_token='USD',
            flat_fees=[TokenAmount(token='USD', amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return "1111-11111-111111"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return CoinbaseAdvancedTradeExchange(
            client_config_map=client_config_map,
            coinbase_advanced_trade_api_key="testAPIKey",
            coinbase_advanced_trade_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["product_id"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertTrue("limit_limit_gtc" in request_data["order_configuration"])
        self.assertEqual(Decimal("100"), Decimal(request_data["order_configuration"]["limit_limit_gtc"]["base_size"]))
        self.assertEqual(Decimal("10000"),
                         Decimal(request_data["order_configuration"]["limit_limit_gtc"]["limit_price"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["order_ids"][0])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual({}, request_params)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["product_id"])
        self.assertEqual(order.exchange_order_id, str(request_params["order_id"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.BATCH_CANCEL_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.BATCH_CANCEL_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.BATCH_CANCEL_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancel_request_not_found_error_mock_response(order=order)
        mock_api.post(regex_url, status=400, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        urls = []
        url = web_utils.private_rest_url(CONSTANTS.FILLS_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"fills": []}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        urls.append(url)

        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        urls.append(url)
        return urls

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_EP)
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
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_EP)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FILLS_EP)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return CoinbaseAdvancedTradeCumulativeUpdate(**{
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.exchange_order_id,
            "status": "OPEN",
            "trading_pair": self.trading_pair,
            "fill_timestamp": 1499405658.658,
            "average_price": Decimal("0"),
            "cumulative_base_amount": Decimal("0"),
            "remainder_base_amount": Decimal(str(order.amount)),
            "cumulative_fee": "0",
            "is_taker": False,
        })

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return CoinbaseAdvancedTradeCumulativeUpdate(**{
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.exchange_order_id,
            "status": "CANCELLED",
            "trading_pair": self.trading_pair,
            "fill_timestamp": 1499405658.658,
            "average_price": Decimal("10"),
            "cumulative_base_amount": Decimal("10"),
            "remainder_base_amount": Decimal(str(order.amount)),
            "cumulative_fee": "0",
            "is_taker": False,
        })

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return CoinbaseAdvancedTradeCumulativeUpdate(**{
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.exchange_order_id,
            "status": "FILLED",
            "trading_pair": self.trading_pair,
            "fill_timestamp": 1499405659.658,
            "average_price": Decimal(str(order.price)),
            "cumulative_base_amount": order.amount,
            "remainder_base_amount": Decimal("0"),
            "cumulative_fee": Decimal(str(self.expected_fill_fee.flat_fees[0].amount)),
            "is_taker": False,
        })

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def in_log(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    def test_user_stream_balance_update(self):
        # Coinbase Advanced Trade does not emit balance update events
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = web_utils.public_rest_url(
            CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=str(self.expected_exchange_order_id)))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        test_substitutes = {
            "order":
                {
                    "order_id": self.expected_exchange_order_id,
                    "status": "UNKNOWN_ORDER_STATUS"
                }
        }

        response = CoinbaseAdvancedTradeGetOrderResponse.dict_sample_from_json_docstring(test_substitutes)

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        if self.is_order_fill_http_update_included_in_status_update:
            # This is done for completeness reasons (to have a response available for the trades request)
            self.configure_erroneous_http_fill_trade_response(order=order, mock_api=mock_api)

        self.configure_order_not_found_error_order_status_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)

        self.assertFalse(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [1640000003, 1640000003, 1640000003]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"data": {"iso": "2021-12-20T11:33:23.000Z", "epoch": 1640000003}}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["data"]["epoch"], self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
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

        url = web_utils.private_rest_url(CONSTANTS.FILLS_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "entry_id": "22222-2222222-22222222",
            "trade_id": "1111-11111-111111",
            "order_id": order.exchange_order_id,
            "trade_time": "2021-05-31T09:59:59Z",
            "trade_type": "FILL",
            "price": "10000.00",
            "size": "0.001",
            "commission": "1.25",
            "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "sequence_timestamp": "2021-05-31T09:58:59Z",
            "liquidity_indicator": "UNKNOWN_LIQUIDITY_INDICATOR",
            "size_in_quote": False,
            "user_id": "3333-333333-3333333",
            "side": "BUY"
        }
        trade_fill_non_tracked_order = {
            "entry_id": "22222-2222222-22222222",
            "trade_id": "1111-11111-111111",
            "order_id": "123456",
            "trade_time": "2021-05-31T09:59:59Z",
            "trade_type": "FILL",
            "price": "10000.00",
            "size": "0.001",
            "commission": "1.25",
            "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "sequence_timestamp": "2021-05-31T09:58:59Z",
            "liquidity_indicator": "UNKNOWN_LIQUIDITY_INDICATOR",
            "size_in_quote": False,
            "user_id": "3333-333333-3333333",
            "side": "BUY"
        }

        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["order_id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["product_id"])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["size"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(self.quote_asset, Decimal(trade_fill["commission"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(get_timestamp_from_exchange_time(trade_fill_non_tracked_order["trade_time"], "s"),
                         fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["size"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                self.quote_asset,
                Decimal(trade_fill_non_tracked_order["commission"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self.is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_api):
        self.exchange._set_current_timestamp(0)
        self.exchange._last_poll_timestamp = -1

        url = web_utils.private_rest_url(CONSTANTS.FILLS_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["product_id"])
        self.assertNotIn("start_sequence_timestamp", request_params)

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        self.exchange._last_trades_poll_timestamp = 10
        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, url)[1]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["product_id"])
        self.assertEqual(set_exchange_time_from_timestamp(10), request_params["start_sequence_timestamp"])

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = web_utils.private_rest_url(CONSTANTS.FILLS_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill_non_tracked_order = {
            "entry_id": "22222-2222222-22222222",
            "trade_id": "1111-11111-111111",
            "order_id": "OID99",
            "trade_time": "2021-05-31T09:59:59Z",
            "trade_type": "FILL",
            "price": "10000.00",
            "size": "0.001",
            "commission": "1.25",
            "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "sequence_timestamp": "2021-05-31T09:58:59Z",
            "liquidity_indicator": "UNKNOWN_LIQUIDITY_INDICATOR",
            "size_in_quote": False,
            "user_id": "3333-333333-3333333",
            "side": "BUY"
        }

        mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["order_id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["product_id"])

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(float(get_timestamp_from_exchange_time(trade_fill_non_tracked_order["trade_time"], "s")),
                         fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["size"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(self.quote_asset,
                        Decimal(trade_fill_non_tracked_order["commission"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self.is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        mock_api.clear()  # Clear registered responses at the start of the test.

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

        url = web_utils.private_rest_url(CONSTANTS.FILLS_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "order": {
                "order_id": order.exchange_order_id,
                "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "user_id": "2222-000000-000000",
                "order_configuration": {
                    "limit_limit_gtc": {
                        "base_size": "0.001",
                        "limit_price": "10000.00",
                        "post_only": False
                    },
                },
                "side": "BUY",
                "client_order_id": "11111-000000-000000",
                "status": "FAILED",
                "time_in_force": "UNKNOWN_TIME_IN_FORCE",
                "created_time": "2021-05-31T09:59:59Z",
                "completion_percentage": "50",
                "filled_size": "0.001",
                "average_filled_price": "50",
                "fee": "string",
                "number_of_fills": "2",
                "filled_value": "10000",
                "pending_cancel": True,
                "size_in_quote": False,
                "total_fees": "5.00",
                "size_inclusive_of_fees": False,
                "total_value_after_fees": "string",
                "trigger_status": "UNKNOWN_TRIGGER_STATUS",
                "order_type": "UNKNOWN_ORDER_TYPE",
                "reject_reason": "REJECT_REASON_UNSPECIFIED",
                "settled": "boolean",
                "product_type": "SPOT",
                "reject_message": "string",
                "cancel_message": "string",
                "order_placement_source": "RETAIL_ADVANCED"
            },
            "updateTime": 1640780000.0
        }
        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        # Timestamp for the call is not available
        self.assertTrue(
            self.in_log(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
            )
        )
        self.assertTrue(
            self.in_log(
                "INFO",
                f", new_state={repr(OrderState.FAILED)}, "
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

        # event_message = {
        #     "channel": "user",
        #     "client_id": "",
        #     "timestamp": "2023-02-09T20:33:57.609931463Z",
        #     "sequence_num": 0,
        #     "events": [
        #         {
        #             "type": "snapshot",
        #             "orders": [
        #                 {
        #                     "order_id": order.exchange_order_id,
        #                     "client_order_id": order.client_order_id,
        #                     "cumulative_quantity": "0",
        #                     "leaves_quantity": "0.000994",
        #                     "avg_price": "0",
        #                     "total_fees": "0",
        #                     "status": "FAILED",
        #                     "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
        #                     "creation_time": "2022-12-07T19:42:18.719312Z",
        #                     "order_side": "BUY",
        #                     "order_type": "Limit"
        #                 },
        #             ]
        #         }
        #     ]
        # }

        cat_event_message = CoinbaseAdvancedTradeCumulativeUpdate(
            exchange_order_id=order.exchange_order_id,
            client_order_id=order.client_order_id,
            status="FAILED",
            trading_pair=f"{self.base_asset}-{self.quote_asset}",
            fill_timestamp=1640780000,
            average_price=Decimal(order.price),
            cumulative_base_amount=Decimal("0"),
            remainder_base_amount=Decimal("0.000994"),
            cumulative_fee=Decimal("0"),
        )

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [cat_event_message, asyncio.CancelledError]
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

    @aioresponses()
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all", new_callable=AsyncMock())
    def test_update_order_status_when_canceled(self, mock_api, fetch_all):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        urls = self.configure_canceled_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            if "fills" not in url:
                self.validate_order_status_request(order=order, request_call=order_status_request)

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all", new_callable=AsyncMock())
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api, fetcher):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
            request_sent_event.set()

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        if self.is_order_fill_http_update_included_in_status_update:
            trades_request = self._all_executed_requests(mock_api, trade_url)[0]
            self.validate_auth_credentials_present(trades_request)
            self.validate_trades_request(
                order=order,
                request_call=trades_request)

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

        request_sent_event.clear()

        # Configure again the response to the order fills request since it is required by lost orders update logic
        self.configure_full_fill_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

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

    #    def test_time_synchronizer_related_request_error_detection(self):
    #        exception = IOError(
    #            "Error executing request POST https://api.coinbase_advanced_trade.com/api/v3/order. HTTP status is 400. "
    #            "Error: {'code':-1021,'msg':'Timestamp for this request is outside of the recvWindow.'}")
    #        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))
    #
    #        exception = IOError(
    #            "Error executing request POST https://api.coinbase_advanced_trade.com/api/v3/order. HTTP status is 400. "
    #            "Error: {'code':-1021,'msg':'Timestamp for this request was 1000ms ahead of the server's "
    #            "time.'}")
    #        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))
    #
    #        exception = IOError(
    #            "Error executing request POST https://api.coinbase_advanced_trade.com/api/v3/order. HTTP status is 400. "
    #            "Error: {'code':-1022,'msg':'Timestamp for this request was 1000ms ahead of the server's "
    #            "time.'}")
    #        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))
    #
    #        exception = IOError(
    #            "Error executing request POST https://api.coinbase_advanced_trade.com/api/v3/order. HTTP status is 400. "
    #            "Error: {'code':-1021,'msg':'Other error.'}")
    #        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    #    @aioresponses()
    #    def test_place_order_manage_server_overloaded_error_unknown_order(self, mock_api):
    #        self.exchange._set_current_timestamp(1640780000)
    #        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
    #        url = web_utils.private_rest_url(CONSTANTS.ORDER_EP)
    #        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
    #        mock_response = {
    #            "error": "internal_server_error",
    #            "code": "500",
    #            "message": "Internal server error",
    #            "details": []
    #        }
    #        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)
    #
    #        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
    #            order_id="test_order_id",
    #            trading_pair=self.trading_pair,
    #            amount=Decimal("1"),
    #            trade_type=TradeType.BUY,
    #            order_type=OrderType.LIMIT,
    #            price=Decimal("2"),
    #        ))
    #        self.assertEqual(o_id, "UNKNOWN")

    # @aioresponses()
    #    def test_place_order_manage_server_overloaded_error_failure(self, mock_api):
    #        self.exchange._set_current_timestamp(1640780000)
    #        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
    #
    #        url = web_utils.private_rest_url(CONSTANTS.ORDER_EP)
    #        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
    #        mock_response = {"code": -1003, "msg": "Service Unavailable."}
    #        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)
    #
    #        self.assertRaises(
    #            IOError,
    #            self.async_run_with_timeout,
    #            self.exchange._place_order(
    #                order_id="test_order_id",
    #                trading_pair=self.trading_pair,
    #                amount=Decimal("1"),
    #                trade_type=TradeType.BUY,
    #                order_type=OrderType.LIMIT,
    #                price=Decimal("2"),
    #            ))
    #
    #        mock_response = {"code": -1003, "msg": "Internal error; unable to process your request. Please try again."}
    #        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)
    #
    #        self.assertRaises(
    #            IOError,
    #            self.async_run_with_timeout,
    #            self.exchange._place_order(
    #                order_id="test_order_id",
    #                trading_pair=self.trading_pair,
    #                amount=Decimal("1"),
    #                trade_type=TradeType.BUY,
    #                order_type=OrderType.LIMIT,
    #                price=Decimal("2"),
    #            ))

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        # self.assertIn("timestamp", params)
        # self.assertIn("signature", params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("CB-ACCESS-KEY", request_headers)
        self.assertEqual("testAPIKey", request_headers["CB-ACCESS-KEY"])

    # def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
    #     substitutes = {
    #                 "success": True,
    #                 "order_id": order.exchange_order_id,
    #             }
    #     return CoinbaseAdvancedTradeCancelOrdersResponse.dict_sample_from_json_docstring(substitutes)["results"][0]

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "results":
                [
                    {
                        "success": True,
                        "order_id": order.exchange_order_id,
                    }
                ]
        }
        return CoinbaseAdvancedTradeCancelOrdersResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_cancel_request_not_found_error_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "results":
                [
                    {
                        "success": False,
                        "order_id": order.exchange_order_id,
                        "failure_reason": "UNKNOWN_CANCEL_ORDER"
                    }
                ]
        }
        return CoinbaseAdvancedTradeCancelOrdersResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "order":
                {
                    "order_id": order.exchange_order_id,
                    "client_order_id": order.client_order_id,
                    "status": "FILLED",
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name,
                    "completion_percentage": "100",
                    "filled_size": str(order.amount),
                    "average_filled_price": str(order.price),
                    "order_type": order.order_type.name,
                    "pending_cancel": False,
                }
        }
        return CoinbaseAdvancedTradeGetOrderResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "order":
                {
                    "order_id": order.exchange_order_id,
                    "client_order_id": order.client_order_id,
                    "status": "CANCELLED",
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name,
                    "completion_percentage": "50",
                    "filled_size": str(order.amount),
                    "average_filled_price": str(order.price),
                    "order_type": order.order_type.name,
                }
        }
        return CoinbaseAdvancedTradeGetOrderResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "order":
                {
                    "order_id": order.exchange_order_id,
                    "client_order_id": order.client_order_id,
                    "status": "OPEN",
                    "product_id": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name,
                    "completion_percentage": "50",
                    "filled_size": str(order.amount),
                    "average_filled_price": str(order.price),
                    "order_type": order.order_type.name,
                }
        }
        return CoinbaseAdvancedTradeGetOrderResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        test_substitutes = {
            "order": {
                "order_id": order.exchange_order_id,
                "product_id": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "side": order.order_type.name.upper(),
                "client_order_id": order.client_order_id,
                "status": "OPEN",
                "completion_percentage": str(self.expected_partial_fill_amount / order.amount * Decimal("100")),
                "filled_size": str(self.expected_partial_fill_amount),
                "average_filled_price": str(self.expected_partial_fill_price),
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "filled_value": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                "total_fees": str(self.expected_fill_fee.flat_fees[0].amount),
                "order_type": order.order_type.name.upper(),
            },
        }
        return CoinbaseAdvancedTradeGetOrderResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        test_substitutes = {
            "fills":
                [
                    {
                        "product_id": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                        "trade_id": self.expected_fill_trade_id,
                        "order_id": order.exchange_order_id,
                        "price": str(self.expected_partial_fill_price),
                        "size": str(self.expected_partial_fill_amount),
                        "size_in_quote": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                        "commission": str(self.expected_fill_fee.flat_fees[0].amount),
                        "side": "BUY",
                    }
                ],
            "cursor": "0"
        }
        return CoinbaseAdvancedTradeListFillsResponse.dict_sample_from_json_docstring(test_substitutes)

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        test_substitutes = {
            "fills":
                [
                    {
                        "product_id": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                        "trade_id": self.expected_fill_trade_id,
                        "order_id": order.exchange_order_id,
                        "price": str(order.price),
                        "size": str(order.amount),
                        "size_in_quote": str(order.amount * order.price),
                        "commission": str(self.expected_fill_fee.flat_fees[0].amount),
                        "side": "BUY",
                    }
                ],
            "cursor": "0"
        }
        return CoinbaseAdvancedTradeListFillsResponse.dict_sample_from_json_docstring(test_substitutes)
