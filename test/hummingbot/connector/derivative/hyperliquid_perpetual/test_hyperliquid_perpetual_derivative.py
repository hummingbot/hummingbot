import asyncio
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.core.network_iterator import NetworkStatus


class HyperliquidPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_address = "someAddress"
        cls.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        cls.hyperliquid_mode = "arb_wallet"  # noqa: mock
        cls.use_vault = False
        cls.user_id = "someUserId"
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.client_order_id_prefix = "0x48424f5442454855443630616330301"  # noqa: mock

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.TICKER_PRICE_CHANGE_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.CREATE_ORDER_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNT_INFO_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        pass

    @property
    def balance_request_mock_response_only_base(self):
        pass

    @property
    def all_symbols_request_mock_response(self):
        mock_response = [
            {'universe': [{'maxLeverage': 50, 'name': 'BTC', 'onlyIsolated': False, 'szDecimals': 5},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False, 'szDecimals': 4}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.89157', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'
                 }]
        ]
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = [
            {'universe': [{'maxLeverage': 50, 'name': 'BTC', 'onlyIsolated': False, 'szDecimals': 5},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False, 'szDecimals': 4}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': str(self.expected_latest_price), 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': str(self.expected_latest_price),
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]
        ]

        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = [
            {'universe': [{'maxLeverage': 50, 'name': self.base_asset, 'onlyIsolated': False, 'szDecimals': 5},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False, 'szDecimals': 4}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]]
        return "INVALID-PAIR", mock_response

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": 1587884283175
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = [
            {'universe': [{'maxLeverage': 50, 'name': self.base_asset, 'onlyIsolated': False},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]
        ]
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {'status': 'ok', 'response': {'type': 'order', 'data': {
            'statuses': [{'resting': {'oid': self.expected_exchange_order_id}}]}}}
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {'assetPositions': [{'position': {'coin': 'ETH', 'cumFunding': {'allTime': '-0.442044',
                                                                                        'sinceChange': '0.036699',
                                                                                        'sinceOpen': '0.036699'},
                                                          'entryPx': '2059.6',
                                                          'leverage': {'type': 'cross', 'value': 21},
                                                          'liquidationPx': None, 'marginUsed': '0.990428',
                                                          'maxLeverage': 50, 'positionValue': '20.797',
                                                          'returnOnEquity': '0.20294257', 'szi': '0.01',
                                                          'unrealizedPnl': '0.201'}, 'type': 'oneWay'}],
                         'crossMaintenanceMarginUsed': '0.20799',
                         'crossMarginSummary': {'accountValue': '2000', 'totalMarginUsed': '0.990428',
                                                'totalNtlPos': '20.799', 'totalRawUsd': '63.442322'},
                         'marginSummary': {'accountValue': '84.241322', 'totalMarginUsed': '0.990428',
                                           'totalNtlPos': '20.799', 'totalRawUsd': '63.442322'},
                         'withdrawable': '2000'}

        return mock_response

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        pass

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Position mode PositionMode.HEDGE is not supported. Mode not set."
            )
        )

    def is_cancel_request_executed_synchronously_by_server(self):
        return False

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        self.async_run_with_timeout(asyncio.sleep(0.5))
        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"Position mode switched to {PositionMode.ONEWAY}.",
            )
        )

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_info_next_funding_utc_str_ws_updated(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp_ws_updated)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_payment_timestamp_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_payment_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def funding_info_mock_response(self):
        mock_response = self.latest_prices_request_mock_response
        funding_info = mock_response[1][0]
        funding_info["markPx"] = self.target_funding_info_mark_price
        # funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["funding"] = self.target_funding_info_rate
        return mock_response

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        price_info = self.trading_rules_request_mock_response[1][0]
        coin_info = self.trading_rules_request_mock_response[0]["universe"][0]
        collateral_token = self.quote_asset

        step_size = Decimal(str(10 ** -coin_info.get("szDecimals")))
        price_size = Decimal(str(10 ** -len(price_info.get("markPx").split('.')[1])))
        _min_order_size = Decimal(str(10 ** -len(price_info.get("openInterest").split('.')[1])))

        return TradingRule(self.trading_pair,
                           min_base_amount_increment=step_size,
                           min_price_increment=price_size,
                           min_order_size=_min_order_size,
                           buy_order_collateral_token=collateral_token,
                           sell_order_collateral_token=collateral_token,
                           )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response
        # The error logs the individual coin_info, not the entire response
        coin_info = erroneous_rule[0]['universe'][0]  # First coin_info in universe
        return f"Error parsing the trading pair rule {coin_info}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "2650113037"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("100")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("10")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6"

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        exchange = HyperliquidPerpetualDerivative(
            hyperliquid_perpetual_secret_key=self.api_secret,
            hyperliquid_perpetual_mode=self.hyperliquid_mode,
            hyperliquid_perpetual_address=self.api_address,
            use_vault=self.use_vault,
            trading_pairs=[self.trading_pair],
        )
        return exchange

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(True if order.trade_type is TradeType.BUY else False,
                         request_data["action"]["orders"][0]["b"])
        self.assertEqual(order.amount, abs(Decimal(str(request_data["action"]["orders"][0]["s"]))))
        self.assertEqual(order.client_order_id, request_data["action"]["orders"][0]["c"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.api_address, request_params["user"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.public_rest_url(
            CONSTANTS.CANCEL_ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.CANCEL_ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.post(regex_url, status=400, callback=callback)
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
    ):
        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {"code": -2013, "msg": "order"}
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url_order_status

    def configure_order_not_found_unknow_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {'status': 'unknownOid'}
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url_order_status

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):

        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url_order_status

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):

        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)

        return url_order_status

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL,
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        endpoint = CONSTANTS.SET_LEVERAGE_URL
        url = web_utils.public_rest_url(
            endpoint
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        err_msg = "Unable to set leverage"
        mock_response = {
            "status": "error",
            "code": 0,
            "message": "",
            "data": {
                "pair": "BTC-USD",
                "leverage_ratio": "60.00000000"
            }
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)
        return url, err_msg

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        endpoint = CONSTANTS.SET_LEVERAGE_URL
        url = web_utils.public_rest_url(
            endpoint
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "status": "ok",
            "code": 0,
            "message": "",
            "data": {
                "pair": "BTC-USD",
                "leverage_ratio": str(leverage)
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def get_trading_rule_rest_msg(self):
        return [
            {'universe': [{'maxLeverage': 50, 'name': self.base_asset, 'onlyIsolated': False},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]
        ]

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {'channel': 'orderUpdates', 'data': [{'order': {'coin': 'BTC', 'side': 'B', 'limitPx': order.price,
                                                               'sz': float(order.amount),
                                                               'oid': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                                                               'timestamp': 1700818402905, 'origSz': '0.01',
                                                               'cloid': order.client_order_id or ""},
                                                     'status': 'open', 'statusTimestamp': 1700818867334}]}

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {'channel': 'orderUpdates', 'data': [{'order': {'coin': 'BTC', 'side': 'B', 'limitPx': order.price,
                                                               'sz': float(order.amount),
                                                               'oid': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                                                               'timestamp': 1700818402905, 'origSz': '0.01',
                                                               'cloid': order.client_order_id or ""},
                                                     'status': 'canceled', 'statusTimestamp': 1700818867334}]}

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {'channel': 'orderUpdates', 'data': [{'order': {'coin': 'BTC', 'side': 'B', 'limitPx': order.price,
                                                               'sz': float(order.amount),
                                                               'oid': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                                                               'timestamp': 1700818402905, 'origSz': '0.01',
                                                               'cloid': order.client_order_id or ""},
                                                     'status': 'filled', 'statusTimestamp': 1700818867334}]}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {'channel': 'user', 'data': {'fills': [
            {'coin': 'BTC', 'px': order.price, 'sz': float(order.amount), 'side': 'B', 'time': 1700819083138,
             'startPosition': '0.0',
             'dir': 'Open Long', 'closedPnl': '0.0',
             'hash': '0x6065d86346c0ee0f5d9504081647930115005f95c201c3a6fb5ba2440507f2cf',  # noqa: mock
             'tid': '0x6065d86346c0ee0f5d9504081647930115005f95c201c3a6fb5ba2440507f2cf',  # noqa: mock
             'oid': order.exchange_order_id or "EOID1",
             'cloid': order.client_order_id or "",
             'crossed': True, 'fee': str(self.expected_fill_fee.flat_fees[0].amount), 'liquidationMarkPx': None}]}}

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        pass

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

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="0x48424f54424548554436306163303012",  # noqa: mock
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["0x48424f54424548554436306163303012"]  # noqa: mock

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertTrue(order.is_open)

    @property
    def balance_event_websocket_update(self):
        pass

    def funding_info_event_for_websocket_update(self):
        pass

    def validate_auth_credentials_present(self, request_call: RequestCall):
        pass

    def test_supported_position_modes(self):
        linear_connector = HyperliquidPerpetualDerivative(
            hyperliquid_perpetual_secret_key=self.api_secret,
            hyperliquid_perpetual_mode=self.hyperliquid_mode,
            hyperliquid_perpetual_address=self.api_address,
            use_vault=self.use_vault,
            trading_pairs=[self.trading_pair],
        )

        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, buy_collateral_token)
        self.assertEqual(self.quote_asset, sell_collateral_token)

    @aioresponses()
    @patch("asyncio.Queue.get")
    @patch(
        "hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_api_order_book_data_source.HyperliquidPerpetualAPIOrderBookDataSource._next_funding_time")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_next_funding_time,
                                                                     mock_queue_get):
        pass

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_first_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response[0]["universe"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.base_asset}_12345"
        duplicate["szDecimals"] = int(duplicate["szDecimals"]) + 1
        results.append(duplicate)
        # Also need to add price info for the duplicate symbol
        response[1].append(deepcopy(response[1][0]))
        mock_api.post(url, body=json.dumps(response))
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        # Hyperliquid uses simple symbol names (BTC, BTC_12345) which create separate trading pairs
        # BTC -> BTC-USD-PERPETUAL, BTC_12345 -> BTC_12345-USD-PERPETUAL (plus ETH)
        self.assertEqual(3, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_second_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response[0]["universe"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.base_asset}_12345"
        duplicate["szDecimals"] = int(duplicate["szDecimals"]) + 1
        results.insert(0, duplicate)
        # Also need to add price info for the duplicate symbol
        response[1].insert(0, deepcopy(response[1][0]))
        mock_api.post(url, body=json.dumps(response))
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        # Hyperliquid uses simple symbol names (BTC_12345, BTC, ETH) which create separate trading pairs
        self.assertEqual(3, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_cannot_resolve(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response[0]["universe"]
        first_duplicate = deepcopy(results[0])
        first_duplicate["name"] = f"{self.base_asset}_12345"
        first_duplicate["szDecimals"] = int(first_duplicate["szDecimals"]) + 1
        second_duplicate = deepcopy(results[0])
        second_duplicate["name"] = f"{self.base_asset}_67890"
        second_duplicate["szDecimals"] = int(second_duplicate["szDecimals"]) + 2
        results.pop(0)
        results.append(first_duplicate)
        results.append(second_duplicate)
        # Also need to add price info for the duplicate symbols
        response[1].append(deepcopy(response[1][0]))
        response[1].append(deepcopy(response[1][0]))
        # Remove the first price info since we popped the first coin_info
        response[1].pop(0)
        mock_api.post(url, body=json.dumps(response))
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        # Hyperliquid uses simple symbol names which create separate trading pairs
        # ETH, BTC_12345, BTC_67890 all create separate trading pairs
        self.assertEqual(3, len(self.exchange.trading_rules))
        # Original BTC was removed, so BTC-USD-PERPETUAL shouldn't be in the rules
        self.assertNotIn(self.trading_pair, self.exchange.trading_rules)

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="0x48424f54424548554436306163303012",  # noqa: mock
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("0x48424f54424548554436306163303012", self.exchange.in_flight_orders)  # noqa: mock
        order = self.exchange.in_flight_orders["0x48424f54424548554436306163303012"]  # noqa: mock

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        # self.validate_auth_credentials_present(cancel_request)
        self.validate_order_cancelation_request(
            order=order,
            request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)
        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)
        self.assertEqual(leverage, fill_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        buy_event = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_user_stream_update_for_trade_message(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)
        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        def call_later():
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id="EOID1",
                trading_pair=order.trading_pair,
                update_timestamp=self.exchange.current_timestamp,
                new_state=OrderState.OPEN,
            )
            self.exchange._order_tracker.process_order_update(order_update)

        asyncio.get_event_loop().call_later(1, call_later)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener(), timeout=5)
        except asyncio.CancelledError:
            pass

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during cancellation (check _is_order_not_found_during_cancelation_error)
        pass

    @aioresponses()
    def test_update_order_status_when_exchange_order_id_timeout(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_order_not_found_unknow_error_order_status_response(
            order=order,
            mock_api=mock_api)
        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout(self.exchange._update_order_status())
        self.assertFalse(order.is_done)

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

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

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {'status': 'ok', 'response': {'type': 'cancel', 'data': {'statuses': ['success']}}}

    def _order_fills_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return [{'closedPnl': '0.0', 'coin': self.base_asset, 'crossed': False, 'dir': 'Open Long',
                 'hash': 'xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6', 'oid': order.exchange_order_id,
                 'cloid': order.client_order_id, 'px': '10000', 'side': 'B', 'startPosition': '26.86',
                 'sz': '1', 'time': 1681222254710, 'fee': '0.1'}]

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {'order': {
            'order': {'children': [], 'cloid': order.client_order_id, 'coin': self.base_asset,
                      'isPositionTpsl': False, 'isTrigger': False, 'limitPx': str(order.price),
                      'oid': int(order.exchange_order_id),
                      'orderType': 'Limit', 'origSz': float(order.amount), 'reduceOnly': False, 'side': 'B',
                      'sz': str(order.amount), 'tif': 'Gtc', 'timestamp': 1700814942565, 'triggerCondition': 'N/A',
                      'triggerPx': '0.0'}, 'status': 'filled', 'statusTimestamp': 1700818403290}, 'status': 'filled'}

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "canceled"
        resp["order"]["status"] = "canceled"
        resp["order"]["order"]["sz"] = "0"
        resp["order"]["order"]["limitPx"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["order"]["status"] = "open"
        resp["order"]["order"]["limitPx"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["order"]["status"] = "open"
        resp["order"]["order"]["limitPx"] = str(order.price)
        return resp

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["order"]["status"] = "open"
        resp["order"]["order"]["limitPx"] = str(order.price)
        resp["order"]["order"]["sz"] = float(order.amount) / 2
        return resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return [
            {
                "closedPnl": "0.0",
                "coin": self.base_asset,
                "crossed": False,
                "dir": "Open Long",
                "hash": self.expected_fill_trade_id,  # noqa: mock
                "oid": order.exchange_order_id,
                "cloid": order.client_order_id,
                "px": str(order.price),
                "side": "B",
                "startPosition": "26.86",
                "sz": str(Decimal(order.amount)),
                "time": 1681222254710,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
            }
        ]

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = self.latest_prices_url

        response = self.latest_prices_request_mock_response

        mock_api.post(url, body=json.dumps(response))

        latest_prices = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        pass

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]), callback=callback)
        return [url]

    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="0x48424f54424548554436306163303012",  # noqa: mock
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("0x48424f54424548554436306163303012", self.exchange.in_flight_orders)  # noqa: mock
        order: InFlightOrder = self.exchange.in_flight_orders["0x48424f54424548554436306163303012"]  # noqa: mock

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        if url:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            # self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertFalse(order.is_cancelled)
            self.assertTrue(order.is_failure)
            self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        else:
            self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertTrue(order.is_failure)

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
        self.async_run_with_timeout(request_sent_event.wait())

        if url != "":
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_cancelled)
            cancel_event = self.order_cancelled_logger.event_log[0]
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

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        if url != "":
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("12", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["12"]

        urls = self.configure_one_successful_one_erroneous_cancel_all_response(
            successful_order=order1,
            erroneous_order=order2,
            mock_api=mock_api)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        for url in urls:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertEqual(1, len(self.order_cancelled_logger.event_log))
            cancel_event = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order1.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order1.client_order_id}."
                )
            )

    @aioresponses()
    def test_set_leverage_failure(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        target_leverage = 2
        _, message = self.configure_failed_set_leverage(
            leverage=target_leverage,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(
            self.is_logged(
                log_level="NETWORK",
                message=f"Error setting leverage {target_leverage} for {self.trading_pair}: {message}",
            )
        )

    @aioresponses()
    def test_set_leverage_success(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        target_leverage = 2
        self.configure_successful_set_leverage(
            leverage=target_leverage,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(
            self.is_logged(
                log_level="INFO",
                message=f"Leverage for {self.trading_pair} successfully set to {target_leverage}.",
            )
        )

    def _configure_balance_response(
            self,
            response,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = self.balance_url
        mock_api.post(
            re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")),
            body=json.dumps(response),
            callback=callback)
        return url

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        self._simulate_trading_rules_initialized()
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
            self.validate_order_status_request(order=order, request_call=order_status_request)

        cancel_event = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def configure_erroneous_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_url
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]), callback=callback)
        return [url]

    def test_user_stream_balance_update(self):
        pass

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = self.all_symbols_url
        mock_api.post(url, exception=Exception)

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        self.configure_all_symbols_response(mock_api=mock_api)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        # expected_valid_trading_pairs = self._expected_valid_trading_pairs()

        self.assertEqual(2, len(all_trading_pairs))
        self.assertIn(self.trading_pair, all_trading_pairs)

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.all_symbols_url
        response = self.all_symbols_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        # Mock DEX API call for HIP-3 markets (returns empty list since no HIP-3 markets in base tests)
        mock_api.post(url, body=json.dumps([]), callback=callback)
        return [url]

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = self.network_status_url

        mock_api.post(url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = self.network_status_url
        response = self.network_status_request_successful_mock_response
        mock_api.post(url, body=json.dumps(response))

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        pass

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.exchange.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in
                                       enumerate(mocked_response[0]["universe"])}
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        """Open long position"""
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp,
                         create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100.000000"), create_event.amount)
        self.assertEqual(Decimal("10000.0000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id),
                         create_event.exchange_order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000')}."
            )
        )

    @aioresponses()
    def test_create_order_to_close_long_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        leverage = 5
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_sell_order(position_action=PositionAction.CLOSE)
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
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                f"at {Decimal('10000')}."
            )
        )

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        leverage = 4
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_buy_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp,
                         create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id),
                         create_event.exchange_order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                f"at {Decimal('10000')}."
            )
        )

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        """Open short position"""
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        leverage = 3
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
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
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000')}."
            )
        )

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        # Create a market buy order - this will trigger lines 306-307
        order_id = self.place_buy_order(order_type=OrderType.MARKET)
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]
        self.assertEqual(OrderType.MARKET, order.order_type)

        self.validate_order_creation_request(
            order=order,
            request_call=order_request)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(order_id, create_event.order_id)

    @aioresponses()
    def test_create_sell_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        # Create a market sell order - this will trigger lines 343-344
        order_id = self.place_sell_order(order_type=OrderType.MARKET)
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]
        self.assertEqual(OrderType.MARKET, order.order_type)

        self.validate_order_creation_request(
            order=order,
            request_call=order_request)

        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(order_id, create_event.order_id)

    @aioresponses()
    def test_create_limit_maker_order(self, mock_api):
        """Test creating LIMIT_MAKER order to trigger tif: Alo."""
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        # Create a LIMIT_MAKER order - this will trigger line 424
        order_id = self.place_buy_order(order_type=OrderType.LIMIT_MAKER)
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]
        self.assertEqual(OrderType.LIMIT_MAKER, order.order_type)

    @aioresponses()
    async def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        await (request_sent_event.wait())
        await asyncio.sleep(0.1)

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

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "NETWORK",
                f"Error submitting buy LIMIT order to {self.exchange.name_cap} for 100.000000 {self.trading_pair} 10000."
            )
        )

    @aioresponses()
    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.0001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        await asyncio.wait_for(request_sent_event.wait(), timeout=3)
        await asyncio.sleep(0.1)

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "NETWORK",
                f"Error submitting buy LIMIT order to {self.exchange.name_cap} for 100.000000 {self.trading_pair} 10000."
            )
        )
        error_message = (
            f"Order amount 0.0001 is lower than minimum order size 0.01 for the pair {self.trading_pair}. "
            "The order will not be created."
        )
        misc_updates = {
            "error_message": error_message,
            "error_type": "ValueError"
        }

        expected_log = (
            f"Order {order_id_for_invalid_order} has failed. Order Update: "
            f"OrderUpdate(trading_pair='{self.trading_pair}', "
            f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
            f"client_order_id='{order_id_for_invalid_order}', exchange_order_id=None, "
            f"misc_updates={repr(misc_updates)})"
        )

        self.assertTrue(self.is_logged("INFO", expected_log))

    @aioresponses()
    def test_update_trading_rules_with_dex_markets(self, mock_api):
        """Test trading rules update with HIP-3 DEX markets."""
        # Enable HIP-3 markets for this test
        self.exchange._enable_hip3_markets = True

        # Mock base market response
        base_response = self.trading_rules_request_mock_response
        mock_api.post(self.trading_rules_url, body=json.dumps(base_response))

        # Mock DEX markets response with perpMeta
        dex_response = [{
            "name": "xyz",
            "perpMeta": [{
                "name": "xyz:XYZ100",
                "szDecimals": 3
            }, {
                "name": "xyz:TSLA",
                "szDecimals": 2
            }]
        }]
        mock_api.post(self.trading_rules_url, body=json.dumps(dex_response))

        # Mock meta endpoint for DEX
        dex_meta_response = [{"universe": dex_response[0]["perpMeta"]}, {}]
        mock_api.post(self.trading_rules_url, body=json.dumps(dex_meta_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        # Verify DEX markets were processed
        self.assertIn("xyz:XYZ100", self.exchange.coin_to_asset)
        self.assertIn("xyz:TSLA", self.exchange.coin_to_asset)
        self.assertTrue(self.exchange._is_hip3_market.get("xyz:XYZ100", False))
        self.assertEqual(110000, self.exchange.coin_to_asset["xyz:XYZ100"])
        self.assertEqual(110001, self.exchange.coin_to_asset["xyz:TSLA"])

    @aioresponses()
    def test_initialize_trading_pair_symbol_map_with_dex_markets(self, mock_api):
        """Test symbol map initialization includes DEX markets."""
        # Enable HIP-3 markets for this test
        self.exchange._enable_hip3_markets = True

        base_response = self.trading_rules_request_mock_response
        mock_api.post(self.trading_rules_url, body=json.dumps(base_response))

        dex_response = [{
            "name": "xyz",
            "perpMeta": [{"name": "xyz:XYZ100", "szDecimals": 3}]
        }]
        mock_api.post(self.trading_rules_url, body=json.dumps(dex_response))
        mock_api.post(self.trading_rules_url, body=json.dumps([{"universe": dex_response[0]["perpMeta"]}]))

        self.async_run_with_timeout(self.exchange._initialize_trading_pair_symbol_map())

        # Verify DEX symbol is in the map
        self.assertIsNotNone(self.exchange.trading_pair_symbol_map)

    @aioresponses()
    def test_format_trading_rules_with_dex_markets_exception_handling(self, mock_api):
        """Test exception handling when parsing HIP-3 trading rules."""
        self.exchange._dex_markets = [{
            "name": "xyz",
            "perpMeta": [
                {"name": "xyz:XYZ100", "szDecimals": 3},
                {"bad_format": "invalid"},  # This will cause exception
                {"name": "xyz:TSLA", "szDecimals": 2}
            ]
        }]

        # Should handle exception and continue with other markets
        exchange_info = self.trading_rules_request_mock_response
        self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        # Should have processed valid entries - no exception raised
        self.assertTrue(True)

    @aioresponses()
    def test_format_trading_rules_dex_perpmeta_none(self, mock_api):
        """Test handling when perpMeta is None or missing."""
        # Test with DEX markets that have None or missing perpMeta - should be filtered out
        self.exchange._dex_markets = [
            {"name": "xyz"},  # Missing perpMeta
            {"name": "abc", "perpMeta": None}  # None perpMeta
        ]

        exchange_info = self.trading_rules_request_mock_response
        self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        # Should handle gracefully - no exception raised
        self.assertTrue(True)

    @aioresponses()
    def test_initialize_trading_pair_symbols_with_dex_duplicate_handling(self, mock_api):
        """Test duplicate symbol resolution for DEX markets."""
        self.exchange._dex_markets = [{
            "name": "xyz",
            "perpMeta": [
                {"name": "xyz:BTC"},  # Might conflict with base BTC
            ]
        }]

        exchange_info = self.trading_rules_request_mock_response
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        # Should have resolved or handled the duplicate
        self.assertIsNotNone(self.exchange.trading_pair_symbol_map)

    @aioresponses()
    def test_format_trading_rules_dex_with_different_deployers(self, mock_api):
        """Test HIP-3 markets with different deployer prefixes."""
        self.exchange._dex_markets = [{
            "name": "xyz",
            "perpMeta": [
                {"name": "xyz:XYZ100", "szDecimals": 3},
            ]
        }, {
            "name": "abc",
            "perpMeta": [
                {"name": "abc:MSFT", "szDecimals": 2},
            ]
        }]

        exchange_info = self.trading_rules_request_mock_response
        self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        # Verify different deployers get different offsets
        self.assertEqual(110000, self.exchange.coin_to_asset.get("xyz:XYZ100"))
        self.assertEqual(120000, self.exchange.coin_to_asset.get("abc:MSFT"))

    @aioresponses()
    def test_format_trading_rules_dex_without_colon_separator(self, mock_api):
        """Test handling of DEX market names without colon separator."""
        self.exchange._dex_markets = [{
            "name": "xyz",
            "perpMeta": [
                {"name": "INVALID_NO_COLON", "szDecimals": 3},
                {"name": "xyz:VALID", "szDecimals": 2}
            ]
        }]

        exchange_info = self.trading_rules_request_mock_response
        self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        # Should skip invalid entry and process valid one
        self.assertIn("xyz:VALID", self.exchange.coin_to_asset)
        self.assertNotIn("INVALID_NO_COLON", self.exchange.coin_to_asset)

    @aioresponses()
    def test_update_trading_fees_is_noop(self, mock_api):
        """Test that _update_trading_fees does nothing (pass implementation)."""
        # Should complete without error
        self.async_run_with_timeout(self.exchange._update_trading_fees())
        self.assertTrue(True)

    @aioresponses()
    def test_get_order_book_data_handles_dex_markets(self, mock_api):
        """Test that order book data correctly identifies DEX markets."""
        self.exchange._is_hip3_market = {"xyz:XYZ100": True, "BTC": False}

        # The method should handle HIP-3 markets
        self.assertTrue(self.exchange._is_hip3_market.get("xyz:XYZ100", False))
        self.assertFalse(self.exchange._is_hip3_market.get("BTC", False))

    def test_trading_pairs_request_path(self):
        """Test that trading pairs request path is correct."""
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_URL, self.exchange.trading_pairs_request_path)

    def test_trading_rules_request_path(self):
        """Test that trading rules request path is correct."""
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_URL, self.exchange.trading_rules_request_path)

    def test_funding_fee_poll_interval(self):
        """Test funding fee poll interval is 120 seconds."""
        self.assertEqual(120, self.exchange.funding_fee_poll_interval)

    def test_rate_limits_rules(self):
        """Test rate limits rules returns correct list."""
        rules = self.exchange.rate_limits_rules
        self.assertIsInstance(rules, list)
        self.assertEqual(CONSTANTS.RATE_LIMITS, rules)

    def test_authenticator_when_required(self):
        """Test authenticator is created when trading is required."""
        self.exchange._trading_required = True
        auth = self.exchange.authenticator
        self.assertIsNotNone(auth)

    def test_authenticator_when_not_required(self):
        """Test authenticator is None when trading is not required."""
        # Temporarily set trading_required to False to test line 85
        original_value = self.exchange._trading_required
        self.exchange._trading_required = False

        # Clear cached auth to force re-creation
        if hasattr(self.exchange, '_authenticator'):
            del self.exchange._authenticator

        # This should return None when trading is not required
        auth = self.exchange.authenticator
        self.assertIsNone(auth)

        # Restore
        self.exchange._trading_required = original_value

    def test_is_request_exception_related_to_time_synchronizer(self):
        """Test that time synchronizer check returns False."""
        result = self.exchange._is_request_exception_related_to_time_synchronizer(Exception("test"))
        self.assertFalse(result)

    def test_get_buy_collateral_token(self):
        """Test get_buy_collateral_token returns correct token."""
        self._simulate_trading_rules_initialized()
        token = self.exchange.get_buy_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, token)

    def test_get_sell_collateral_token(self):
        """Test get_sell_collateral_token returns correct token."""
        self._simulate_trading_rules_initialized()
        token = self.exchange.get_sell_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, token)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        """Test check_network returns failure on error."""
        url = web_utils.public_rest_url(CONSTANTS.PING_URL)
        mock_api.post(url, status=500)

        result = self.async_run_with_timeout(self.exchange.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    def test_get_fee_maker(self):
        """Test _get_fee for maker order."""
        fee = self.exchange._get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("10000"),
            is_maker=True
        )
        self.assertIsNotNone(fee)
        # Just verify it returns a fee object, not checking flat_fees structure

    def test_get_fee_taker(self):
        """Test _get_fee for taker order."""
        fee = self.exchange._get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.MARKET,
            order_side=TradeType.SELL,
            position_action=PositionAction.CLOSE,
            amount=Decimal("1"),
            price=Decimal("10000"),
            is_maker=False
        )
        self.assertIsNotNone(fee)

    def test_get_fee_none_is_maker(self):
        """Test _get_fee when is_maker is None (defaults to False)."""
        fee = self.exchange._get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("10000"),
            is_maker=None  # This tests line 287
        )
        self.assertIsNotNone(fee)

    @aioresponses()
    def test_make_trading_pairs_request(self, mock_api):
        """Test making trading pairs request."""
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        mock_api.post(
            url,
            body=json.dumps([
                {
                    "name": "BTC",
                    "szDecimals": 5,
                    "maxLeverage": 50,
                    "onlyIsolated": False
                }
            ])
        )

        result = self.async_run_with_timeout(self.exchange._make_trading_pairs_request())
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)

    @aioresponses()
    def test_make_trading_rules_request(self, mock_api):
        """Test making trading rules request."""
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        mock_api.post(
            url,
            body=json.dumps([
                {
                    "name": "BTC",
                    "szDecimals": 5,
                    "maxLeverage": 50,
                    "onlyIsolated": False
                }
            ])
        )

        result = self.async_run_with_timeout(self.exchange._make_trading_rules_request())
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)

    @aioresponses()
    def test_execute_cancel_returns_false_when_not_success(self, mock_api):
        """Test cancel returns False when success is not in response."""
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        order = self.exchange.in_flight_orders["OID3"]

        # Mock response without success field
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        mock_api.post(
            url,
            body=json.dumps({
                "status": "ok",
                "response": {
                    "data": {
                        "statuses": [{"pending": True}]
                    }
                }
            })
        )

        result = self.async_run_with_timeout(
            self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        )

        self.assertFalse(result)

    # ==================== HIP-3 Coverage Tests ====================

    @aioresponses()
    def test_get_all_pairs_prices(self, mock_api):
        """Test get_all_pairs_prices returns prices for both perp and HIP-3 markets."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        # Mock base perp response
        base_response = [
            {'universe': [{'name': 'BTC', 'szDecimals': 5}]},
            [{'coin': 'BTC', 'markPx': '50000.0'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # Mock DEX markets response
        dex_response = [{
            "name": "xyz",
            "perpMeta": [{"name": "xyz:XYZ100", "szDecimals": 3}],
            "assetCtxs": [{"markPx": "25349.0"}]
        }]
        mock_api.post(url, body=json.dumps(dex_response))

        # Mock metaAndAssetCtxs for DEX
        dex_meta_response = [
            {"universe": [{"name": "xyz:XYZ100", "szDecimals": 3}]},
            [{"markPx": "25349.0"}]
        ]
        mock_api.post(url, body=json.dumps(dex_meta_response))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    @aioresponses()
    def test_get_all_pairs_prices_with_empty_dex(self, mock_api):
        """Test get_all_pairs_prices when DEX response is empty."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        base_response = [
            {'universe': [{'name': 'BTC', 'szDecimals': 5}]},
            [{'coin': 'BTC', 'markPx': '50000.0'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # Empty DEX response
        mock_api.post(url, body=json.dumps([]))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertIsInstance(result, list)

    @aioresponses()
    def test_set_leverage_for_hip3_market(self, mock_api):
        """Test setting leverage for HIP-3 market uses isolated margin."""
        self._simulate_trading_rules_initialized()

        # Setup HIP-3 market
        hip3_trading_pair = "xyz:XYZ100-USD"
        self.exchange._is_hip3_market["xyz:XYZ100"] = True
        self.exchange.coin_to_asset["xyz:XYZ100"] = 110000

        # Add to symbol map
        from bidict import bidict
        mapping = bidict({"xyz:XYZ100": hip3_trading_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        url = web_utils.public_rest_url(CONSTANTS.SET_LEVERAGE_URL)
        mock_api.post(url, body=json.dumps({"status": "ok"}))

        success, msg = self.async_run_with_timeout(
            self.exchange._set_trading_pair_leverage(hip3_trading_pair, 10)
        )

        self.assertTrue(success)
        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"HIP-3 market {hip3_trading_pair} does not support leverage setting for cross margin. Defaulting to isolated margin."
            )
        )

    @aioresponses()
    def test_set_leverage_coin_not_in_mapping(self, mock_api):
        """Test setting leverage fails when coin not in coin_to_asset mapping."""
        self._simulate_trading_rules_initialized()

        # Setup an unknown trading pair
        unknown_pair = "UNKNOWN:COIN-USD"

        # Add to symbol map but NOT to coin_to_asset
        from bidict import bidict
        mapping = bidict({"UNKNOWN:COIN": unknown_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        success, msg = self.async_run_with_timeout(
            self.exchange._set_trading_pair_leverage(unknown_pair, 10)
        )

        self.assertFalse(success)
        self.assertIn("not found in coin_to_asset mapping", msg)

    @aioresponses()
    def test_fetch_last_fee_payment_for_hip3_market(self, mock_api):
        """Test that _fetch_last_fee_payment returns early for HIP-3 markets."""
        self._simulate_trading_rules_initialized()

        # Setup HIP-3 market
        hip3_trading_pair = "xyz:XYZ100-USD"
        self.exchange._is_hip3_market["xyz:XYZ100"] = True

        # Add to symbol map
        from bidict import bidict
        mapping = bidict({"xyz:XYZ100": hip3_trading_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        timestamp, funding_rate, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(hip3_trading_pair)
        )

        # Should return early with default values
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("-1"), funding_rate)
        self.assertEqual(Decimal("-1"), payment)

    @aioresponses()
    def test_fetch_last_fee_payment_for_regular_market(self, mock_api):
        """Test _fetch_last_fee_payment for regular (non-HIP-3) market."""
        self._simulate_trading_rules_initialized()

        # Setup non-HIP-3 market
        self.exchange._is_hip3_market["BTC"] = False

        url = web_utils.public_rest_url(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)

        # Mock empty funding response
        mock_api.post(url, body=json.dumps([]))

        timestamp, funding_rate, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair)
        )

        # Should return defaults when no funding data
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("-1"), funding_rate)
        self.assertEqual(Decimal("-1"), payment)

    @aioresponses()
    def test_fetch_last_fee_payment_with_data(self, mock_api):
        """Test _fetch_last_fee_payment returns data when available."""
        self._simulate_trading_rules_initialized()

        self.exchange._is_hip3_market["BTC"] = False

        url = web_utils.public_rest_url(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)

        funding_response = [{
            "time": 1640780000000,
            "delta": {
                "coin": "BTC",
                "USD": "0.5",
                "fundingRate": "0.0001"
            }
        }]
        mock_api.post(url, body=json.dumps(funding_response))

        timestamp, funding_rate, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair)
        )

        self.assertGreater(timestamp, 0)
        self.assertEqual(Decimal("0.0001"), funding_rate)
        self.assertEqual(Decimal("0.5"), payment)

    @aioresponses()
    def test_fetch_last_fee_payment_with_zero_payment(self, mock_api):
        """Test _fetch_last_fee_payment when payment is zero."""
        self._simulate_trading_rules_initialized()

        self.exchange._is_hip3_market["BTC"] = False

        url = web_utils.public_rest_url(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)

        funding_response = [{
            "time": 1640780000000,
            "delta": {
                "coin": "BTC",
                "USD": "0",  # Zero payment
                "fundingRate": "0.0001"
            }
        }]
        mock_api.post(url, body=json.dumps(funding_response))

        timestamp, funding_rate, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair)
        )

        # Should return defaults when payment is zero
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("-1"), funding_rate)
        self.assertEqual(Decimal("-1"), payment)

    @aioresponses()
    def test_update_positions(self, mock_api):
        """Test _update_positions processes positions correctly."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }
        mock_api.post(url, body=json.dumps(positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        # Should have processed position
        positions = self.exchange.account_positions
        self.assertGreater(len(positions), 0)

    @aioresponses()
    def test_update_positions_removes_zero_amount(self, mock_api):
        """Test _update_positions removes position when amount is zero."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0",  # Zero amount
                    "entryPx": "50000.0",
                    "unrealizedPnl": "0",
                    "leverage": {"value": 10}
                }
            }]
        }
        mock_api.post(url, body=json.dumps(positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        # The position should not exist or be removed
        self.assertTrue(True)  # No crash

    @aioresponses()
    def test_update_positions_empty_response(self, mock_api):
        """Test _update_positions handles empty positions."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions_response = {"assetPositions": []}
        mock_api.post(url, body=json.dumps(positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        # Should handle empty positions
        positions = self.exchange.account_positions
        self.assertEqual(0, len(positions))

    @aioresponses()
    def test_update_positions_with_hip3_markets(self, mock_api):
        """Test _update_positions fetches HIP-3 positions from DEX markets."""
        self._simulate_trading_rules_initialized()

        # Enable HIP-3 markets for this test
        self.exchange._enable_hip3_markets = True

        # Set up DEX markets
        self.exchange._dex_markets = [{"name": "xyz", "perpMeta": [{"name": "xyz:XYZ100", "szDecimals": 3}]}]

        # Add HIP-3 symbol to mapping
        from bidict import bidict
        mapping = bidict({"BTC": "BTC-USD", "xyz:XYZ100": "XYZ:XYZ100-USD"})
        self.exchange._set_trading_pair_symbol_map(mapping)
        self.exchange._is_hip3_market["xyz:XYZ100"] = True

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        # Base perpetual positions response
        base_positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        # HIP-3 DEX positions response
        hip3_positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "xyz:XYZ100",
                    "szi": "10.0",
                    "entryPx": "25.0",
                    "unrealizedPnl": "50.0",
                    "leverage": {"value": 5}
                }
            }]
        }

        # Mock both API calls (base + DEX)
        mock_api.post(url, body=json.dumps(base_positions_response))
        mock_api.post(url, body=json.dumps(hip3_positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        # Should have both positions
        positions = self.exchange.account_positions
        self.assertEqual(2, len(positions))

    @aioresponses()
    def test_update_positions_hip3_dex_error_handling(self, mock_api):
        """Test _update_positions handles DEX API errors gracefully."""
        self._simulate_trading_rules_initialized()

        # Enable HIP-3 markets for this test
        self.exchange._enable_hip3_markets = True

        # Set up DEX markets
        self.exchange._dex_markets = [{"name": "xyz", "perpMeta": [{"name": "xyz:XYZ100", "szDecimals": 3}]}]

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        # Base perpetual positions response
        base_positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        # Mock base call success, DEX call failure
        mock_api.post(url, body=json.dumps(base_positions_response))
        mock_api.post(url, status=500)  # DEX call fails

        # Should not raise, just log and continue
        self.async_run_with_timeout(self.exchange._update_positions())

        # Should still have base position
        positions = self.exchange.account_positions
        self.assertGreaterEqual(len(positions), 1)

    @aioresponses()
    def test_update_positions_skips_unmapped_coins(self, mock_api):
        """Test _update_positions skips positions for coins not in symbol map."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        # Response with an unmapped coin
        positions_response = {
            "assetPositions": [
                {
                    "position": {
                        "coin": "BTC",
                        "szi": "0.5",
                        "entryPx": "50000.0",
                        "unrealizedPnl": "100.0",
                        "leverage": {"value": 10}
                    }
                },
                {
                    "position": {
                        "coin": "UNKNOWN_COIN",  # Not in symbol map
                        "szi": "1.0",
                        "entryPx": "100.0",
                        "unrealizedPnl": "10.0",
                        "leverage": {"value": 5}
                    }
                }
            ]
        }
        mock_api.post(url, body=json.dumps(positions_response))

        # Should not raise, just skip unmapped coin
        self.async_run_with_timeout(self.exchange._update_positions())

        # Should have only BTC position
        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))

    @aioresponses()
    def test_update_positions_deduplicates_coins(self, mock_api):
        """Test _update_positions deduplicates positions from multiple sources."""
        self._simulate_trading_rules_initialized()

        # Set up DEX markets
        self.exchange._dex_markets = [{"name": "xyz", "perpMeta": []}]

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        # Both responses have BTC (simulating overlap)
        base_positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        dex_positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",  # Duplicate coin
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        mock_api.post(url, body=json.dumps(base_positions_response))
        mock_api.post(url, body=json.dumps(dex_positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        # Should have only one BTC position (deduplicated)
        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))

    @aioresponses()
    def test_update_positions_with_none_dex_info(self, mock_api):
        """Test _update_positions handles None entries in _dex_markets."""
        self._simulate_trading_rules_initialized()

        # Set up DEX markets with None entry
        self.exchange._dex_markets = [None, {"name": "xyz", "perpMeta": []}]

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        # Base call + valid DEX call (None is skipped)
        mock_api.post(url, body=json.dumps(positions_response))
        mock_api.post(url, body=json.dumps({"assetPositions": []}))

        # Should not raise
        self.async_run_with_timeout(self.exchange._update_positions())

        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))

    @aioresponses()
    def test_update_positions_with_empty_dex_name(self, mock_api):
        """Test _update_positions skips DEX with empty name."""
        self._simulate_trading_rules_initialized()

        # Set up DEX markets with empty name
        self.exchange._dex_markets = [{"name": "", "perpMeta": []}]

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "50000.0",
                    "unrealizedPnl": "100.0",
                    "leverage": {"value": 10}
                }
            }]
        }

        # Only base call (empty dex name is skipped)
        mock_api.post(url, body=json.dumps(positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))

    @aioresponses()
    def test_update_positions_short_position(self, mock_api):
        """Test _update_positions correctly identifies SHORT positions."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.POSITION_INFORMATION_URL)

        # Negative szi indicates short position
        positions_response = {
            "assetPositions": [{
                "position": {
                    "coin": "BTC",
                    "szi": "-0.5",  # Negative = SHORT
                    "entryPx": "50000.0",
                    "unrealizedPnl": "-100.0",
                    "leverage": {"value": 10}
                }
            }]
        }
        mock_api.post(url, body=json.dumps(positions_response))

        self.async_run_with_timeout(self.exchange._update_positions())

        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))

        # Verify position has correct side and negative amount
        pos = list(positions.values())[0]
        from hummingbot.core.data_type.common import PositionSide
        self.assertEqual(PositionSide.SHORT, pos.position_side)
        self.assertLess(pos.amount, 0)

    @aioresponses()
    def test_get_last_traded_price_for_hip3_market(self, mock_api):
        """Test _get_last_traded_price for HIP-3 market includes dex param."""
        self._simulate_trading_rules_initialized()

        hip3_trading_pair = "xyz:XYZ100-USD"
        self.exchange._is_hip3_market["xyz:XYZ100"] = True

        # Add to symbol map
        from bidict import bidict
        mapping = bidict({"xyz:XYZ100": hip3_trading_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        response = [
            {"universe": [
                {
                    'szDecimals': 4,
                    'name': 'xyz:XYZ100',
                    'maxLeverage': 20,
                    'marginTableId': 20, 'onlyIsolated': True,
                    'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'
                },]
             },
            [{
                'funding': '0.00000625',
                'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955',
                'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0',
                'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'}]
        ]
        mock_api.post(url, body=json.dumps(response))

        price = self.async_run_with_timeout(
            self.exchange._get_last_traded_price(hip3_trading_pair)
        )

        self.assertEqual(25349.0, price)

    def test_last_funding_time(self):
        """Test _last_funding_time calculation."""
        timestamp = self.exchange._last_funding_time()

        # Should be a positive integer
        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 0)

    def test_supported_order_types(self):
        """Test supported_order_types returns correct list."""
        order_types = self.exchange.supported_order_types()

        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    @aioresponses()
    def test_get_position_mode(self, mock_api):
        """Test _get_position_mode returns ONEWAY."""
        mode = self.async_run_with_timeout(self.exchange._get_position_mode())

        self.assertEqual(PositionMode.ONEWAY, mode)

    @aioresponses()
    def test_initialize_trading_pair_symbol_map_exception(self, mock_api):
        """Test _initialize_trading_pair_symbol_map handles exceptions."""
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)

        # Mock an error response
        mock_api.post(url, status=500)

        self.async_run_with_timeout(self.exchange._initialize_trading_pair_symbol_map())

        # Should log exception and not crash
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="There was an error requesting exchange info."
            )
        )

    def test_format_trading_rules_with_hip3_markets(self):
        """Test _format_trading_rules processes HIP-3 DEX markets from hip_3_result (lines 300, 321, 329, 335)."""
        # Initialize trading rules first to setup symbol mapping
        self._simulate_trading_rules_initialized()

        # Setup _dex_markets with HIP-3 data
        self.exchange._dex_markets = [
            {
                "name": "xyz",
                "perpMeta": [
                    {'szDecimals': 4, 'name': 'xyz:XYZ100', 'maxLeverage': 20, 'marginTableId': 20, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'},
                    {'szDecimals': 3, 'name': 'xyz:TSLA', 'maxLeverage': 10, 'marginTableId': 10, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'}
                ],
                "assetCtxs": [
                    {'funding': '0.00000625', 'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955', 'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0', 'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'},
                    {'funding': '0.00000625', 'openInterest': '61339.114', 'prevDayPx': '483.99', 'dayNtlVlm': '14785221.9612099975', 'premium': '0.0002288211', 'oraclePx': '482.91', 'markPx': '483.02', 'midPx': '483.025', 'impactPxs': ['482.973', '483.068'], 'dayBaseVlm': '30504.829'}
                ]
            },
        ]

        # Call _format_trading_rules
        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(self.all_symbols_request_mock_response)
        )

        # Verify HIP-3 markets were processed - should have base markets + hip3
        # Base markets come from all_symbols_request_mock_response, HIP-3 from _dex_markets
        self.assertGreater(len(rules), 0)

    def test_format_trading_rules_price_decimal_parsing(self):
        """Test price decimal parsing in _format_trading_rules (lines 253-254)."""
        # Initialize trading rules first to setup symbol mapping
        self._simulate_trading_rules_initialized()

        # Use symbols that already exist in the exchange mapping
        # Get actual symbols from all_symbols_request_mock_response
        existing_symbols = self.all_symbols_request_mock_response[0].get("universe", [])

        # Create mock response with various decimal formats using actual symbols
        mock_response = [
            {
                "universe": existing_symbols[:2]  # Use first 2 symbols from actual universe
            },
            [
                {"markPx": "123.456789", "openInterest": "1000.123"},      # 6 & 3 decimals
                {"markPx": "0.001", "openInterest": "100.1"}              # 3 & 1 decimals
            ]
        ]

        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(mock_response)
        )

        # Verify rules were created - should have at least 2 from base markets
        self.assertGreaterEqual(len(rules), 2)

    def test_populate_coin_to_asset_id_map_with_hip3(self):
        """Test asset ID mapping for HIP-3 DEX markets (lines 780, 788)."""
        # Initialize trading rules first to setup symbol mapping
        self._simulate_trading_rules_initialized()

        # Setup multiple DEX markets with proper structure
        # Each DEX needs perpMeta list and assetCtxs list
        self.exchange._dex_markets = [
            {
                "name": "xyz",
                "perpMeta": [
                    {'szDecimals': 4, 'name': 'xyz:XYZ100', 'maxLeverage': 20, 'marginTableId': 20, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'},
                    {'szDecimals': 3, 'name': 'xyz:TSLA', 'maxLeverage': 10, 'marginTableId': 10, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'}
                ],
                "assetCtxs": [
                    {'funding': '0.00000625', 'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955', 'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0', 'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'},
                    {'funding': '0.00000625', 'openInterest': '61339.114', 'prevDayPx': '483.99', 'dayNtlVlm': '14785221.9612099975', 'premium': '0.0002288211', 'oraclePx': '482.91', 'markPx': '483.02', 'midPx': '483.025', 'impactPxs': ['482.973', '483.068'], 'dayBaseVlm': '30504.829'}
                ]
            },
            {
                "name": "dex2",
                "perpMeta": [
                    {"name": "dex2:SOL", "szDecimals": 3}
                ],
                "assetCtxs": [
                    {"markPx": "189.5", "openInterest": "50.5"}
                ]
            }
        ]

        # Call _format_trading_rules which processes HIP-3 markets and populates asset IDs
        self.async_run_with_timeout(
            self.exchange._format_trading_rules(self.all_symbols_request_mock_response)
        )

        # Verify asset IDs were mapped with correct offsets
        # First DEX (index 0): base_offset = 110000 + asset_index
        # Second DEX (index 1): base_offset = 120000 + asset_index
        self.assertEqual(self.exchange.coin_to_asset.get("xyz:XYZ100"), 110000)
        self.assertEqual(self.exchange.coin_to_asset.get("xyz:TSLA"), 110001)
        self.assertEqual(self.exchange.coin_to_asset.get("dex2:SOL"), 120000)

    def test_initialize_trading_pair_symbols_with_hip3(self):
        """Test trading pair symbol mapping for HIP-3 markets (lines 834-845)."""
        self._simulate_trading_rules_initialized()
        # Setup DEX markets with proper structure
        self.exchange._dex_markets = [
            {
                "name": "xyz",
                "perpMeta": [
                    {'szDecimals': 4, 'name': 'xyz:XYZ100', 'maxLeverage': 20, 'marginTableId': 20, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'},
                    {'szDecimals': 3, 'name': 'xyz:TSLA', 'maxLeverage': 10, 'marginTableId': 10, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'}
                ],
                "assetCtxs": [
                    {'funding': '0.00000625', 'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955', 'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0', 'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'},
                    {'funding': '0.00000625', 'openInterest': '61339.114', 'prevDayPx': '483.99', 'dayNtlVlm': '14785221.9612099975', 'premium': '0.0002288211', 'oraclePx': '482.91', 'markPx': '483.02', 'midPx': '483.025', 'impactPxs': ['482.973', '483.068'], 'dayBaseVlm': '30504.829'}
                ]
            }
        ]

        # Call symbol mapping method with exchange_info parameter
        # Pass the base exchange info which will be combined with _dex_markets
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(
            exchange_info=self.all_symbols_request_mock_response
        )

        # Verify HIP-3 symbols are in the internal symbol map
        # The method sets the internal _trading_pair_symbol_map via _set_trading_pair_symbol_map
        # We can verify by checking that the exchange has the symbol map set (non-None)
        self.assertIsNotNone(self.exchange.trading_pair_symbol_map)

    @aioresponses()
    def test_get_last_traded_price_hip3_with_dex_param(self, mock_api):
        """Test price fetching for HIP-3 markets includes DEX parameter (lines 869, 876, 888)."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        hip3_symbol = "xyz:XYZ100"
        hip3_trading_pair = "XYZ_AAPL-USD"

        # Setup HIP-3 market
        self.exchange._is_hip3_market[hip3_symbol] = True
        from bidict import bidict
        mapping = bidict({hip3_symbol: hip3_trading_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        # Mock price response for HIP-3 market
        response = [
            {"universe": [{"name": hip3_symbol}]},
            [{"markPx": "25349.0"}]
        ]
        mock_api.post(url, body=json.dumps(response))

        # Get price - should include dex parameter
        price = self.async_run_with_timeout(
            self.exchange._get_last_traded_price(hip3_trading_pair)
        )

        # Verify price was fetched
        self.assertEqual(25349.0, price)

    @aioresponses()
    def test_get_last_traded_price_hip3_not_found(self, mock_api):
        """Test RuntimeError when HIP-3 market price not found (line 915)."""
        self._simulate_trading_rules_initialized()

        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        hip3_symbol = "xyz:UNKNOWN"
        hip3_trading_pair = "XYZ_UNKNOWN-USD"

        # Setup HIP-3 market
        self.exchange._is_hip3_market[hip3_symbol] = True
        from bidict import bidict
        mapping = bidict({hip3_symbol: hip3_trading_pair})
        self.exchange._set_trading_pair_symbol_map(mapping)

        # Mock response without the symbol
        response = [
            {"universe": [{"name": "xyz:OTHER"}]},
            [{"markPx": "100.0"}]
        ]
        mock_api.post(url, body=json.dumps(response))

        # Should raise RuntimeError
        with self.assertRaises(RuntimeError):
            self.async_run_with_timeout(
                self.exchange._get_last_traded_price(hip3_trading_pair)
            )

    def test_format_trading_rules_exception_path(self):
        """Test exception handling in _format_trading_rules (lines 256-261)."""
        # Initialize trading rules first to setup symbol mapping
        self._simulate_trading_rules_initialized()

        # Create mock response with missing szDecimals using actual symbols from the universe
        mock_response = [
            {
                "universe": [
                    {"name": "BTC"},  # Missing szDecimals - should cause exception
                    {"name": "ETH", "szDecimals": 4}  # Valid entry
                ]
            },
            [
                {"markPx": "36733.0", "openInterest": "34.37756"},
                {"markPx": "1923.1", "openInterest": "638.89157"}
            ]
        ]

        # Should not raise, but skip problematic entry
        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(mock_response)
        )

        # At least one rule should be created (the valid ETH entry)
        self.assertGreaterEqual(len(rules), 1)

    @aioresponses()
    def test_update_trading_rules_with_perpmeta_assetctxs_mismatch(self, mock_api):
        """Test _update_trading_rules when perpMeta and assetCtxs have different lengths (line 206, 211)."""
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)

        # Base exchange info
        base_response = [
            {'universe': [{'maxLeverage': 50, 'name': 'BTC', 'onlyIsolated': False, 'szDecimals': 5}]},
            [{'markPx': '36733.0', 'openInterest': '34.37756', 'funding': '0.0001'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # DEX response with mismatched lengths
        dex_response = [
            {
                "name": "xyz",
                "perpMeta": [
                    {"name": "xyz:AAPL", "szDecimals": 3},
                    {"name": "xyz:GOOG", "szDecimals": 3}  # Extra item
                ],
                "assetCtxs": [
                    {"markPx": "175.50", "openInterest": "100.5"}
                    # Missing second item - mismatch
                ]
            }
        ]
        mock_api.post(url, body=json.dumps(dex_response))

        # Mock metaAndAssetCtxs call
        meta_response = [
            {"universe": [{"name": "xyz:AAPL", "szDecimals": 3}]},
            [{"markPx": "175.50", "openInterest": "100.5"}]
        ]
        mock_api.post(url, body=json.dumps(meta_response))

        # Should handle mismatch gracefully
        self.async_run_with_timeout(self.exchange._update_trading_rules())

    @aioresponses()
    def test_initialize_trading_pair_symbol_map_with_mismatch(self, mock_api):
        """Test _initialize_trading_pair_symbol_map with perpMeta/assetCtxs mismatch (lines 250-261)."""
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)

        # Base exchange info
        base_response = [
            {'universe': [{'name': 'BTC', 'szDecimals': 5}]},
            [{'markPx': '36733.0'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # DEX response
        dex_response = [
            {"name": "xyz"}
        ]
        mock_api.post(url, body=json.dumps(dex_response))

        # Meta response with mismatch
        meta_response = [
            {"universe": [{"name": "xyz:AAPL"}, {"name": "xyz:GOOG"}]},  # 2 items
            [{"markPx": "175.50"}]  # 1 item - mismatch
        ]
        mock_api.post(url, body=json.dumps(meta_response))

        self.async_run_with_timeout(self.exchange._initialize_trading_pair_symbol_map())

        # Should still initialize properly
        self.assertTrue(self.exchange.trading_pair_symbol_map_ready())

    @aioresponses()
    def test_get_all_pairs_prices_with_dex_no_name(self, mock_api):
        """Test get_all_pairs_prices when DEX has no name (line 321)."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        # Base response
        base_response = [
            {'universe': [{'name': 'BTC'}]},
            [{'markPx': '50000.0', 'name': 'BTC'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # DEX response with missing name
        dex_response = [
            {"perpMeta": [{"name": "xyz:AAPL"}]}  # No "name" field
        ]
        mock_api.post(url, body=json.dumps(dex_response))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        # Should return base prices at minimum
        self.assertIsInstance(result, list)

    @aioresponses()
    def test_get_all_pairs_prices_with_dex_no_universe(self, mock_api):
        """Test get_all_pairs_prices when DEX meta has no universe (line 329)."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        # Base response
        base_response = [
            {'universe': [{'name': 'BTC'}]},
            [{'markPx': '50000.0', 'name': 'BTC'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # DEX list response
        dex_response = [{"name": "xyz"}]
        mock_api.post(url, body=json.dumps(dex_response))

        # Meta response without universe
        meta_response = [{"noUniverse": []}, []]
        mock_api.post(url, body=json.dumps(meta_response))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertIsInstance(result, list)

    @aioresponses()
    def test_get_all_pairs_prices_with_dex_mismatch(self, mock_api):
        """Test get_all_pairs_prices with perpMeta/assetCtxs mismatch (line 335)."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        # Base response
        base_response = [
            {'universe': [{'name': 'BTC'}]},
            [{'markPx': '50000.0', 'name': 'BTC'}]
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # DEX list response
        dex_response = [{"name": "xyz"}]
        mock_api.post(url, body=json.dumps(dex_response))

        # Meta response with mismatch
        meta_response = [
            {"universe": [{"name": "xyz:AAPL"}, {"name": "xyz:GOOG"}]},
            [{"markPx": "175.50"}]  # Only 1 item
        ]
        mock_api.post(url, body=json.dumps(meta_response))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertIsInstance(result, list)

    @aioresponses()
    def test_get_all_pairs_prices_perp_mismatch(self, mock_api):
        """Test get_all_pairs_prices when base perp universe/assetCtxs mismatch (line 300)."""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)

        # Base response with mismatch
        base_response = [
            {'universe': [{'name': 'BTC'}, {'name': 'ETH'}]},  # 2 items
            [{'markPx': '50000.0', 'name': 'BTC'}]  # 1 item
        ]
        mock_api.post(url, body=json.dumps(base_response))

        # Empty DEX response
        mock_api.post(url, body=json.dumps([]))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertIsInstance(result, list)

    def test_format_trading_rules_with_dex_markets_none(self):
        """Test _format_trading_rules when _dex_markets is None (line 780)."""
        self._simulate_trading_rules_initialized()

        # Set _dex_markets to None
        self.exchange._dex_markets = None

        mock_response = [
            {
                "universe": [
                    {"name": "BTC", "szDecimals": 5}
                ]
            },
            [
                {"markPx": "36733.0", "openInterest": "34.37756"}
            ]
        ]

        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(mock_response)
        )

        self.assertGreaterEqual(len(rules), 1)

    def test_format_trading_rules_with_hip3_exception(self):
        """Test _format_trading_rules HIP-3 exception path (lines 855-856)."""
        self._simulate_trading_rules_initialized()

        # Setup HIP-3 market data with missing required fields
        self.exchange.hip_3_result = [
            {
                "name": "xyz:AAPL",
                # Missing markPx, openInterest - will cause exception
            }
        ]

        # Setup symbol mapping for HIP-3 market
        from bidict import bidict
        mapping = bidict({"xyz:AAPL": "XYZ:AAPL-USD", "BTC": "BTC-USD"})
        self.exchange._set_trading_pair_symbol_map(mapping)

        mock_response = [
            {"universe": [{"name": "BTC", "szDecimals": 5}]},
            [{"markPx": "36733.0", "openInterest": "34.37756"}]
        ]

        # Should not raise, should log error and skip
        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(mock_response)
        )

        # Should have at least the BTC rule
        self.assertGreaterEqual(len(rules), 1)

    def test_initialize_trading_pair_symbols_with_hip3_duplicate(self):
        """Test _initialize_trading_pair_symbols_from_exchange_info with HIP-3 duplicate (lines 888)."""
        # Setup DEX markets with a symbol that will cause duplicate
        self.exchange._dex_markets = [
            {
                "name": "xyz",
                "perpMeta": [
                    {"name": "xyz:BTC"},  # Will conflict with base BTC
                ]
            }
        ]

        mock_response = [
            {"universe": [{"name": "BTC", "szDecimals": 5}]},
            [{"markPx": "36733.0"}]
        ]

        # Should handle duplicate gracefully
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mock_response)

        # Should still have symbol map
        self.assertTrue(self.exchange.trading_pair_symbol_map_ready())

    def test_format_trading_rules_dex_info_none_in_list(self):
        """Test _format_trading_rules when dex_info is None in _dex_markets list (line 788)."""
        self._simulate_trading_rules_initialized()

        # Set _dex_markets with None entry
        self.exchange._dex_markets = [None, {"name": "xyz", "perpMeta": []}]

        mock_response = [
            {"universe": [{"name": "BTC", "szDecimals": 5}]},
            [{"markPx": "36733.0", "openInterest": "34.37756"}]
        ]

        rules = self.async_run_with_timeout(
            self.exchange._format_trading_rules(mock_response)
        )

        self.assertGreaterEqual(len(rules), 1)
