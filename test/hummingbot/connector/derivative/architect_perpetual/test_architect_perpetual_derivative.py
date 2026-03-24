import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
    AdditionalInstrumentInfo,
    ArchitectPerpetualDerivative,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)


class ArchitectPerpetualDerivativeUnitTest(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test-key"
        cls.api_secret = "test-secret"
        cls.base_asset = "EUR"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.SANDBOX_DOMAIN
        cls.auth_token = "test-token"

        cls.ev_loop = asyncio.get_event_loop()

    def setup_auth_token(self, mock_api: aioresponses):
        url = web_utils.public_rest_url(CONSTANTS.AUTH_TOKEN_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps({"token": self.auth_token}))

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return regex_url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SINGLE_TICKER_INFO_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_ENDPOINT, domain=self.domain)
        return url

    @property
    def trading_rules_url(self):
        raise NotImplementedError  # re-implements configure_trading_rules_response

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PLACE_ORDER_ENDPOINT, domain=self.domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.RISK_ENDPOINT, domain=self.domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        response = {
            "instruments": [
                {
                    "symbol": self.exchange_trading_pair,
                    "multiplier": "1",
                    "price_scale": 10000,
                    "minimum_order_size": "100",
                    "tick_size": "0.0001",
                    "quote_currency": "USD",
                    "price_band_lower_deviation_pct": "10",
                    "price_band_upper_deviation_pct": "10",
                    "funding_settlement_currency": "USD",
                    "funding_rate_cap_upper_pct": "1.0",
                    "funding_rate_cap_lower_pct": "-1.0",
                    "maintenance_margin_pct": "4.0",
                    "initial_margin_pct": "8.0",
                    "description": "Euro / US Dollar FX Perpetual Future",
                    "underlying_benchmark_price": "WMR London 4pm Closing Spot Rate",
                    "contract_mark_price": "Average price on Architect Bermuda Ltd. at London 4pm",
                    "contract_size": "1 Euro per contract",
                    "price_quotation": "U.S. dollars per Euro",
                    "price_bands": "+/- 10% from prior Contract Mark Price",
                    "funding_frequency": "Daily around 4:00 P.M. London time",
                    "funding_calendar_schedule": (
                        "All days where a valid Underlying Benchmark Price AND Contract Mark Price are published"
                    ),
                    "trading_schedule": {
                    },
                },
            ]
        }
        return response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "ticker": {
                "ts": 1767915571,
                "tn": 376503435,
                "s": self.exchange_trading_pair,
                "p": "1.1659",
                "q": 300,
                "o": "1",
                "l": "1",
                "h": "1.1762",
                "v": -766600492,
                "oi": 477700,
                "i": "OPEN",
                "m": "1.1654",
                "pl": "1.1105",
                "pu": "1.2273",
            },
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = self.all_symbols_request_mock_response
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        return {"status": "OK", "timestamp": "2026-01-12T06:58:57.843888786Z"}

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError  # configure_trading_rules_response re-implemented

    @property
    def trading_rules_request_erroneous_mock_response(self):
        raise NotImplementedError  # configure_erroneous_trading_rules_response re-implemented

    @property
    def order_creation_request_successful_mock_response(self):
        return {"oid": self.expected_exchange_order_id}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        response = {
            "risk_snapshot": {
                "user_id": "01KEGB-VCF0-0000",
                "timestamp_ns": "2026-01-13T09:37:06.896527453Z",
                "per_symbol": {
                    "EURUSD-PERP": {
                        "signed_quantity": 1000,
                        "open_notional": "1167.2000",
                        "average_price": "1.1672",
                        "initial_margin_required_position": "93.360000",
                        "initial_margin_required_open_orders": "0",
                        "initial_margin_required_total": "93.360000",
                        "maintenance_margin_required": "46.680000",
                        "unrealized_pnl": "-0.2000",
                        "liquidation_price": "-198.777568726680"
                    }
                },
                "initial_margin_required_for_positions": "93.360000",
                "initial_margin_required_for_open_orders": "0",
                "initial_margin_required_total": "93.360000",
                "maintenance_margin_required": "46.680000",
                "unrealized_pnl": "-0.2000",
                "equity": "199991.248726680000",
                "initial_margin_available": "1000",
                "maintenance_margin_available": "199944.568726680000",
                "balance_usd": "2000"
            }
        }
        return response

    @property
    def balance_request_mock_response_only_base(self):
        raise NotImplementedError  # test_update_balances re-implemented

    @property
    def balance_event_websocket_update(self):
        raise NotImplementedError  # Architect exchange does not provide WS updates for balances

    @property
    def expected_latest_price(self):
        return 1.1659

    @property
    def expected_supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("100"),  # see all_symbols_request_mock_response
            min_price_increment=Decimal("0.0001"),  # see all_symbols_request_mock_response
            min_base_amount_increment=Decimal("100"),  # see all_symbols_request_mock_response
            min_notional_size=Decimal("111.0500"),  # see configure_trading_rules_response
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.all_symbols_request_mock_response["instruments"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "O-01KER9AWEBHD45J2HE2NC60JSF"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

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
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("25"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "7G2GCXA0442B"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}-PERP"

    def create_exchange_instance(self) -> ArchitectPerpetualDerivative:
        exchange = ArchitectPerpetualDerivative(
            api_key=self.api_key,
            api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self.assertIn(member="Authorization", container=request_call.kwargs["headers"])
        self.assertEqual(first=f"Bearer {self.auth_token}", second=request_call.kwargs["headers"]["Authorization"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        data = json.loads(request_call.kwargs["data"])
        self.assertEqual(data["d"], "B" if order.trade_type == TradeType.BUY else "S")
        self.assertEqual(Decimal(data["p"]), order.price)
        self.assertTrue(data["po"] if order.order_type == OrderType.LIMIT_MAKER else not data["po"])
        self.assertEqual(Decimal(data["q"]), order.amount)
        self.assertEqual(data["s"], self.exchange_trading_pair)
        self.assertEqual(data["cid"], int(order.client_order_id))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        data_dict = json.loads(request_call.kwargs["data"])
        self.assertEqual(first=order.exchange_order_id, second=data_dict["oid"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.client_order_id, str(request_params["client_order_id"]))

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(request_params["order_id"], order.exchange_order_id)

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self.setup_auth_token(mock_api=mock_api)
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, body=json.dumps({"cxl_rx": order.exchange_order_id}), callback=callback)

        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self.setup_auth_token(mock_api=mock_api)
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=404, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self.setup_auth_token(mock_api=mock_api)
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        return [
            self.configure_successful_cancelation_response(
                order=successful_order,
                mock_api=mock_api
            ),
            self.configure_erroneous_cancelation_response(
                order=erroneous_order,
                mock_api=mock_api
            )
        ]

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self.order_status_request_completely_filled_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Union[str, List[str]]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {
            "status": {
                "symbol": self.exchange_trading_pair,
                "order_id": order.exchange_order_id,
                "clord_id": int(order.client_order_id),
                "state": "CANCELED",
            },
        }
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {
            "status": {
                "symbol": self.exchange_trading_pair,
                "order_id": order.exchange_order_id,
                "clord_id": int(order.client_order_id),
                "state": "ACCEPTED",
            },
        }
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=404, callback=callback)

        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {
            "status": {
                "symbol": self.exchange_trading_pair,
                "order_id": order.exchange_order_id,
                "clord_id": int(order.client_order_id),
                "state": "PARTIALLY_FILLED",
            },
        }
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_STATUS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({"error": "no matching orders"}), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {
            "fills": [
                {
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "is_taker": False,
                    "price": str(self.expected_partial_fill_price),
                    "quantity": int(self.expected_partial_fill_amount),
                    "side": "B" if order.trade_type == TradeType.BUY else "S",
                    "symbol": self.exchange_trading_pair,
                    "timestamp": "2023-11-07T05:31:56Z",
                    "trade_id": self.expected_fill_trade_id,
                    "user_id": "01KEGB-VCF0-0000",
                    "order_id": order.exchange_order_id,
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)

        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {
            "fills": [
                {
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "is_taker": False,
                    "price": str(order.price),
                    "quantity": int(order.amount),
                    "side": "B" if order.trade_type == TradeType.BUY else "S",
                    "symbol": self.exchange_trading_pair,
                    "timestamp": "2023-11-07T05:31:56Z",
                    "trade_id": self.expected_fill_trade_id,
                    "user_id": "01KEGB-VCF0-0000",
                    "order_id": order.exchange_order_id,
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_trading_rules_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        exchange_info_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_ENDPOINT, domain=self.domain)
        exchange_info_response = self.get_trading_rule_rest_msg()
        mock_api.get(exchange_info_url, body=json.dumps(exchange_info_response), callback=callback)

        tickers_info_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKERS_INFO_ENDPOINT, domain=self.domain)
        tickers_info_response = {
            "tickers": [
                {
                    "ts": 1767915571,
                    "tn": 376503435,
                    "s": self.exchange_trading_pair,
                    "p": "1.1659",
                    "q": 300,
                    "o": "1",
                    "l": "1",
                    "h": "1.1762",
                    "v": -766600492,
                    "oi": 477700,
                    "i": "OPEN",
                    "m": "1.1654",
                    "pl": "1.1105",
                    "pu": "1.2273",
                },
            ]
        }
        mock_api.get(tickers_info_url, body=json.dumps(tickers_info_response), callback=callback)

        return [exchange_info_url, tickers_info_url]

    def configure_erroneous_trading_rules_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        exchange_info_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_ENDPOINT, domain=self.domain)
        exchange_info_response = self.get_trading_rule_rest_msg()
        mock_api.get(exchange_info_url, body=json.dumps(exchange_info_response), callback=callback)

        tickers_info_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKERS_INFO_ENDPOINT, domain=self.domain)
        tickers_info_response = {
            "tickers": [
                {
                    "ts": 1767915571,
                    "tn": 376503435,
                    "s": self.exchange_trading_pair,
                    "p": "1.1659",
                    "q": 300,
                    "o": "1",
                    "l": "1",
                    "h": "1.1762",
                    "v": -766600492,
                    "oi": 477700,
                    "i": "OPEN",
                    "m": "1.1654",
                    "pu": "1.2273",
                },
            ]
        }
        mock_api.get(tickers_info_url, body=json.dumps(tickers_info_response), callback=callback)

        return [exchange_info_url, tickers_info_url]

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        event = {
            "t": "n",
            "ts": 1609459200,
            "tn": 123456789,
            "eid": "E-01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "o": {
                "oid": self.expected_exchange_order_id,
                "u": "01KEGB-VCF0-0000",
                "s": self.exchange_trading_pair,
                "p": str(order.price),
                "q": int(order.amount),
                "xq": 0,
                "rq": 100,
                "o": "ACCEPTED",
                "d": "B" if order.trade_type == TradeType.BUY else "S",
                "tif": "GTC",
                "ts": 1609459200,
                "tn": 0,
            },
        }
        return event

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        event = {
            "t": "c",
            "ts": 1609459200,
            "tn": 123456789,
            "eid": "E-01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "o": {
                "oid": self.expected_exchange_order_id,
                "u": "01KEGB-VCF0-0000",
                "s": self.exchange_trading_pair,
                "p": str(order.price),
                "q": int(order.amount),
                "xq": 0,
                "rq": 100,
                "o": "CANCELED",
                "d": "B",
                "tif": "GTC",
                "ts": 1609459200,
                "tn": 0,
            },
            "xr": "USER_REQUESTED",
            "txt": "Canceled by user",
        }
        return event

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        event = {
            "t": "f",
            "ts": 1609459200,
            "tn": 123456789,
            "eid": "E-01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "o": {
                "oid": self.expected_exchange_order_id,
                "u": "01KEGB-VCF0-0000",
                "s": self.exchange_trading_pair,
                "p": str(order.price),
                "q": int(order.amount),
                "xq": int(order.amount),
                "rq": 0,
                "o": "FILLED",
                "d": "B" if order.trade_type == TradeType.BUY else "S",
                "tif": "GTC",
                "ts": 1609459200,
                "tn": 0,
            },
            "xs": {
                "tid": self.expected_fill_trade_id,
                "s": self.exchange_trading_pair,
                "q": int(order.amount),
                "p": str(order.price),
                "d": "B" if order.trade_type == TradeType.BUY else "S",
                "agg": True,  # taker
            }
        }
        return event

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None  # delivered with order event update

    def order_status_request_completely_filled_mock_response(self, order: InFlightOrder):
        response = {
            "status": {
                "symbol": self.exchange_trading_pair,
                "order_id": self.expected_exchange_order_id,
                "clord_id": int(order.client_order_id),
                "state": "FILLED",
            },
        }
        return response

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def funding_info_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.FUNDING_INFO_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.FUNDING_EVENTS_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def funding_info_mock_response(self):
        resp = {
            "funding_rates": [
                {
                    "benchmark_price": str(self.target_funding_info_index_price),
                    "funding_amount": "0.000000082967",
                    "funding_rate": str(self.target_funding_info_rate),
                    "settlement_price": str(self.target_funding_info_mark_price),
                    "symbol": self.exchange_trading_pair,
                    "timestamp_ns": int(self.target_funding_info_next_funding_utc_timestamp * 1e9),
                },
            ],
        }
        return resp

    @property
    def empty_funding_payment_mock_response(self):
        resp = {"funding_transactions": []}
        return resp

    @property
    def target_funding_payment_timestamp(self):
        return pd.Timestamp("2026-01-12T18:25:45.095773627Z").timestamp()

    @property
    def funding_payment_mock_response(self):
        resp = {
            "funding_transactions": [
                {
                    "user_id": "01KEGB-VCF0-0000",
                    "currency": self.quote_asset,
                    "timestamp": "2026-01-12T18:25:45.095773627Z",
                    "transaction_type": "funding",
                    "amount": "0.003318680000",
                    "event_id": "01KESQ9X470T3M1ZY8TJEV92Y0",
                    "sequence_number": 10,
                    "reference_id": "settlement://JPYUSD-PERP/1768233600000000000",
                    "symbol": self.exchange_trading_pair,
                    "funding_rate": str(self.target_funding_payment_funding_rate),
                    "funding_amount": str(self.target_funding_payment_payment_amount),
                    "benchmark_price": str(self.target_funding_info_index_price),
                    "settlement_price": str(self.target_funding_info_mark_price),
                },
            ],
        }
        return resp

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        raise NotImplementedError

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
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        """
        :return: A tuple of the URL and an error message if the exchange returns one on failure.
        """
        raise NotImplementedError

    def configure_failed_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        additional_info = AdditionalInstrumentInfo(
            leverage=int(leverage + 1),
            upper_price_bound=Decimal("10000"),
            lower_price_bound=Decimal("0"),
        )
        self.exchange._additional_instruments_info[self.trading_pair] = additional_info
        self.exchange._trading_rules_updates_event.set()
        return "", f"Leverage for {self.trading_pair} is fixed at {additional_info.leverage}."

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        additional_info = AdditionalInstrumentInfo(
            leverage=int(leverage),
            upper_price_bound=Decimal("10000"),
            lower_price_bound=Decimal("0"),
        )
        self.exchange._additional_instruments_info[self.trading_pair] = additional_info
        self.exchange._trading_rules_updates_event.set()

    def funding_info_event_for_websocket_update(self):
        pass

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        instrument_rules = mocked_response["instruments"][0]
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(instrument_rules["minimum_order_size"]),
                min_price_increment=Decimal(instrument_rules["tick_size"]),
                min_base_amount_increment=Decimal(instrument_rules["minimum_order_size"]),
            )
        }

        return self.exchange._trading_rules

    def get_trading_rule_rest_msg(self):
        response = {
            "instruments": [
                {
                    "symbol": self.exchange_trading_pair,
                    "multiplier": "1",
                    "price_scale": 10000,
                    "minimum_order_size": "100",
                    "tick_size": "0.0001",
                    "quote_currency": "USD",
                    "price_band_lower_deviation_pct": "10",
                    "price_band_upper_deviation_pct": "10",
                    "funding_settlement_currency": "USD",
                    "funding_rate_cap_upper_pct": "1.0",
                    "funding_rate_cap_lower_pct": "-1.0",
                    "maintenance_margin_pct": "4.0",
                    "initial_margin_pct": "8.0",
                    "description": "Euro / US Dollar FX Perpetual Future",
                    "underlying_benchmark_price": "WMR London 4pm Closing Spot Rate",
                    "contract_mark_price": "Average price on Architect Bermuda Ltd. at London 4pm",
                    "contract_size": "1 Euro per contract",
                    "price_quotation": "U.S. dollars per Euro",
                    "price_bands": "+/- 10% from prior Contract Mark Price",
                    "funding_frequency": "Daily around 4:00 P.M. London time",
                    "funding_calendar_schedule": (
                        "All days where a valid Underlying Benchmark Price AND Contract Mark Price are published"
                    ),
                    "trading_schedule": {
                    },
                },
            ]
        }
        return response

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(
            url,
            body=json.dumps(creation_response),
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )

        # leverage = 2
        # self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait(), timeout=1)

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request,
        )

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(
            self.exchange.current_timestamp,
            create_event.timestamp,
        )
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(
            str(self.expected_exchange_order_id),
            create_event.exchange_order_id,
        )
        self.assertEqual(PositionAction.OPEN.value, create_event.position)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    async def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        await asyncio.wait_for(request_sent_event.wait(), timeout=1)
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
                f"Error submitting buy LIMIT order to {self.exchange.name_cap} for 100 {self.trading_pair} 10000.0000."
            )
        )

    @aioresponses()
    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
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
                f"Error submitting buy LIMIT order to {self.exchange.name_cap} for 100 {self.trading_pair} 10000.0000."
            )
        )
        error_message = (
            f"Order amount 0.0001 is lower than minimum order size 100 for the pair {self.trading_pair}. "
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
    def test_create_order_to_close_long_position(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
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
                f"{Decimal('100')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
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
                f"{Decimal('100')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        """Open short position"""
        self.setup_auth_token(mock_api=mock_api)
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
                f"{Decimal('100')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    async def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
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
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        trade_url = self.configure_full_fill_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )

        await asyncio.wait_for(self.exchange._update_order_status(), timeout=1)
        # Execute one more synchronization to ensure the async task that processes the update is finished
        await asyncio.wait_for(request_sent_event.wait(), timeout=1)

        await asyncio.wait_for(order.wait_until_completely_filled(), timeout=1)
        await asyncio.sleep(0.1)

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        trades_request = self._all_executed_requests(mock_api, trade_url)[0]
        self.validate_auth_credentials_present(trades_request)
        self.validate_trades_request(order=order, request_call=trades_request)

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
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )

        await asyncio.wait_for(self.exchange._update_lost_orders_status(), timeout=1)
        # Execute one more synchronization to ensure the async task that processes the update is finished
        await asyncio.wait_for(request_sent_event.wait(), timeout=1)
        await asyncio.sleep(0.1)

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

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)

        def callback(*args, **kwargs):
            request_sent_event.set()

        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        url = self.funding_payment_url

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

        self.async_run_with_timeout(run_test())

        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        funding_event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
        self.assertEqual(self.target_funding_payment_timestamp, funding_event.timestamp)
        self.assertEqual(self.exchange.name, funding_event.market)
        self.assertEqual(self.trading_pair, funding_event.trading_pair)
        self.assertEqual(self.target_funding_payment_payment_amount, funding_event.amount)
        self.assertEqual(self.target_funding_payment_funding_rate, funding_event.funding_rate)

    @aioresponses()
    @patch(
        "hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source.ArchitectPerpetualAPIOrderBookDataSource._sleep")
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(
        self, mock_api: aioresponses, mock_queue_get: AsyncMock, sleep_mock: AsyncMock
    ):
        self.setup_auth_token(mock_api=mock_api)
        url = self.funding_info_url

        response = self.funding_info_mock_response
        mock_api.get(url, body=json.dumps(response), repeat=True)

        sleep_mock.side_effect = asyncio.CancelledError

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    async def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
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
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await (
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        if self.is_order_fill_http_update_included_in_status_update:
            # This is done for completeness reasons (to have a response available for the trades request)
            self.configure_erroneous_http_fill_trade_response(order=order, mock_api=mock_api)

        self.configure_order_not_found_error_order_status_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        await (self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        await asyncio.wait_for(request_sent_event.wait(), timeout=1)
        await asyncio.sleep(0.1)

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)

        self.assertFalse(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

    @aioresponses()
    async def test_update_order_status_when_canceled(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        urls = self.configure_canceled_order_status_response(
            order=order,
            mock_api=mock_api)

        await (self.exchange._update_order_status())
        await asyncio.sleep(0.1)

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
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
    async def test_update_order_status_when_order_has_not_changed(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        urls = self.configure_open_order_status_response(
            order=order,
            mock_api=mock_api)

        self.assertTrue(order.is_open)

        await (self.exchange._update_order_status())

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(order=order, request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    @aioresponses()
    async def test_update_balances(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        await (self.exchange._update_balances_and_positions())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("1000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

    @aioresponses()
    async def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = self.configure_http_error_order_status_response(
            order=order,
            mock_api=mock_api)

        await (self.exchange._update_order_status())

        if url:
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @aioresponses()
    async def test_update_trading_rules(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1000)

        self.configure_trading_rules_response(mock_api=mock_api)

        await (self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

        trading_rule_with_default_values = TradingRule(trading_pair=self.trading_pair)

        # The following element can't be left with the default value because that breaks quantization in Cython
        self.assertNotEqual(trading_rule_with_default_values.min_base_amount_increment,
                            trading_rule.min_base_amount_increment)
        self.assertNotEqual(trading_rule_with_default_values.min_price_increment,
                            trading_rule.min_price_increment)

    @aioresponses()
    async def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1000)

        self.configure_erroneous_trading_rules_response(mock_api=mock_api)

        await (self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self.is_logged("ERROR", self.expected_logged_error_for_erroneous_trading_rule)
        )

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = "123"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[order_id]

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

    def test_user_stream_balance_update(self):
        # Architect does not update balances via WS
        pass

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        pass

    @aioresponses()
    def test_set_leverage_failure(self, mock_api):
        request_sent_event = asyncio.Event()
        target_leverage = 2
        _, message = self.configure_failed_set_leverage(
            leverage=target_leverage,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)

        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertTrue(
            self.is_logged(
                log_level="NETWORK",
                message=f"Error setting leverage {target_leverage} for {self.trading_pair}: {message}",
            )
        )

    @aioresponses()
    def test_set_leverage_success(self, mock_api):
        request_sent_event = asyncio.Event()
        target_leverage = 2
        self.configure_successful_set_leverage(
            leverage=target_leverage,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)

        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertTrue(
            self.is_logged(
                log_level="INFO",
                message=f"Leverage for {self.trading_pair} successfully set to {target_leverage}.",
            )
        )

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        self.exchange.set_position_mode(PositionMode.HEDGE)

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=(
                    f"Position mode {PositionMode.HEDGE} is not supported. Mode not set."
                )
            )
        )

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        self.exchange.set_position_mode(PositionMode.ONEWAY)

        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"Position mode switched to {PositionMode.ONEWAY}.",
            )
        )

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
    async def test_update_positions(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)
        self.configure_trading_rules_response(mock_api=mock_api)

        await asyncio.wait_for(self.exchange._update_trading_rules(), timeout=1)

        response = {
            "risk_snapshot": {
                "user_id": "01KEGB-VCF0-0000",
                "timestamp_ns": "2026-01-13T12:01:06.906306671Z",
                "per_symbol": {
                    self.exchange_trading_pair: {
                        "signed_quantity": 1000,
                        "open_notional": "1167.2000",
                        "average_price": "1.1672",
                        "initial_margin_required_position": "93.3680000",
                        "initial_margin_required_open_orders": "0",
                        "initial_margin_required_total": "93.3680000",
                        "maintenance_margin_required": "46.6840000",
                        "unrealized_pnl": "-0.1000",
                        "liquidation_price": "-198.771872026680"
                    }
                },
                "initial_margin_required_for_positions": "104.1400000",
                "initial_margin_required_for_open_orders": "0",
                "initial_margin_required_total": "104.1400000",
                "maintenance_margin_required": "52.0700000",
                "unrealized_pnl": "-0.0700",
                "equity": "199991.042026680000",
                "initial_margin_available": "199886.902026680000",
                "maintenance_margin_available": "199938.972026680000",
                "balance_usd": "199991.112026680000"
            }
        }

        url = web_utils.private_rest_url(path_url=CONSTANTS.RISK_ENDPOINT, domain=self.domain)
        mock_api.get(
            re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")),
            body=json.dumps(response),
        )

        await asyncio.wait_for(self.exchange._update_balances_and_positions(), timeout=1)

        account_positions = self.exchange.account_positions

        self.assertEqual(1, len(account_positions))

        position: Position = list(account_positions.values())[0]

        self.assertEqual(Decimal("1000"), position.amount)
        self.assertEqual(Decimal("1.1672"), position.entry_price)
        self.assertEqual(12, position.leverage)
        self.assertEqual(PositionSide.LONG, position.position_side)
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(Decimal("-0.1000"), position.unrealized_pnl)

    @aioresponses()
    async def test_get_last_trade_prices(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        url = self.latest_prices_url

        response = self.latest_prices_request_mock_response

        mock_api.get(url, body=json.dumps(response))

        latest_prices: Dict[str, float] = await (
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    @aioresponses()
    async def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await (
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

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
            await (self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        await (order.wait_until_completely_filled())
        await asyncio.sleep(0.1)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        urls = self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(order=order, request_call=order_status_request)

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)

        if self.is_order_fill_http_update_included_in_status_update:
            self.assertTrue(order.is_filled)

            if trade_url:
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
            self.assertEqual(leverage, fill_event.leverage)
            self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(
            order.amount if self.is_order_fill_http_update_included_in_status_update else Decimal(0),
            buy_event.base_asset_amount)
        self.assertEqual(
            order.amount * order.price
            if self.is_order_fill_http_update_included_in_status_update
            else Decimal(0),
            buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    async def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self,
                                                                                                         mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)

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

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_erroneous_http_fill_trade_response(
                order=order,
                mock_api=mock_api)

        urls = self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        # Since the trade fill update will fail we need to manually set the event
        # to allow the ClientOrderTracker to process the last status update
        order.completely_filled_event.set()
        await (self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        await (order.wait_until_completely_filled())
        await asyncio.sleep(0.1)

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(order=order, request_call=order_status_request)

        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        if self.is_order_fill_http_update_included_in_status_update:
            if trade_url:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

        self.assertEqual(0, len(self.order_filled_logger.event_log))

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    async def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_partial_fill_trade_response(
                order=order,
                mock_api=mock_api)

        order_url = self.configure_partially_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        self.assertTrue(order.is_open)

        await (self.exchange._update_order_status())
        await asyncio.sleep(0.1)

        if order_url:
            order_status_request = self._all_executed_requests(mock_api, order_url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        if self.is_order_fill_http_update_included_in_status_update:
            if trade_url:
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
            self.assertEqual(self.expected_partial_fill_price, fill_event.price)
            self.assertEqual(self.expected_partial_fill_amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)
