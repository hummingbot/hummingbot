import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import patch
from urllib.parse import urlencode

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_derivative import DeepcoinPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import FundingPaymentCompletedEvent, OrderCancelledEvent


class DeepcoinPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.passphrase = "somePassphrase"

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    # @property
    # def all_symbols_url(self):
    #     url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.EXCHANGE_INFO_URL)
    #     url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
    #     return url

    @property
    def all_symbols_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.EXCHANGE_INFO_URL)
        params = {"instType": "SWAP"}
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.TICKER_PRICE_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    # OK
    @property
    def network_status_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SERVER_TIME_PATH_URL)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CREATIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.FUNDING_INFO_URL)
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def funding_payment_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_BILLS_DETAILS, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "uly": "",
                    "baseCcy": self.base_asset,
                    "quoteCcy": self.quote_asset,
                    "ctVal": "0.001",
                    "ctValCcy": "",
                    "listTime": "0",
                    "lever": "125",
                    "tickSz": "0.1",
                    "lotSz": "1",
                    "minSz": "1",
                    "ctType": "",
                    "alias": "",
                    "state": "live",
                    "maxLmtSz": "200000",
                    "maxMktSz": "200000"
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": "0",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "uly": "",
                    "baseCcy": "INVALID",
                    "quoteCcy": "USDT",
                    "ctVal": "0.001",
                    "ctValCcy": "",
                    "listTime": "0",
                    "lever": "125",
                    "tickSz": "0.1",
                    "lotSz": "1",
                    "minSz": "1",
                    "ctType": "",
                    "alias": "",
                    "state": "live",
                    "maxLmtSz": "200000",
                    "maxMktSz": "200000"
                },
            ]
        }

        return "INVALID-PAIR", response

    @property
    def trading_rules_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.EXCHANGE_INFO_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_request_mock_response(self):
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": "BTC-USDT-SWAP",
                    "uly": "",
                    "baseCcy": "BTC",
                    "quoteCcy": "USDT",
                    "ctVal": "0.01",
                    "ctValCcy": "",
                    "listTime": "0",
                    "lever": "125",
                    "tickSz": "0.1",
                    "lotSz": "1",
                    "minSz": "1",
                    "ctType": "",
                    "alias": "",
                    "state": "live",
                    "maxLmtSz": "200000",
                    "maxMktSz": "200000"
                }
            ]
        }
        return response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "uly": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ctValCcy": self.base_asset,
                    "ctType": "linear",
                    "state": "live"
                }
            ]
        }
        return response

    def test_format_trading_rules(self):
        margin_asset = self.quote_asset
        min_order_size = Decimal(str(1))
        min_price_increment = Decimal(str(0.01))
        min_base_amount_increment = Decimal(str(1))
        mocked_response = self.trading_rules_request_mock_response
        self._simulate_trading_rules_initialized()
        trading_rules = self.run_async_with_timeout(self.exchange._format_trading_rules(mocked_response))

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)
        self.assertEqual(margin_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(margin_asset, trading_rule.sell_order_collateral_token)

    def test_format_trading_rules_exception(self):
        mocked_response = self.trading_rules_request_erroneous_mock_response
        self._simulate_trading_rules_initialized()
        self.run_async_with_timeout(self.exchange._format_trading_rules(mocked_response))

        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error parsing the trading pair rule: {mocked_response['data'][0]}. Skipping..."
        ))

    @property
    def latest_prices_request_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.trading_pair,
                    "last": str(self.expected_latest_price),
                    "lastSz": "",
                    "askPx": "96127.8",
                    "askSz": "179208",
                    "bidPx": "96127.3",
                    "bidSz": "2951",
                    "open24h": "95596.6",
                    "high24h": "96531.5",
                    "low24h": "95247",
                    "volCcy24h": "55.814169",
                    "vol24h": "5350671",
                    "sodUtc0": "",
                    "sodUtc8": "",
                    "ts": "1739242026000"
                }
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": {
                "ts": 1762414261346
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": {
                "clOrdId": "dp123456",
                "ordId": self.expected_exchange_order_id,
                "tag": "",
                "sCode": "0",
                "sMsg": ""
            }
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "ccy": "USDT",
                    "bal": "41473433.53",
                    "frozenBal": "192.05",
                    "availBal": "41473234.12"
                },
                {
                    "ccy": "BTC",
                    "bal": "0.99715276",
                    "frozenBal": "0.00135139",
                    "availBal": "0.99448105"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "ccy": self.base_asset,
                    "bal": "0.99715276",
                    "frozenBal": "0.00135139",
                    "availBal": "0.99448105"
                }
            ]
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "action": "PushAccount",
            "result": [
                {
                    "table": "Account",
                    "data": {
                        "A": "36005550",
                        "B": 1998332.7691469,
                        "C": "USDT",
                        "M": "36005550",
                        "W": 1998316.543355371,
                        "a": 1998316.543355371,
                        "c": 2.02499997,
                        "u": 12.932968
                    }
                }
            ]
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minSz"]),
            min_price_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["tickSz"]),
            min_base_amount_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["lotSz"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "1000587866646229"

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
        return "TrID1"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}-SWAP"

    def create_exchange_instance(self):
        exchange = DeepcoinPerpetualDerivative(
            deepcoin_perpetual_api_key=self.api_key,
            deepcoin_perpetual_secret_key=self.api_secret,
            deepcoin_perpetual_passphrase=self.passphrase,
            trading_pairs=[self.trading_pair],
        )
        exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def _simulate_contract_sizes_initialized(self):
        self.exchange._contract_sizes = {
            self.trading_pair: Decimal("1")
        }

    def _format_amount_to_size(self, amount: Decimal) -> Decimal:
        self._simulate_contract_sizes_initialized()
        return amount / self.exchange._contract_sizes[self.trading_pair]

    def _format_size_to_amount(self, size: Decimal) -> Decimal:
        self._simulate_contract_sizes_initialized()
        return size * self.exchange._contract_sizes[self.trading_pair]

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": []
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "billId": "1000749090787153",
                    "ccy": "USDT",
                    "clientId": "",
                    "balChg": "-0.08911552",
                    "bal": "210523.96755368",
                    "type": "7",
                    "ts": "1736760623000"
                }
            ]
        }

    @property
    def funding_info_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": {
                "current_fund_rates": [
                    {
                        "instrumentId": "BTCUSDT",
                        "fundingRate": 0.00011794
                    }
                ]
            }
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_timestamp(self):
        return 1763538303

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

    @staticmethod
    def _order_cancelation_request_successful_mock_response(response_scode: int, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": order.client_order_id,
                    "ordId": order.exchange_order_id or "dummyOrdId",
                    "sCode": str(response_scode),
                    "sMsg": ""
                }
            ]
        }

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("OK-ACCESS-KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["OK-ACCESS-KEY"])
        self.assertIn("OK-ACCESS-TIMESTAMP", request_headers)
        self.assertIn("OK-ACCESS-SIGN", request_headers)
        self.assertIn("OK-ACCESS-PASSPHRASE", request_headers)
        self.assertEqual(self.passphrase, request_headers["OK-ACCESS-PASSPHRASE"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        self._simulate_trading_rules_initialized()
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["instId"])
        self.assertEqual("cross", request_data["tdMode"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.order_type.name.lower(), request_data["ordType"])
        self.assertEqual(order.amount, self._format_size_to_amount(abs(Decimal(str(request_data["sz"])))))
        self.assertEqual(Decimal("10000"), Decimal(request_data["px"]))
        self.assertEqual(order.client_order_id, request_data["clOrdId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["instId"])
        self.assertEqual(order.client_order_id, request_data["clOrdId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["instId"])
        self.assertEqual(order.client_order_id, request_params["clOrdId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        self.validate_order_status_request(order, request_call)

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            response_scode: int = 0,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_OPEN_ORDERS_URL, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order, response_scode=response_scode)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_OPEN_ORDERS_URL, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": order.client_order_id,
                    "ordId": order.exchange_order_id or "dummyExchangeOrderId",
                    "sCode": "1",
                    "sMsg": "Error"
                }
            ]
        }
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses,
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
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACTIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACTIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACTIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACTIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACTIVE_ORDER_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        self._simulate_trading_rules_initialized()
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "tradeId": "1000169956494218",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tgtCcy": "",
                    "ccy": "",
                    "tag": "",
                    "px": "1.000000",
                    "sz": "95000.000000",
                    "pnl": "0.000000",
                    "ordType": "limit",
                    "side": "buy",
                    "posSide": "long",
                    "tdMode": "cross",
                    "accFillSz": "0.000000",
                    "fillPx": "",
                    "fillSz": "0.000000",
                    "fillTime": "1739263130000",
                    "avgPx": "",
                    "state": "live",
                    "lever": "1.000000",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "",
                    "slOrdPx": "",
                    "feeCcy": "USDT",
                    "fee": "0.000000",
                    "rebateCcy": "",
                    "source": "",
                    "rebate": "",
                    "category": "normal",
                    "uTime": "1739263130000",
                    "cTime": "1739263130000"
                }
            ]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["state"] = "canceled"
        resp["data"][0]["fillSz"] = 0
        resp["data"][0]["cum_exec_value"] = 0
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["state"] = "live"
        resp["data"][0]["fillSz"] = 0
        resp["data"][0]["fillPx"] = 0
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["state"] = "partially_filled"
        resp["data"][0]["fillSz"] = str(self._format_amount_to_size(self.expected_partial_fill_amount))
        resp["data"][0]["accFillSz"] = str(self._format_amount_to_size(self.expected_partial_fill_amount))
        resp["data"][0]["sz"] = str(self._format_amount_to_size(self.expected_partial_fill_amount))
        resp["data"][0]["fillPx"] = float(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "tradeId": self.expected_fill_trade_id,
                    "ordId": order.exchange_order_id,
                    "clOrdId": order.client_order_id,
                    "billId": "1111",
                    "tag": "",
                    "fillPx": str(self.expected_partial_fill_price),
                    "fillSz": str(self._format_amount_to_size(self.expected_partial_fill_amount)),
                    "side": order.order_type.name.lower(),
                    "posSide": (
                        "short"
                        if (
                                (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                                or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE)
                        )
                        else "long"
                    ),
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(-self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                },
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "tradeId": self.expected_fill_trade_id,
                    "ordId": order.exchange_order_id,
                    "clOrdId": order.client_order_id,
                    "billId": "1111",
                    "tag": "",
                    "fillPx": str(order.price),
                    "fillSz": str(self._format_amount_to_size(Decimal(order.amount))),
                    "side": order.order_type.name.lower(),
                    "posSide": (
                        "short"
                        if (
                                (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                                or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE)
                        )
                        else "long"
                    ),
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(-self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                }
            ]
        }

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_URL, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(f"^{url}")

        err_code = 1
        err_msg = "Some problem"
        mock_response = {
            "code": err_code,
            "data": [],
            "msg": err_msg
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"ret_code <{err_code}> - {err_msg}"

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_URL, domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(f"^{url}")
        mock_response = {
            "code": "0",
            "data": [
                {
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "lever": "17",
                    "mgnMode": "cross",
                    "mrgPosition": "merge",
                    "sCode": "0",
                    "sMsg": ""

                }
            ],
            "msg": ""
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "action": "PushOrder",
            "result": [
                {
                    "table": "Order",
                    "data": {
                        "D": "1",
                        "I": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                        "IT": 1690804738,
                        "L": "1000175061255804",
                        "O": "9",
                        "OS": "1000175061255804",
                        "OT": "0",
                        "Or": "1",
                        "P": 29365,
                        "T": 1616.621,
                        "U": 1690804738,
                        "V": 55,
                        "i": 0,
                        "l": 125,
                        "o": "0",
                        "p": "1",
                        "t": 29393.1090909091,
                        "v": 55
                    }
                }
            ]
        }

    @aioresponses()
    def test_update_trade_history(self, mock_api):
        amount = Decimal("100")
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=amount,
            order_type=OrderType.LIMIT,
        )
        response = self._order_fills_request_full_fill_mock_response(self.exchange.in_flight_orders["11"])
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.ACCOUNT_TRADE_LIST_URL)
        url = f"{url}?instId={self.exchange_trading_pair}&limit=100&instType=SWAP"
        regex_url = re.compile(f"^{url}")
        mock_api.get(regex_url, body=json.dumps(response))
        asyncio.get_event_loop().run_until_complete(self.exchange._update_trade_history())
        # Assert that self._trading_pairs is not empty
        self.assertNotEqual(len(self.exchange._trading_pairs), 0, "No trading pairs fetched")

        # Assert that each parsed response is a dictionary
        for data in response["data"]:
            self.assertIsInstance(data, dict, "Parsed response is not a dictionary")

            # Assert that each parsed response has 'ts', 'tradeId', 'fillSz', and 'fillPx' keys
            self.assertTrue(all(key in data for key in ["ts", "tradeId", "fillSz", "fillPx"]),
                            "Parsed response does not contain expected keys")

            # Assert that amount is not None and is a Decimal
            self.assertIsNotNone(amount, "Amount is None")
            self.assertIsInstance(amount, Decimal, "Amount is not a Decimal")

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {}

    def funding_info_event_for_websocket_update(self):
        return {}

    def test_create_order_with_invalid_position_action_raises_value_error(self):
        self._simulate_trading_rules_initialized()
        with self.assertRaises(ValueError) as exception_context:
            asyncio.get_event_loop().run_until_complete(
                self.exchange._create_order(
                    trade_type=TradeType.BUY,
                    order_id="C1",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                    position_action=PositionAction.NIL,
                ),
            )

        self.assertEqual(
            f"Invalid position action {PositionAction.NIL}. Must be one of {[PositionAction.OPEN, PositionAction.CLOSE]}",
            str(exception_context.exception)
        )

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, mock_api):
        def callback(*args, **kwargs):
            request_sent_event.set()

        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        url = self.funding_payment_url
        # TODO: Check with dman if this is ok
        # Since the funding payment is not updated in the order book, we need to set the last rate
        self.exchange._orderbook_ds._last_rate = self.target_funding_payment_funding_rate

        async def run_test():
            response = self.empty_funding_payment_mock_response
            mock_api.get(url, body=json.dumps(response), callback=callback)
            _ = asyncio.create_task(self.exchange._funding_payment_polling_loop())

            # Allow task to start - on first pass no event is emitted (initialization)
            await asyncio.sleep(0.1)
            self.assertEqual(0, len(self.funding_payment_logger.event_log))

            response = self.funding_payment_mock_response
            mock_api.get(url, body=json.dumps(response), callback=callback, repeat=True)

            request_sent_event.clear()
            self.exchange._funding_fee_poll_notifier.set()
            await request_sent_event.wait()
            self.assertEqual(1, len(self.funding_payment_logger.event_log))

            request_sent_event.clear()
            self.exchange._funding_fee_poll_notifier.set()
            await request_sent_event.wait()

        self.run_async_with_timeout(run_test())

        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        funding_event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
        self.assertEqual(self.target_funding_payment_timestamp, funding_event.timestamp)
        self.assertEqual(self.exchange.name, funding_event.market)
        self.assertEqual(self.trading_pair, funding_event.trading_pair)
        self.assertEqual(self.target_funding_payment_payment_amount, funding_event.amount)
        self.assertEqual(self.target_funding_payment_funding_rate, funding_event.funding_rate)

    def test_supported_position_modes(self):
        pass

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError(
            "Error executing request POST https://api.deepcoin.com/deepcoin/trade/order. HTTP status is 401. "
            'Error: {"code":"50111","msg":"message"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError(
            "Error executing request POST https://api.deepcoin.com/deepcoin/trade/order. HTTP status is 401. "
            'Error: {"code":"50114","msg":"message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        # Not supported at present
        pass

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        # Not supported at present
        pass

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1763538303)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        url = self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            response_scode=0,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.exchange_order_id)
        self.run_async_with_timeout(request_sent_event.wait())

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(cancel_request)
        self.validate_order_cancelation_request(
            order=order,
            request_call=cancel_request)

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_cancelled)
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order.client_order_id}."
                )
            )
        else:
            self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_pending_cancel_confirmation)

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {}

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        raise NotImplementedError

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        raise NotImplementedError

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        pass

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        pass
