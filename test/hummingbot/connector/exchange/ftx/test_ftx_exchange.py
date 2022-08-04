import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.connector_base import OrderType, TradeType
from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS, ftx_web_utils as web_utils
from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase


class FtxExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"
        cls.subaccount_name = "someSubaccountName"

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.FTX_MARKETS_PATH)

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.FTX_SINGLE_MARKET_PATH.format(
                self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset)))

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.FTX_NETWORK_STATUS_PATH)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.FTX_MARKETS_PATH)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.FTX_PLACE_ORDER_PATH)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.FTX_BALANCES_PATH)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "success": True,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "highLeverageFeeExempt": False,
                    "minProvideSize": 0.001,
                    "type": "spot",
                    "underlying": None,
                    "enabled": True,
                    "ask": 3949.25,
                    "bid": 3949,
                    "last": 10579.52,
                    "postOnly": False,
                    "price": 10579.52,
                    "priceIncrement": 0.25,
                    "sizeIncrement": 0.0001,
                    "restricted": False,
                    "volumeUsd24h": 28914.76,
                    "largeOrderThreshold": 5000.0,
                    "isEtfMarket": False,
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "success": True,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "highLeverageFeeExempt": False,
                    "minProvideSize": 0.001,
                    "type": "spot",
                    "underlying": None,
                    "enabled": True,
                    "ask": 3949.25,
                    "bid": 3949,
                    "last": float(self.expected_latest_price),
                    "postOnly": False,
                    "price": 10579.52,
                    "priceIncrement": 0.25,
                    "sizeIncrement": 0.0001,
                    "restricted": False,
                    "volumeUsd24h": 28914.76,
                    "largeOrderThreshold": 5000.0,
                    "isEtfMarket": False,
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "success": True,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "highLeverageFeeExempt": False,
                    "minProvideSize": 0.001,
                    "type": "spot",
                    "underlying": None,
                    "enabled": True,
                    "ask": 3949.25,
                    "bid": 3949,
                    "last": 10579.52,
                    "postOnly": False,
                    "price": 10579.52,
                    "priceIncrement": 0.25,
                    "sizeIncrement": 0.0001,
                    "restricted": False,
                    "volumeUsd24h": 28914.76,
                    "largeOrderThreshold": 5000.0,
                    "isEtfMarket": False,
                },
                {
                    "name": self.exchange_symbol_for_tokens(base_token="INVALID", quote_token="PAIR"),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "highLeverageFeeExempt": False,
                    "minProvideSize": 0.001,
                    "type": "future",
                    "underlying": None,
                    "enabled": True,
                    "ask": 3949.25,
                    "bid": 3949,
                    "last": 10579.52,
                    "postOnly": False,
                    "price": 10579.52,
                    "priceIncrement": 0.25,
                    "sizeIncrement": 0.0001,
                    "restricted": False,
                    "volumeUsd24h": 28914.76,
                    "largeOrderThreshold": 5000.0,
                    "isEtfMarket": False,
                }
            ]
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "success": True,
            "result": True
        }

    @property
    def trading_rules_request_mock_response(self):
        return {
            "success": True,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "highLeverageFeeExempt": False,
                    "minProvideSize": 0.001,
                    "type": "spot",
                    "underlying": "BTC",
                    "enabled": True,
                    "ask": 3949.25,
                    "bid": 3949,
                    "last": 10579.52,
                    "postOnly": False,
                    "price": 10579.52,
                    "priceIncrement": 0.25,
                    "sizeIncrement": 0.0001,
                    "restricted": False,
                    "volumeUsd24h": 28914.76,
                    "largeOrderThreshold": 5000.0,
                    "isEtfMarket": False,
                }
            ]
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "success": True,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "quoteVolume24h": 28914.76,
                    "change1h": 0.012,
                    "change24h": 0.0299,
                    "changeBod": 0.0156,
                    "type": "spot",
                    "enabled": True,
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "success": True,
            "result": {
                "createdAt": "2019-03-05T09:56:55.728933+00:00",
                "filledSize": 0,
                "future": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                "id": int(self.expected_exchange_order_id),
                "market": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                "price": 0.306525,
                "remainingSize": 31431,
                "side": "buy",
                "size": 31431,
                "status": "open",
                "type": "limit",
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "clientId": "OID1",
            }
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "success": True,
            "result": [
                {
                    "coin": self.base_asset,
                    "free": 10.0,
                    "spotBorrow": 0.0,
                    "total": 15.0,
                    "usdValue": 2340.2,
                    "availableWithoutBorrow": 15.0
                },
                {
                    "coin": self.quote_asset,
                    "free": 2000.0,
                    "spotBorrow": 0.0,
                    "total": 2000.0,
                    "usdValue": 2340.2,
                    "availableWithoutBorrow": 2000.0
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "success": True,
            "result": [
                {
                    "coin": self.base_asset,
                    "free": 10.0,
                    "spotBorrow": 0.0,
                    "total": 15.0,
                    "usdValue": 2340.2,
                    "availableWithoutBorrow": 15.0
                }
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
        min_order_size = Decimal(str(self.trading_rules_request_mock_response["result"][0]["minProvideSize"]))
        min_price_increment = Decimal(str(self.trading_rules_request_mock_response["result"][0]["priceIncrement"]))
        min_base_amount_increment = Decimal(str(
            self.trading_rules_request_mock_response["result"][0]["sizeIncrement"]))
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
            min_quote_amount_increment=min_base_amount_increment * min_price_increment,
            min_notional_size=min_order_size * min_price_increment,
            min_order_value=min_order_size * min_price_increment,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["result"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "9596912"

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
        return DeductedFromReturnsTradeFee(
            percent_token=self.base_asset,
            flat_fees=[TokenAmount(token=self.base_asset, amount=Decimal("0.0001"))])

    @property
    def expected_fill_trade_id(self) -> int:
        return 30000

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}/{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return FtxExchange(
            client_config_map=client_config_map,
            ftx_api_key=self.api_key,
            ftx_secret_key=self.api_secret_key,
            ftx_subaccount_name=self.subaccount_name,
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("FTX-KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["FTX-KEY"])
        self.assertIn("FTX-TS", request_headers)
        self.assertIn("FTX-SIGN", request_headers)
        self.assertIn("FTX-SUBACCOUNT", request_headers)
        self.assertEqual(self.subaccount_name, request_headers["FTX-SUBACCOUNT"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["market"])
        order_type = "market" if order.order_type == OrderType.MARKET else "limit"
        self.assertEqual(order_type, request_data["type"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["clientId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        self.assertIsNone(request_params)
        self.assertIsNone(request_data)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        self.assertIsNone(request_params)
        self.assertIsNone(request_data)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["market"])
        self.assertEqual(int(order.exchange_order_id), request_params["orderId"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "success": False,
            "result": "Cancelation error"
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FTX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FTX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.FTX_ORDER_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "orders",
            "data": {
                "id": int(order.exchange_order_id or self.expected_exchange_order_id),
                "clientId": order.client_order_id,
                "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "price": float(order.price),
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "status": "new",
                "filledSize": 0.0,
                "remainingSize": float(order.amount),
                "avgFillPrice": 0.0,
                "createdAt": "2021-05-02T22:40:07.217963+00:00"
            },
            "type": "update"
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "orders",
            "data": {
                "id": int(order.exchange_order_id),
                "clientId": order.client_order_id,
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "price": float(order.price),
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "status": "closed",
                "filledSize": 0,
                "remainingSize": float(order.amount),
                "avgFillPrice": 0,
                "createdAt": "2021-05-02T22:40:07.217963+00:00"
            },
            "type": "update"
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "orders",
            "data": {
                "id": int(order.exchange_order_id),
                "clientId": order.client_order_id,
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "price": float(order.price),
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "status": "closed",
                "filledSize": float(order.amount),
                "remainingSize": 0,
                "avgFillPrice": float(order.price),
                "createdAt": "2021-05-02T22:40:07.217963+00:00"
            },
            "type": "update"
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "fills",
            "data": {
                "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                "feeRate": 0.0014,
                "future": None,
                "id": 7828307,
                "liquidity": "maker",
                "market": "BTC-PERP",
                "orderId": int(order.exchange_order_id),
                "tradeId": self.expected_fill_trade_id,
                "price": float(order.price),
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "time": "2019-05-07T16:40:58.358438+00:00",
                "type": "order"
            },
            "type": "update"
        }

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
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
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
            hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("FTX does not have a documented error for wrong timestamp")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    def test_user_stream_update_for_order_full_fill_for_different_exchange_order_id_is_ignored(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["11"]

        order_event = {
            "channel": "orders",
            "data": {
                "id": 1,
                "clientId": "UNKNOWN_ORDER_ID",
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "price": float(order.price),
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "status": "closed",
                "filledSize": float(order.amount),
                "remainingSize": 0,
                "avgFillPrice": float(order.price),
                "createdAt": "2021-05-02T22:40:07.217963+00:00"
            },
            "type": "update"
        }
        trade_event = {
            "channel": "fills",
            "data": {
                "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                "feeRate": 0.0014,
                "future": None,
                "id": 7828307,
                "liquidity": "maker",
                "market": "BTC-PERP",
                "orderId": 1,
                "tradeId": self.expected_fill_trade_id,
                "price": float(order.price),
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "time": "2019-05-07T16:40:58.358438+00:00",
                "type": "order"
            },
            "type": "update"
        }

        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(0, len(self.order_filled_logger.event_log))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "result": "Order queued for cancellation"
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": {
                "createdAt": "2019-03-05T09:56:55.728933+00:00",
                "filledSize": 0,
                "future": None,
                "id": int(exchange_order_id),
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": float(order.price),
                "avgFillPrice": 0,
                "remainingSize": 0,
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "status": "open",
                "type": "limit",
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "clientId": order.client_order_id
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": {
                "createdAt": "2019-03-05T09:56:55.728933+00:00",
                "filledSize": float(self.expected_partial_fill_amount),
                "future": None,
                "id": int(exchange_order_id),
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": float(order.price),
                "avgFillPrice": float(self.expected_partial_fill_price),
                "remainingSize": float(order.amount - self.expected_partial_fill_amount),
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "status": "open",
                "type": "limit",
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "clientId": order.client_order_id
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": {
                "createdAt": "2019-03-05T09:56:55.728933+00:00",
                "filledSize": float(order.amount),
                "future": None,
                "id": int(exchange_order_id),
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": float(order.price),
                "avgFillPrice": float(order.price + Decimal(2)),
                "remainingSize": 0,
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "status": "closed",
                "type": "limit",
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "clientId": order.client_order_id
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": {
                "createdAt": "2019-03-05T09:56:55.728933+00:00",
                "filledSize": 0,
                "future": None,
                "id": int(exchange_order_id),
                "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": float(order.price),
                "avgFillPrice": 0,
                "remainingSize": float(order.amount),
                "side": order.trade_type.name.lower(),
                "size": float(order.amount),
                "status": "closed",
                "type": "limit",
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "clientId": order.client_order_id
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": [
                {
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "feeCurrency": self.expected_fill_fee.flat_fees[0].token,
                    "feeRate": 0.0005,
                    "future": None,
                    "id": 11215,
                    "liquidity": "taker",
                    "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "baseCurrency": order.base_asset,
                    "quoteCurrency": order.quote_asset,
                    "orderId": int(exchange_order_id),
                    "tradeId": int(self.expected_fill_trade_id),
                    "price": float(order.price),
                    "side": order.trade_type.name.lower(),
                    "size": float(order.amount),
                    "time": "2019-03-27T19:15:10.204619+00:00",
                    "type": "order"
                }
            ]
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "success": True,
            "result": [
                {
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "feeCurrency": self.expected_fill_fee.flat_fees[0].token,
                    "feeRate": 0.0005,
                    "future": None,
                    "id": 11215,
                    "liquidity": "taker",
                    "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "baseCurrency": order.base_asset,
                    "quoteCurrency": order.quote_asset,
                    "orderId": int(exchange_order_id),
                    "tradeId": int(self.expected_fill_trade_id),
                    "price": float(self.expected_partial_fill_price),
                    "side": order.trade_type.name.lower(),
                    "size": float(self.expected_partial_fill_amount),
                    "time": "2019-03-27T19:15:10.204619+00:00",
                    "type": "order"
                }
            ]
        }
