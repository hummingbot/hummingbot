import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ciex import ciex_constants as CONSTANTS, ciex_web_utils as web_utils
from hummingbot.connector.exchange.ciex.ciex_exchange import CiexExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class CiexExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.exchange._set_trading_pair_symbol_map(bidict({self.exchange_trading_pair.lower(): self.trading_pair}))

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.CIEX_SYMBOLS_PATH)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.CIEX_TICKER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.CIEX_PING_PATH)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.CIEX_SYMBOLS_PATH)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.CIEX_ORDER_PATH)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ACCOUNT_INFO_PATH)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "symbols": [
                {
                    "quantityPrecision": 2,
                    "symbol": self.exchange_trading_pair,
                    "pricePrecision": 6,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                }
            ],
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "high": "24245.63",
            "vol": "566.71548091",
            "last": str(self.expected_latest_price),
            "low": "23674.93",
            "buy": 23986.02,
            "sell": 23987.04,
            "rose": "0.0036385013",
            "time": 1660683590000,
            "open": "23899.95",
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        # There is no filter for symbols in CI-EX connector

        response = {
            "symbols": [
                {
                    "quantityPrecision": 2,
                    "symbol": self.exchange_trading_pair,
                    "pricePrecision": 6,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                }
            ],
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "symbols": [
                {"symbol": self.exchange_trading_pair, "baseAsset": self.base_asset, "quoteAsset": self.quote_asset}
            ],
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "orderId": int(self.expected_exchange_order_id),
            "clientOrderId": "",
            "symbol": self.exchange_trading_pair,
            "transactTime": 1273774892913,
            "price": 10000.0,
            "origQty": 100.0,
            "executedQty": 0.0,
            "type": "LIMIT",
            "side": "BUY",
            "status": "NEW",
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "balances": [
                {"asset": self.base_asset, "free": 10.0, "locked": 5.0},
                {"asset": self.quote_asset, "free": 2000.0, "locked": 0.0},
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "balances": [
                {"asset": self.base_asset, "free": 10.0, "locked": 5.0},
            ]
        }

    @property
    def balance_event_websocket_update(self):
        raise NotImplementedError

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        quantity_precision = self.trading_rules_request_mock_response["symbols"][0]["quantityPrecision"]
        price_precision = self.trading_rules_request_mock_response["symbols"][0]["pricePrecision"]
        min_order_size = Decimal(str(10**-quantity_precision))
        min_quote_amount = Decimal(str(10**-price_precision))

        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_order_size,
            min_order_value=min_order_size * min_quote_amount,
            max_price_significant_digits=price_precision,
            min_base_amount_increment=min_order_size,
            min_quote_amount_increment=min_quote_amount,
            min_price_increment=min_quote_amount,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["symbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "150695552109032492"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        raise NotImplementedError

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return self.expected_fill_fee

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "28457"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return base_token.lower() + quote_token.lower()

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return CiexExchange(
            client_config_map=client_config_map,
            ciex_api_key=self.api_key,
            ciex_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("Content-Type", request_headers)
        self.assertIn("X-CH-APIKEY", request_headers)
        self.assertEqual(self.api_key, request_headers["X-CH-APIKEY"])
        self.assertIn("X-CH-TS", request_headers)
        self.assertIn("X-CH-SIGN", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertEqual("LIMIT", request_data["type"])
        self.assertEqual(float(order.amount), Decimal(request_data["volume"]))
        self.assertEqual(float(order.price), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["newClientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(json.loads(request_call.kwargs["data"]))
        self.assertEqual(self.exchange_trading_pair.lower(), request_data["symbol"])
        self.assertEqual(order.client_order_id, request_data["newClientOrderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self.assertEqual(self.exchange_trading_pair.lower(), request_params["symbol"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual("1000", request_params["limit"])

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CIEX_CANCEL_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CIEX_CANCEL_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": "-1145", "msg": "The order status does not allow cancellation", "data": None}
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Implement the expected not found response when enabling test_cancel_order_not_found_in_the_exchange
        raise NotImplementedError

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Implement the expected not found response when enabling
        # test_lost_order_removed_if_not_found_during_order_status_update
        raise NotImplementedError

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ORDER_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CIEX_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.CIEX_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ORDER_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=512, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CIEX_ORDER_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CIEX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_cancelled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self.configure_canceled_order_status_response(order=order, mock_api=mock_api, callback=callback)

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_partially_filled_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_partially_canceled_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def trade_event_for_partial_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError

    def _expected_initial_status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": True,
        }

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("HTTP status is 429")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    def test_create_order_fails_with_exchange_code_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url

        creation_response = {
            "code": "-1000",
            "msg": "An unknown error occurred while processing the request",
            "data": None,
        }

        mock_api.post(
            url, body=json.dumps(creation_response), callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        order_to_validate_request = InFlightOrder(
            client_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            creation_timestamp=self.exchange.current_timestamp,
            price=Decimal("10000"),
        )
        self.validate_order_creation_request(order=order_to_validate_request, request_call=order_request)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)",
            )
        )

    def test_user_stream_update_for_canceled_order(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_lost_order_user_stream_full_fill_events_are_processed(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_user_stream_logs_errors(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_user_stream_raises_cancel_exception(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_user_stream_update_for_new_order(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_user_stream_update_for_order_full_fill(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    def test_user_stream_update_for_partially_cancelled_order(self):
        #  CI-EX connector does not have user stream data source or user stream tracker
        pass

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        # Reimplementing this test because CI-EX implements cancel_all using batch cancels

        self.exchange._set_current_timestamp(1640780000)
        expected_correctly_cancelled_oids = []
        expected_exchange_oid_to_cancel_first_batch = []

        for iteration in range(0, CONSTANTS.MAX_ORDERS_PER_BATCH_CANCEL):
            self.exchange.start_tracking_order(
                order_id=str(10 + iteration),
                exchange_order_id=str(110 + iteration),
                trading_pair=self.trading_pair,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
            )

            self.assertIn(str(10 + iteration), self.exchange.in_flight_orders)
            expected_correctly_cancelled_oids.append(str(10 + iteration))
            expected_exchange_oid_to_cancel_first_batch.append(str(110 + iteration))

        self.exchange.start_tracking_order(
            order_id="92",
            exchange_order_id="192",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("12", self.exchange.in_flight_orders)

        url = web_utils.private_rest_url(CONSTANTS.CIEX_BATCH_CANCEL_ORDERS_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        successful_response = {
            "success": list(map(lambda exchange_oid: int(exchange_oid), expected_exchange_oid_to_cancel_first_batch))
        }
        mock_api.post(regex_url, body=json.dumps(successful_response))
        erroneous_response = {"code": "-1145", "msg": "The order status does not allow cancellation", "data": None}
        mock_api.post(regex_url, body=json.dumps(erroneous_response))

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(cancel_request)

        request_data = json.loads(cancel_request.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(expected_exchange_oid_to_cancel_first_batch, request_data["orderIds"])

        for oid in expected_correctly_cancelled_oids:
            self.assertIn(CancellationResult(oid, True), cancellation_results)

        self.assertIn(CancellationResult("92", False), cancellation_results)

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during cancellation (check _is_order_not_found_during_cancelation_error)
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during status update (check _is_order_not_found_during_status_update_error)
        pass

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "status": "CANCELED",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": float(order.price),
            "origQty": float(order.amount),
            "executedQty": float(order.amount),
            "avgPrice": float(order.price + Decimal(2)),
            "type": "LIMIT",
            "side": order.trade_type.name.upper(),
            "status": CONSTANTS.FILLED_STATUS,
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "list": [
                {
                    "symbol": self.exchange_trading_pair,
                    "id": int(self.expected_fill_trade_id),
                    "bidId": int(order.exchange_order_id),
                    "askId": 150695552109032493,
                    "price": float(order.price),
                    "qty": float(order.amount),
                    "time": 1499865549590,
                    "isBuyer": True,
                    "isMaker": True,
                    "feeCoin": self.expected_fill_fee.flat_fees[0].token,
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                }
            ]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": float(order.price),
            "origQty": float(order.amount),
            "executedQty": 0.0,
            "avgPrice": 0.0,
            "type": "LIMIT",
            "side": order.trade_type.name.upper(),
            "status": CONSTANTS.CANCELED_STATUS,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": float(order.price),
            "origQty": float(order.amount),
            "executedQty": 0.0,
            "avgPrice": 0.0,
            "type": "LIMIT",
            "side": order.trade_type.name.upper(),
            "status": CONSTANTS.NEW_STATUS,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair,
            "price": float(order.price),
            "origQty": float(order.amount),
            "executedQty": float(self.expected_partial_fill_amount),
            "avgPrice": float(self.expected_partial_fill_price),
            "type": "LIMIT",
            "side": order.trade_type.name.upper(),
            "status": CONSTANTS.PARTIALLY_FILLED_STATUS,
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "list": [
                {
                    "symbol": self.exchange_trading_pair,
                    "id": int(self.expected_fill_trade_id),
                    "bidId": int(order.exchange_order_id),
                    "askId": 150695552109032493,
                    "price": float(self.expected_partial_fill_price),
                    "qty": float(self.expected_partial_fill_amount),
                    "time": 1499865549590,
                    "isBuyer": True,
                    "isMaker": True,
                    "feeCoin": self.expected_partial_fill_fee.flat_fees[0].token,
                    "fee": float(self.expected_partial_fill_fee.flat_fees[0].amount),
                }
            ]
        }

    # TODO: Add tests that updates the order statuses when a subsequent order status update interval is reached
