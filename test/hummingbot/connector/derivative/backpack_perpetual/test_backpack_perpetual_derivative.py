import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
    BackpackPerpetualDerivative,
)
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BackpackPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test_api_key"
        cls.api_secret = "dGVzdF9zZWNyZXRfNjRfYnl0ZXNfb2ZfZGF0YV9lZDI1NTE5X2tleV9mb3JfdGVzdGluZw=="  # noqa: mock
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(CONSTANTS.TICKERS_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(CONSTANTS.STATUS_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(CONSTANTS.CAPITAL_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.rest_url(CONSTANTS.FUNDING_RATES_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        return None

    @property
    def balance_request_mock_response_only_base(self):
        return None

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "symbol": "BTC_USDC_PERP",
                "baseSymbol": "BTC",
                "quoteSymbol": "USDC",
                "minOrderSize": "0.0001",
                "tickSize": "0.1",
                "stepSize": "0.0001",
                "minNotional": "10",
            },
            {
                "symbol": "SOL_USDC_PERP",
                "baseSymbol": "SOL",
                "quoteSymbol": "USDC",
                "minOrderSize": "0.01",
                "tickSize": "0.001",
                "stepSize": "0.01",
                "minNotional": "1",
            },
        ]

    @property
    def latest_prices_request_mock_response(self):
        return [
            {
                "symbol": "BTC_USDC_PERP",
                "lastPrice": str(self.expected_latest_price),
                "markPrice": str(self.expected_latest_price),
                "indexPrice": str(self.expected_latest_price),
            }
        ]

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, List[Dict[str, Any]]]:
        mock_response = [
            {
                "symbol": "INVALID_PAIR",
                "baseSymbol": "INVALID",
                "quoteSymbol": "PAIR",
            },
            {
                "symbol": "BTC_USDC_PERP",
                "baseSymbol": "BTC",
                "quoteSymbol": "USDC",
                "minOrderSize": "0.0001",
                "tickSize": "0.1",
                "stepSize": "0.0001",
                "minNotional": "10",
            },
        ]
        return "INVALID-PAIR", mock_response

    def empty_funding_payment_mock_response(self):
        return None

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        # Backpack may not support funding payment polling the same way
        pass

    @property
    def network_status_request_successful_mock_response(self):
        return {"status": "ok", "message": ""}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {
                "symbol": "BTC_USDC_PERP",
                # Missing required fields
            }
        ]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "id": self.expected_exchange_order_id,
            "clientId": None,
            "symbol": "BTC_USDC_PERP",
            "side": "Bid",
            "orderType": "Limit",
            "timeInForce": "GTC",
            "price": "50000",
            "quantity": "0.001",
            "executedQuantity": "0",
            "status": "New",
            "createdAt": 1700000000000000,
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "balances": [
                {
                    "asset": self.quote_asset,
                    "available": "2000",
                    "locked": "0",
                    "total": "2000",
                }
            ]
        }

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
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        pass

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Position mode PositionMode.HEDGE is not supported. Mode not set.",
            )
        )

    def is_cancel_request_executed_synchronously_by_server(self):
        return True

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
        return None

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def target_funding_info_next_funding_utc_str(self):
        return "2024-01-01T00:00:00Z"

    @property
    def target_funding_info_next_funding_utc_str_ws_updated(self):
        return "2024-01-01T08:00:00Z"

    @property
    def target_funding_payment_timestamp_str(self):
        return "2024-01-01T00:00:00Z"

    @property
    def funding_info_mock_response(self):
        return [
            {
                "symbol": "BTC_USDC_PERP",
                "fundingRate": self.target_funding_info_rate,
                "nextFundingTime": self.target_funding_info_next_funding_utc_timestamp,
                "markPrice": str(self.target_funding_info_mark_price),
                "indexPrice": str(self.target_funding_info_index_price),
            }
        ]

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market = self.trading_rules_request_mock_response[0]

        return TradingRule(
            self.trading_pair,
            min_order_size=Decimal(str(market.get("minOrderSize", "0.0001"))),
            min_price_increment=Decimal(str(market.get("tickSize", "0.1"))),
            min_base_amount_increment=Decimal(str(market.get("stepSize", "0.0001"))),
            min_notional_size=Decimal(str(market.get("minNotional", "10"))),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "12345678"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("50000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.0005")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.01"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "trade-12345"

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1700000000

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}_PERP"

    def create_exchange_instance(self):
        exchange = BackpackPerpetualDerivative(
            backpack_perpetual_api_key=self.api_key,
            backpack_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        return exchange

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual("Bid" if order.trade_type is TradeType.BUY else "Ask", request_data.get("side"))
        self.assertEqual(str(order.amount), request_data.get("quantity"))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        # Backpack uses DELETE with params
        self.assertIsNotNone(request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        self.assertIsNotNone(request_params)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        self.assertIsNotNone(request_params)

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.delete(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": CONSTANTS.UNKNOWN_ORDER_MESSAGE}
        mock_api.delete(regex_url, body=json.dumps(response), status=404, callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": CONSTANTS.ORDER_NOT_EXIST_MESSAGE}
        mock_api.get(regex_url, body=json.dumps(response), status=404, callback=callback)
        return url

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_failed_set_leverage(
        self,
        leverage: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.rest_url(CONSTANTS.LEVERAGE_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        err_msg = "Unable to set leverage"
        mock_response = {"error": err_msg}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=400, callback=callback)
        return url, err_msg

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.rest_url(CONSTANTS.LEVERAGE_URL)
        regex_url = re.compile(f"^{url}")
        mock_response = {
            "symbol": "BTC_USDC_PERP",
            "leverage": str(leverage),
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)
        return url

    def get_trading_rule_rest_msg(self):
        return self.all_symbols_request_mock_response

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderUpdate",
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": order.client_order_id or "",
                "s": "BTC_USDC_PERP",
                "S": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "o": "Limit",
                "q": str(order.amount),
                "p": str(order.price),
                "X": "New",
                "T": 1700000000000000,
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderUpdate",
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": order.client_order_id or "",
                "s": "BTC_USDC_PERP",
                "S": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "o": "Limit",
                "q": str(order.amount),
                "p": str(order.price),
                "X": "Cancelled",
                "T": 1700000000000000,
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderUpdate",
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": order.client_order_id or "",
                "s": "BTC_USDC_PERP",
                "S": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "o": "Limit",
                "q": str(order.amount),
                "p": str(order.price),
                "z": str(order.amount),  # executedQuantity
                "X": "Filled",
                "T": 1700000000000000,
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "stream": "account.fill",
            "data": {
                "e": "fill",
                "t": self.expected_fill_trade_id,
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "s": "BTC_USDC_PERP",
                "S": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "p": str(self.expected_partial_fill_price),
                "q": str(order.amount),
                "f": "0.01",  # fee
                "T": 1700000000000000,
            },
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "status": "Cancelled",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "clientId": order.client_order_id,
            "symbol": "BTC_USDC_PERP",
            "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": str(order.amount),
            "status": "Filled",
            "createdAt": 1700000000000000,
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "clientId": order.client_order_id,
            "symbol": "BTC_USDC_PERP",
            "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": "0",
            "status": "Cancelled",
            "createdAt": 1700000000000000,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "clientId": order.client_order_id,
            "symbol": "BTC_USDC_PERP",
            "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": "0",
            "status": "New",
            "createdAt": 1700000000000000,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder):
        return {
            "id": order.exchange_order_id,
            "clientId": order.client_order_id,
            "symbol": "BTC_USDC_PERP",
            "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": str(self.expected_partial_fill_amount),
            "status": "PartiallyFilled",
            "createdAt": 1700000000000000,
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id,
                "symbol": "BTC_USDC_PERP",
                "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "price": str(self.expected_partial_fill_price),
                "quantity": str(self.expected_partial_fill_amount),
                "fee": "0.01",
                "feeSymbol": self.quote_asset,
                "createdAt": 1700000000000000,
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id,
                "symbol": "BTC_USDC_PERP",
                "side": "Bid" if order.trade_type is TradeType.BUY else "Ask",
                "price": str(order.price),
                "quantity": str(order.amount),
                "fee": "0.01",
                "feeSymbol": self.quote_asset,
                "createdAt": 1700000000000000,
            }
        ]

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "stream": "account.positionUpdate",
            "data": {
                "e": "positionUpdate",
                "s": "BTC_USDC_PERP",
                "pa": str(order.amount),
                "ep": str(order.price),
                "up": str(unrealized_pnl),
                "ps": "Long" if order.trade_type is TradeType.BUY else "Short",
                "T": 1700000000000000,
            },
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "stream": "fundingRate.BTC_USDC_PERP",
            "data": {
                "s": "BTC_USDC_PERP",
                "r": str(self.target_funding_info_rate),
                "T": self.target_funding_info_next_funding_utc_timestamp_ws_updated * 1000,
                "mp": str(self.target_funding_info_mark_price_ws_updated),
                "ip": str(self.target_funding_info_index_price_ws_updated),
            },
        }
