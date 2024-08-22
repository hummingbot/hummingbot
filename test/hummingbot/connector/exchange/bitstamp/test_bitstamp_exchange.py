import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitstamp import bitstamp_constants as CONSTANTS, bitstamp_web_utils as web_utils
from hummingbot.connector.exchange.bitstamp.bitstamp_exchange import BitstampExchange
from hummingbot.connector.exchange.bitstamp.bitstamp_utils import DEFAULT_FEES
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)


class BitstampExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    maxDiff = None

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        symbol = self.exchange_trading_pair
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_URL.format(symbol), domain=self.exchange._domain)
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.STATUS_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url("/", domain=self.exchange._domain)
        return url

    def order_creation_url_for_trade_type(self, trade_type: TradeType, trading_pair: str):
        type = "buy" if trade_type == TradeType.BUY else "sell"
        url = web_utils.private_rest_url(f"/{type}/{trading_pair}/", domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_BALANCES_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "name": f"{self.base_asset}/{self.quote_asset}",
                "url_symbol": f"{self.base_asset.lower()}{self.quote_asset.lower()}",
                "base_decimals": 8,
                "counter_decimals": 2,
                "instant_order_counter_decimals": 2,
                "minimum_order": "20.0 USD",
                "trading": "Enabled",
                "instant_and_market_orders": "Enabled",
                "description": f"{self.base_asset} / {self.quote_asset}"
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            "ask": "2211.00",
            "bid": "2188.97",
            "high": "2811.00",
            "last": "2211.00",
            "low": "2188.97",
            "open": "2211.00",
            "open_24": "2211.00",
            "percent_change_24": "13.57",
            "side": "0",
            "timestamp": "1643640186",
            "volume": "213.26801100",
            "vwap": "2189.80"
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {
                "name": f"{self.base_asset}/{self.quote_asset}",
                "url_symbol": f"{self.base_asset.lower()}{self.quote_asset.lower()}",
                "base_decimals": 8,
                "counter_decimals": 2,
                "instant_order_counter_decimals": 2,
                "minimum_order": "20.0 USD",
                "trading": "Enabled",
                "instant_and_market_orders": "Enabled",
                "description": f"{self.base_asset} / {self.quote_asset}"
            },
            {
                "name": "INVALID/PAIR",
                "url_symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                "base_decimals": 8,
                "counter_decimals": 2,
                "instant_order_counter_decimals": 2,
                "minimum_order": "20.0 PAIR",
                "trading": "Disabled",
                "instant_and_market_orders": "Enabled",
                "description": f"{self.base_asset} / {self.quote_asset}"
            }
        ]

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "server_time": 1719654227271
        }

    @property
    def trading_rules_request_mock_response(self):
        return [
            {
                "name": f"{self.base_asset}/{self.quote_asset}",
                "url_symbol": f"{self.base_asset.lower()}{self.quote_asset.lower()}",
                "base_decimals": 8,
                "counter_decimals": 2,
                "instant_order_counter_decimals": 2,
                "minimum_order": "20.0 USD",
                "trading": "Enabled",
                "instant_and_market_orders": "Enabled",
                "description": f"{self.base_asset} / {self.quote_asset}"
            }
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {
                "url_symbol": f"{self.base_asset.lower()}{self.quote_asset.lower()}",
                "trading": "Enabled",
            }
        ]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "id": self.expected_exchange_order_id,
            "market": f"{self.base_asset}/{self.quote_asset}",
            "datetime": "2022-01-31 14:43:15.796000",
            "type": "0",
            "price": "10000",
            "amount": "100",
            "client_order_id": ""
        }

    @property
    def trading_fees_mock_response(self):
        return [
            {
                "currency_pair": self.exchange_trading_pair,
                "market": self.exchange_trading_pair,
                "fees": {
                    "maker": "1.0000",
                    "taker": "2.0000"
                }
            },
            {
                "currency_pair": "btcusd",
                "market": "btcusd",
                "fees": {
                    "maker": "0.3000",
                    "taker": "0.4000"
                }
            },
        ]

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "available": "10.00",
                "currency": self.base_asset,
                "reserved": "5.00",
                "total": "15.00"
            },
            {
                "available": "2000.00",
                "currency": self.quote_asset,
                "reserved": "0.00",
                "total": "2000.00"
            }
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "available": "10.00",
                "currency": self.base_asset,
                "reserved": "5.00",
                "total": "15.00"
            }
        ]

    @property
    def balance_event_websocket_update(self):
        raise NotImplementedError

    @property
    def expected_latest_price(self):
        return 2211.00

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_price_increment=Decimal("1e-2"),
            min_base_amount_increment=Decimal("1e-8"),
            min_quote_amount_increment=Decimal("1e-2"),
            min_notional_size=Decimal("20.0"),
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
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token.lower()}{quote_token.lower()}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return BitstampExchange(
            client_config_map=client_config_map,
            bitstamp_api_key="testAPIKey",
            bitstamp_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        expected_headers = [
            "X-Auth",
            "X-Auth-Signature",
            "X-Auth-Nonce",
            "X-Auth-Timestamp",
            "X-Auth-Version"
        ]
        self.assertEqual("BITSTAMP testAPIKey", request_headers["X-Auth"])
        for header in expected_headers:
            self.assertIn(header, request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertEqual(order.exchange_order_id, str(request_data["id"]))

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertEqual(order.client_order_id, str(request_data["client_order_id"]))

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertEqual(order.client_order_id, str(request_data["client_order_id"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._get_error_response(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE, CONSTANTS.ORDER_NOT_EXIST_MESSAGE)
        mock_api.post(regex_url, status=200, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)

        # It's called twice, once during the _request_order_status call and once during _all_trade_updates_for_order
        # TODO: Refactor the code to avoid calling the same endpoint twice
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._get_error_response(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE, CONSTANTS.ORDER_NOT_EXIST_MESSAGE)
        mock_api.post(regex_url, status=200, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_trading_fees_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TRADING_FEES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.trading_fees_mock_response
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = self.balance_url
        mock_api.post(
            re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")),
            body=json.dumps(response),
            callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            'data': {
                'id': order.exchange_order_id,
                'id_str': str(order.exchange_order_id),
                'order_type': 1,
                'datetime': '1719221608',
                'microtimestamp': '1719221607521000',
                'amount': 300.00000000,
                'amount_str': '300.00000000',
                'amount_traded': '0',
                'amount_at_create': '300.00000000',
                'price': 0.12619,
                'price_str': '0.12619',
                'trade_account_id': 0,
                'client_order_id': order.client_order_id,
            },
            'channel': CONSTANTS.WS_PRIVATE_MY_ORDERS.format(self.exchange_trading_pair, 1),
            'event': 'order_created'
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            'data': {
                'id': order.exchange_order_id,
                'id_str': str(order.exchange_order_id),
                'order_type': 1,
                'datetime': '1719221608',
                'microtimestamp': '1719221607521000',
                'amount': 300.00000000,
                'amount_str': '300.00000000',
                'amount_traded': '0',
                'amount_at_create': '300.00000000',
                'price': 0.12619,
                'price_str': '0.12619',
                'trade_account_id': 0,
                'client_order_id': order.client_order_id,
            },
            'channel': CONSTANTS.WS_PRIVATE_MY_ORDERS.format(self.exchange_trading_pair, 1),
            'event': 'order_deleted'
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            'data': {
                'id': order.exchange_order_id,
                'id_str': str(order.exchange_order_id),
                'order_type': 1,
                'datetime': '1719221608',
                'microtimestamp': '1719221607521000',
                'amount': 0,
                'amount_str': '0',
                'amount_traded': '300.00000000',
                'amount_at_create': '300.00000000',
                'price': 0.12619,
                'price_str': '0.12619',
                'trade_account_id': 0,
                'client_order_id': order.client_order_id,
            },
            'channel': CONSTANTS.WS_PRIVATE_MY_ORDERS.format(self.exchange_trading_pair, 1),
            'event': 'order_deleted'
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            'data': {
                'id': int(order.exchange_order_id),
                'amount': str(order.amount),
                'price': str(order.price),
                'microtimestamp': '1719221608330000',
                'fee': str(self.expected_fill_fee.flat_fees[0].amount),
                'order_id': 1762863651524616,
                'client_order_id': order.client_order_id,
                'trade_account_id': 0,
                'side': order.trade_type.name.lower(),
            },
            'channel': CONSTANTS.WS_PRIVATE_MY_TRADES.format(self.exchange_trading_pair, 1),
            'event': 'trade'
        }

    def trade_event_for_self_trade_websocket_update(self, buy_order: InFlightOrder, sell_order: InFlightOrder):
        return {
            'data': {
                'timestamp': 1720288033,
                'amount': buy_order.amount,
                'amount_str': str(buy_order.amount),
                'price': buy_order.price,
                'price_str': str(buy_order.price),
                'type': 0,
                'microtimestamp': '1720288033933000',
                'buy_order_id': buy_order.exchange_order_id,
                'sell_order_id': sell_order.exchange_order_id,
                'sellers_trade_account_id': 0,
                'buyers_trade_account_id': 0
            },
            'channel': CONSTANTS.WS_PRIVATE_MY_SELF_TRADES.format(self.exchange_trading_pair, 1),
            'event': 'self_trade'
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": int(order.exchange_order_id),
            "amount": str(order.amount),
            "price": str(order.price),
            "type": 0 if order.trade_type == TradeType.BUY else 1,
            "market": f"{order.base_asset}/{order.quote_asset}",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Finished",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [],
            "amount_remaining": "0",
            "client_order_id": order.client_order_id,
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Canceled",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [],
            "amount_remaining": str(order.amount),
            "client_order_id": order.client_order_id,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Open",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [],
            "amount_remaining": str(order.amount),
            "client_order_id": order.client_order_id,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Open",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [],
            "amount_remaining": str(order.amount - self.expected_partial_fill_amount),
            "client_order_id": order.client_order_id,
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Open",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [
                {
                    "tid": self.expected_fill_trade_id,
                    "price": str(self.expected_partial_fill_price),
                    order.base_asset.lower(): str(self.expected_partial_fill_amount),
                    order.quote_asset.lower(): str(self.expected_partial_fill_price * self.expected_partial_fill_amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "datetime": "2022-01-31 14:43:16.000",
                    "type": 0
                }
            ],
            "amount_remaining": str(order.amount - self.expected_partial_fill_amount),
            "client_order_id": order.client_order_id,
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "datetime": "2022-01-31 14:43:15",
            "type": "0",
            "status": "Finished",
            "market": f"{self.base_asset}/{self.quote_asset}",
            "transactions": [
                {
                    "tid": self.expected_fill_trade_id,
                    "price": str(order.price),
                    order.base_asset.lower(): str(order.amount),
                    order.quote_asset.lower(): str(order.price * order.amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "datetime": "2022-01-31 14:43:16.000",
                    "type": 0
                }
            ],
            "amount_remaining": "0",
            "client_order_id": order.client_order_id,
        }

    def test_user_stream_balance_update(self):
        """
        The balance update event is not supported by the Bitstamp exchange
        """
        pass

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url_for_trade_type(TradeType.BUY, self.exchange_trading_pair)

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair} "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url_for_trade_type(TradeType.SELL, self.exchange_trading_pair)
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair} at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url_for_trade_type(TradeType.BUY, self.exchange_trading_pair)
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

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
            price=Decimal("10000")
        )
        self.validate_order_creation_request(
            order=order_to_validate_request,
            request_call=order_request)

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
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url_for_trade_type(TradeType.BUY, self.exchange_trading_pair)
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.0001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait(), timeout=3)

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.01. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_update_trading_fees(self, mock_api):
        self.configure_trading_fees_response(mock_api=mock_api)
        resp = self.trading_fees_mock_response

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        expected_trading_fees = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(resp[0]["fees"]["maker"]),
            taker_percent_fee_decimal=Decimal(resp[0]["fees"]["taker"]),
        )

        self.assertEqual(expected_trading_fees, self.exchange._trading_fees[self.trading_pair])
        self.assertEqual(1, len(self.exchange._trading_fees))

    def test_get_fee_default(self):
        expected_maker_fee = AddedToCostTradeFee(percent=DEFAULT_FEES.maker_percent_fee_decimal)
        maker_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, 1, 2, is_maker=True)

        exptected_taker_fee = AddedToCostTradeFee(percent=DEFAULT_FEES.taker_percent_fee_decimal)
        taker_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.MARKET, TradeType.BUY, 1, 2, is_maker=False)

        self.assertEqual(expected_maker_fee, maker_fee)
        self.assertEqual(exptected_taker_fee, taker_fee)

    @aioresponses()
    def test_get_fee(self, mock_api):
        self.configure_trading_fees_response(mock_api=mock_api)
        resp = self.trading_fees_mock_response

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        expected_maker_fee = AddedToCostTradeFee(percent=Decimal(resp[0]["fees"]["maker"]))
        maker_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, 1, 2, is_maker=True)

        expected_taker_fee = AddedToCostTradeFee(percent=Decimal(resp[0]["fees"]["taker"]))
        taker_fee = self.exchange._get_fee(self.base_asset, self.quote_asset, OrderType.MARKET, TradeType.BUY, 1, 2, is_maker=False)

        self.assertEqual(expected_maker_fee, maker_fee)
        self.assertEqual(expected_taker_fee, taker_fee)

    def test_time_synchronizer_related_request_error_detection(self):
        response = self._get_error_response(CONSTANTS.TIMESTAMP_ERROR_CODE, CONSTANTS.TIMESTAMP_ERROR_MESSAGE)
        exception = IOError(f"'Error executing request POST {self.balance_url}. HTTP status is 403. Error: {json.dumps(response)}'")
        self.assertEqual(True, self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    def test_user_stream_update_for_self_trade_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        buy_order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "2",
            exchange_order_id=str(self.expected_exchange_order_id) + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("10"),
        )
        sell_order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "2"]

        trade_event = self.trade_event_for_self_trade_websocket_update(buy_order=buy_order, sell_order=sell_order)

        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)

        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(buy_order.client_order_id, fill_event.order_id)
        self.assertEqual(buy_order.trading_pair, fill_event.trading_pair)
        self.assertEqual(buy_order.trade_type, fill_event.trade_type)
        self.assertEqual(buy_order.order_type, fill_event.order_type)
        self.assertEqual(buy_order.price, fill_event.price)
        self.assertEqual(buy_order.amount, fill_event.amount)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"The BUY order {buy_order.client_order_id} amounting to {buy_order.executed_amount_base}/{buy_order.amount} COINALPHA has been filled at {Decimal('10000')} HBOT."
            )
        )

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"The SELL order {sell_order.client_order_id} amounting to {sell_order.executed_amount_base}/{sell_order.amount} COINALPHA has been filled at {Decimal('10000')} HBOT."
            )
        )

    def _get_error_response(self, error_code, error_reason):
        return {
            "status": "error",
            "reason": error_reason,
            "code": error_code
        }
