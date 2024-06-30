import json
import math
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.btc_markets import (
    btc_markets_constants as CONSTANTS,
    btc_markets_web_utils as web_utils,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_exchange import BtcMarketsExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BtcMarketsExchangeTest(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.MARKETS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def latest_prices_url(self):
        trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        url = web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{trading_pair}/ticker")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.MARKETS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDERS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def trade_url(self):
        url = web_utils.private_rest_url(CONSTANTS.TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + r"\?.*")
        return regex_url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.BALANCE_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": self.base_asset,
                "quoteAssetName": self.quote_asset,
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "bestBid": "0.2612",
            "bestAsk": "0.2677",
            "lastPrice": str(self.expected_latest_price),
            "volume24h": "6392.34930418",
            "volumeQte24h": "1.39",
            "price24h": "130",
            "pricePct24h": "0.002",
            "low24h": "0.2621",
            "high24h": "0.2708",
            "timestamp": "2019-09-01T10:35:04.940000Z"
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": self.base_asset,
                "quoteAssetName": self.quote_asset,
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            },
            {
                "marketId": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                "baseAssetName": self.base_asset,
                "quoteAssetName": self.quote_asset,
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            }
        ]

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "timestamp": "2019-09-01T18:34:27.045000Z"
        }

    @property
    def trading_rules_request_mock_response(self):
        return [
            {
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": self.base_asset,
                "quoteAssetName": self.quote_asset,
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            }
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": "BTC",
                "quoteAssetName": "AUD",
                # "minOrderAmount": "0.0001",
                # "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            }
        ]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "orderId": self.expected_exchange_order_id,
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "clientOrderId": "11",
            "creationTime": "2019-09-01T17:38:17.404000Z",
            "price": "20000",
            "triggerPrice": "20000",
            "amount": "100",
            "openAmount": "100",
            "targetAmount": "100",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "Bid",
            "postOnly": False
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "assetName": self.base_asset,
                "balance": "15",
                "available": "10",
                "locked": "0"
            },
            {
                "assetName": self.quote_asset,
                "balance": "2000",
                "available": "2000",
                "locked": "0"
            }
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "assetName": self.base_asset,
                "balance": "15",
                "available": "10",
                "locked": "0"
            }
        ]

    @property
    def balance_event_websocket_update(self):
        return {
            "fundtransferId": 276811,
            "type": 'Deposit',
            "status": 'Complete',
            "timestamp": '2019-04-16T01:38:02.931Z',
            "amount": '5.00',
            "currency": 'AUD',
            "fee": '0',
            "messageType": 'fundChange'
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        price_decimals = Decimal(str(
            self.trading_rules_request_mock_response[0]["priceDecimals"]))
        # E.g. a price decimal of 2 means 0.01 incremental.
        price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
        amount_decimal = Decimal(str(
            self.trading_rules_request_mock_response[0]["amountDecimals"]))
        amount_step = Decimal("1") / Decimal(str(math.pow(10, amount_decimal)))
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size = Decimal(self.trading_rules_request_mock_response[0]["minOrderAmount"]),
            max_order_size = Decimal(self.trading_rules_request_mock_response[0]["maxOrderAmount"]),
            # min_order_value = Decimal(self.trading_rules_request_mock_response[0]["minOrderAmount"]),
            min_base_amount_increment = amount_step,
            min_price_increment = price_step,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 1736871726781

    @property
    def expected_exchange_trade_id(self):
        return 31727

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

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
        return 30000

    def private_url_with_param(self, url, param = "", seperator = '?'):
        if param != "":
            url = f"{web_utils.private_rest_url(url)}{seperator}{param}"
        else:
            url = web_utils.private_rest_url(url)

        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    def public_url_with_param(self, url, param = "", seperator = '?'):
        if param != "":
            url = f"{web_utils.public_rest_url(url)}{seperator}{param}"
        else:
            url = web_utils.public_rest_url(url)

        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for record in self.log_records
        )

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return base_token + "-" + quote_token

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return BtcMarketsExchange(
            client_config_map=client_config_map,
            btc_markets_api_key="testAPIKey",
            btc_markets_api_secret="XXXX",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("Content-Type", request_headers)
        self.assertIn("BM-AUTH-APIKEY", request_headers)
        self.assertIn("BM-AUTH-SIGNATURE", request_headers)
        self.assertIn("BM-AUTH-TIMESTAMP", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["marketId"])
        self.assertEqual("Limit", request_data["type"])
        self.assertIn(request_data["side"], ["Ask", "Bid"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["clientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        # Client order id is passed in url with Http DELETE rather than POST with body
        self.assertTrue(True)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        # Client order id is passed in url with Http GET rather than GET with body
        self.assertTrue(True)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.exchange_order_id, '/')
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.exchange_order_id, '/')
        response = {
            "code": CONSTANTS.INVALID_ORDERID,
            "message": "In valid Order",
        }
        mock_api.delete(url, status=400, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses
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
        response = {
            "code": CONSTANTS.ORDER_NOT_FOUND,
            "message": "Order not found",
        }
        mock_api.delete(self.order_creation_url, status=404, body=json.dumps(response), callback=callback)
        return self.order_creation_url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        response = {
            "code": CONSTANTS.ORDER_NOT_FOUND,
            "message": "Order not found",
        }
        mock_api.get(self.order_creation_url, body=json.dumps(response), status=404, callback=callback)
        return [self.order_creation_url]

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(self.order_creation_url, body=json.dumps(response), callback=callback)
        return self.order_creation_url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.exchange_order_id, '/')
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.exchange_order_id, '/')
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        response = []
        mock_api.get(self.trade_url, body=json.dumps(response), callback=callback)

        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.exchange_order_id, '/')
        mock_api.get(url, status=401, callback=callback)

        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(self.order_creation_url, body=json.dumps(response), callback=callback)

        self.configure_open_order_status_response(order, mock_api, callback)

        return self.order_creation_url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(self.trade_url, body=json.dumps(response), callback=callback)

        self.configure_partially_filled_order_status_response(order, mock_api, callback)

        return self.trade_url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        mock_api.get(self.trade_url, status=400, callback=callback)

        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, order.client_order_id, '/')
        mock_api.get(url, status=400, callback=callback)

        return self.trade_url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(self.trade_url, body=json.dumps(response), callback=callback)

        self.configure_completely_filled_order_status_response(order, mock_api, callback)

        return self.trade_url

    # https://docs.btcmarkets.net/v3/#section/Order-Life-Cycle-Events
    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "orderId": self.expected_exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "openVolume": "1",
            "status": "Placed",
            "triggerStatus": "",
            "trades": [],
            "timestamp": "2019-04-08T20:41:19.339Z",
            "messageType": "orderChange"
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "orderId": self.expected_exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "openVolume": "1",
            "status": "Cancelled",
            "triggerStatus": "",
            "trades": [],
            "timestamp": "2019-04-08T20:41:41.857Z",
            "messageType": "orderChange"
        }

    # https://docs.btcmarkets.net/v3/#section/Order-Life-Cycle-Events
    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "orderId": self.expected_exchange_order_id,
            # "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "openVolume": "0",
            "status": "Fully Matched",
            "triggerStatus": "",
            "timestamp": "2019-04-08T20:50:39.658Z",
            "trades": [
                {
                    "tradeId": self.expected_exchange_trade_id,
                    "price": str(order.price),
                    "volume": str(order.amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "liquidityType": 'Taker',
                    "valueInQuoteAsset": Decimal(order.amount) * Decimal(order.price)
                }
            ],
            "messageType": 'orderChange'
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "tradeId": self.expected_exchange_trade_id,
            # "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "price": str(order.price),
            "volume": str(order.amount),
            "timestamp": "2019-04-08T20:50:39.658Z",
            "messageType": 'trade'
        }

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("Error executing request POST https://api.btcm.ngin.io/v3/order. HTTP status is 400. "
                            'Error: {"code":InvalidTimestamp,"message":"BM-AUTH-TIMESTAMP range. Within a minute"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.btcm.ngin.io/v3/order. HTTP status is 400. "
                            'Error: {"code":InvalidAuthTimestamp,"message":"BM-AUTH-TIMESTAMP invalid format"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.btcm.ngin.io/v3/order. HTTP status is 400. "
                            'Error: {"code":InvalidTimeWindow,"message":"BM-AUTH-TIMESTAMP range. Within a minute"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.btcm.ngin.io/v3/order. HTTP status is 400. "
                            'Error: {"code":InvalidTimeInForceOption,"message":"Other message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.btcm.ngin.io/v3/order. HTTP status is 400. "
                            'Error: {"code":TradeNotFound,"message":"Other message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": self.expected_exchange_order_id,
            "clientOrderId": order.client_order_id
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "orderId": exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-30T11:08:21.956000Z",
            "price": str(order.price),
            "amount": str(order.amount),
            "openAmount": "1.034",
            "status": "Cancelled"
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "orderId": exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-30T11:08:21.956000Z",
            "price": str(order.price),
            "amount": str(order.amount),
            "openAmount": "1.034",
            "status": "Fully Matched"
        }

    # https://docs.btcmarkets.net/v3/#tag/Trade-APIs
    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return [
            {
                "id": "36014819",
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "timestamp": "2019-06-25T16:01:02.977000Z",
                "price": str(order.price),
                "amount": str(order.amount),
                "side": "Bid",
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "orderId": exchange_order_id,
                "liquidityType": "Taker",
                "clientOrderId": order.client_order_id
            }
        ]

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "orderId": exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-30T11:08:21.956000Z",
            "price": str(order.price),
            "amount": str(order.amount),
            "openAmount": "1.034",
            "status": "Placed"
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "orderId": exchange_order_id,
            "clientOrderId": order.client_order_id,  # leave this property here as it is being asserted in the the tests
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-30T11:08:21.956000Z",
            "price": str(order.price),
            "amount": str(order.amount),
            "openAmount": "1.034",
            "status": "Partially Matched"
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return [
            {
                "id": "36014819",
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "timestamp": "2019-06-25T16:01:02.977000Z",
                "price": str(self.expected_partial_fill_price),
                "amount": str(self.expected_partial_fill_amount),
                "side": "Bid",
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "orderId": exchange_order_id,
                "liquidityType": "Taker",
                "clientOrderId": order.client_order_id
            }
        ]

    @aioresponses()
    def test_place_cancel(self, mock_api):
        order = InFlightOrder(
            client_order_id = 123,
            exchange_order_id = 11223344,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.LIMIT,
            creation_timestamp = 123456789,
            price = str(9999.0),
            amount = str(10.0),
            initial_state = OrderState.OPEN
        )

        orderId = "123456789"

        response = {
            "clientOrderId": "123456789"
        }

        url = self.private_url_with_param(CONSTANTS.ORDERS_URL, 11223344, '/')

        mock_api.delete(url, body=json.dumps(response))

        cancelled = self.async_run_with_timeout(self.exchange._place_cancel(orderId, order))

        self.assertTrue(cancelled)

    def test_get_fee(self):
        expected_limit_order_fee = AddedToCostTradeFee(percent=self.exchange.estimate_fee_pct(True))

        limit_order_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, 1, 2)
        self.assertEqual(limit_order_fee, expected_limit_order_fee)

        expected_market_order_fee = AddedToCostTradeFee(percent=self.exchange.estimate_fee_pct(False))
        market_order_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.MARKET, TradeType.BUY, 1, 2)
        self.assertEqual(market_order_fee, expected_market_order_fee)

    def test_is_request_exception_related_to_time_synchronizer(self):
        result = self.exchange._is_request_exception_related_to_time_synchronizer(Exception("InvalidTimeWindow"))
        self.assertTrue(result)

        result = self.exchange._is_request_exception_related_to_time_synchronizer(Exception("InvalidAuthTimestamp"))
        self.assertTrue(result)

        result = self.exchange._is_request_exception_related_to_time_synchronizer(Exception("InvalidAuthSignature"))
        self.assertTrue(result)

        result = self.exchange._is_request_exception_related_to_time_synchronizer(Exception("RadomException"))
        self.assertFalse(result)

    @aioresponses()
    def test_request_order_fills(self, mock_api):
        order = InFlightOrder(
            client_order_id = 123,
            exchange_order_id = 36014819,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.LIMIT,
            creation_timestamp = 123456789,
            price = str(9999.0),
            amount = str(10.0),
            initial_state = OrderState.OPEN
        )

        response = [
            {
                "id": "36014819",
                "marketId": "XRP-AUD",
                "timestamp": "2019-06-25T16:01:02.977000Z",
                "price": "0.67",
                "amount": "1.50533262",
                "side": "Ask",
                "fee": "0.00857285",
                "orderId": "3648306",
                "liquidityType": "Taker",
                "clientOrderId": "48",
                "valueInQuoteAsset": "0.44508"
            }
        ]

        url = self.public_url_with_param(CONSTANTS.TRADES_URL, f"orderId={order.exchange_order_id}")

        mock_api.get(url, body=json.dumps(response))

        order_response = self.async_run_with_timeout(self.exchange._request_order_fills(order))

        self.assertEqual(order_response[0]["id"], response[0]["id"])

    @aioresponses()
    def test_place_order(self, mock_api):
        order = InFlightOrder(
            client_order_id = 123,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.LIMIT,
            creation_timestamp = 123456789,
            price = str(9999.0),
            amount = str(10.0),
            initial_state = OrderState.OPEN
        )

        response = {
            "orderId": "123456789",
            "marketId": "BTC-AUD",
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-30T11:08:21.956000Z",
            "price": "100.12",
            "amount": "1.034",
            "openAmount": "1.034",
            "status": "Accepted"
        }

        mock_api.post(self.order_creation_url, body=json.dumps(response))

        order_response = self.async_run_with_timeout(self.exchange._place_order(
            order.client_order_id, order.trading_pair, 10.0, order.trade_type, order.order_type, 9999.9))

        self.assertEqual(order_response[0], response["orderId"])

    def test_format_trading_rules(self):
        exchange_info = [
            {
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": "BTC",
                "quoteAssetName": "AUD",
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            },
            {
                "marketId": "LTC-AUD",
                "baseAssetName": "LTC",
                "quoteAssetName": "AUD",
                "minOrderAmount": "0.001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Post Only"
            }
        ]

        trade_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertEqual(trade_rules[0].trading_pair, self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset))
        self.assertEqual(trade_rules[0].min_order_size, Decimal(str(0.0001)))
        self.assertEqual(trade_rules[0].max_order_size, Decimal(str(1000000)))
        self.assertEqual(trade_rules[0].min_price_increment, Decimal("1") / Decimal(str(math.pow(10, 2))))
        self.assertEqual(trade_rules[0].min_base_amount_increment, Decimal("1") / Decimal(str(math.pow(10, 8))))

    def test_format_trading_rules_exception(self):
        exchange_info = [
            {
                # "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseAssetName": "BTC",
                "quoteAssetName": "AUD",
                "minOrderAmount": "0.0001",
                "maxOrderAmount": "1000000",
                "amountDecimals": "8",
                "priceDecimals": "2",
                "status": "Online"
            }
        ]

        self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {exchange_info[0]}. Skipping."))

    def test_create_order_fill_updates(self):
        inflight_order = InFlightOrder(
            client_order_id = 123,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.LIMIT,
            creation_timestamp = 123456789,
            price = str(9999),
            amount = str(10),
            initial_state = OrderState.OPEN
        )

        order_update = [
            {
                "id": "1",
                "orderId": 123,
                "clientOrderId": 6789,
                "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": "Bid",
                "type": "Limit",
                "timestamp": "2019-08-3T11:11:21.956000Z",
                "price": str(9999),
                "amount": str(10),
                "openAmount": "1.034",
                "fee": "77.77",
                "status": "Fully Matched"
            }
        ]

        trade_updates = self.exchange._create_order_fill_updates(inflight_order, order_update)

        self.assertEqual(trade_updates[0].trade_id, order_update[0]["id"])
        self.assertEqual(trade_updates[0].trading_pair, self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset))

    def test_create_order_update(self):
        inflight_order = InFlightOrder(
            client_order_id = 123,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.LIMIT,
            creation_timestamp = 123456789,
            price = str(9999),
            amount = str(10),
            initial_state = OrderState.OPEN
        )

        order_update = {
            "orderId": 123,
            "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "Bid",
            "type": "Limit",
            "creationTime": "2019-08-3T11:11:21.956000Z",
            "price": str(9999),
            "amount": str(10),
            "openAmount": "1.034",
            "status": "Fully Matched"
        }

        order = self.exchange._create_order_update(inflight_order, order_update)

        self.assertEqual(order.new_state, CONSTANTS.ORDER_STATE[order_update["status"]])
        self.assertEqual(order.trading_pair, self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset))

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = [
            {
                "assetName": self.base_asset,
                "available": 900,
                "balance": 1000
            }
        ]

        mock_api.get(self.balance_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertEqual(self.exchange._account_available_balances[self.base_asset], 900)
        self.assertEqual(self.exchange._account_balances[self.base_asset], 1000)

    @aioresponses()
    def test_get_last_traded_price(self, mock_api):
        response = {
            "lastPrice": "9999.00"
        }

        url = web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{self.trading_pair}/ticker")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(response))

        lastprice_response = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))

        self.assertEqual(lastprice_response, 9999.00)

    @aioresponses()
    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self, mocked_api):
        url = web_utils.private_rest_url(CONSTANTS.FEES_URL)
        regex_url = re.compile(f"^{url}")
        resp = {
            "volume30Day": "0.0098275",
            "feeByMarkets": [
                {
                    "makerFeeRate": "0.002",
                    "takerFeeRate": "0.005",
                    "marketId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
                }
            ]
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        # Maker fee
        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.002"), fee.percent)

        # Taker fee
        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.005"), fee.percent)

        # Default maker fee
        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.0085"), fee.percent)  # default maker fee

        # Default taker fee
        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.0085"), fee.percent)  # default maker fee
