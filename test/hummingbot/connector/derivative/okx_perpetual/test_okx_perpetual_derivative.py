import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_derivative import OkxPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
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


class OkxPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.passphrase = "somePassphrase"

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    @property
    def all_symbols_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT])
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_LATEST_SYMBOL_INFORMATION[CONSTANTS.ENDPOINT],
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    # OK
    @property
    def network_status_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_SERVER_TIME[CONSTANTS.ENDPOINT])
        return url

    @property
    def order_creation_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_PLACE_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_GET_WALLET_BALANCE[CONSTANTS.ENDPOINT])
        return url

    @property
    def funding_info_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_FUNDING_RATE_INFO[CONSTANTS.ENDPOINT])
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def mark_price_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_MARK_PRICE[CONSTANTS.ENDPOINT])
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def index_price_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_INDEX_TICKERS[CONSTANTS.ENDPOINT])
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def funding_payment_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_BILLS_DETAILS[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url_regex

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "",
                    "category": "1",
                    "ctMult": "1",
                    "ctType": "linear",
                    "ctVal": "1",
                    "ctValCcy": self.base_asset,
                    "expTime": "",
                    "instFamily": self.exchange_trading_pair,
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SWAP",
                    "lever": "50",
                    "listTime": "1611916828000",
                    "lotSz": "1",
                    "maxIcebergSz": "100000000.0000000000000000",
                    "maxLmtAmt": "20000000",
                    "maxLmtSz": "100000000",
                    "maxMktAmt": "",
                    "maxMktSz": "10000",
                    "maxStopSz": "10000",
                    "maxTriggerSz": "100000000.0000000000000000",
                    "maxTwapSz": "100000000.0000000000000000",
                    "minSz": "1",
                    "optType": "",
                    "quoteCcy": "",
                    "settleCcy": self.quote_asset,
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.1",
                    "uly": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                }
            ],
            "msg": ""
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "INVALID",
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "instType": "OPTION",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.000001",
                    "minSz": "0.1",
                    "optType": "",
                    "quoteCcy": "PAIR",
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.001",
                    "uly": ""
                },
            ]
        }

        return "INVALID-PAIR", response

    @property
    def trading_rules_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT],
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_request_mock_response(self):
        response = {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "",
                    "category": "1",
                    "ctMult": "1",
                    "ctType": "linear",
                    "ctVal": "1",
                    "ctValCcy": self.base_asset,
                    "expTime": "",
                    "instFamily": "LTC-USDT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SWAP",
                    "lever": "50",
                    "listTime": "1611916828000",
                    "lotSz": "1",
                    "maxIcebergSz": "100000000.0000000000000000",
                    "maxLmtAmt": "20000000",
                    "maxLmtSz": "100000000",
                    "maxMktAmt": "",
                    "maxMktSz": "10000",
                    "maxStopSz": "10000",
                    "maxTriggerSz": "100000000.0000000000000000",
                    "maxTwapSz": "100000000.0000000000000000",
                    "minSz": "1",
                    "optType": "",
                    "quoteCcy": "",
                    "settleCcy": self.quote_asset,
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.01",
                    "uly": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                }
            ],
            "msg": ""
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
                    "category": "1",
                    "ctValCcy": self.base_asset,
                    "settleCcy": "",
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
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))

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
        self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))

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
                    "lastSz": "0.1",
                    "askPx": "9999.99",
                    "askSz": "11",
                    "bidPx": "8888.88",
                    "bidSz": "5",
                    "open24h": "9000",
                    "high24h": "10000",
                    "low24h": "8888.88",
                    "volCcy24h": "2222",
                    "vol24h": "2222",
                    "sodUtc0": "2222",
                    "sodUtc8": "2222",
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": "oktswap6",
                    "ordId": self.expected_exchange_order_id,
                    "tag": "",
                    "sCode": "0",
                    "sMsg": ""
                }
            ]
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": "0",
            "data": [
                {
                    "adjEq": "10679688.0460531643092577",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "cashBal": "",
                            "ccy": self.base_asset,
                            "crossLiab": "0",
                            "disEq": "9439737.0772999514",
                            "eq": "",
                            "eqUsd": "9933041.196999946",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "10000",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        },
                        {
                            "availBal": "",
                            "availEq": "2000",
                            "cashBal": "",
                            "ccy": self.quote_asset,
                            "crossLiab": "0",
                            "disEq": "1239950.9687532129092577",
                            "eq": "2000",
                            "eqUsd": "1239950.9687532129092577",
                            "frozenBal": "0.0918492093160816",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "1453.92289531493594",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0.570822125136023",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        }
                    ],
                    "imr": "3372.2942371050594217",
                    "isoEq": "0",
                    "mgnRatio": "70375.35408747017",
                    "mmr": "134.8917694842024",
                    "notionalUsd": "33722.9423710505978888",
                    "ordFroz": "0",
                    "totalEq": "11172992.1657531589092577",
                    "uTime": "1623392334718"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "0",
            "data": [
                {
                    "adjEq": "10679688.0460531643092577",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "cashBal": "",
                            "ccy": self.base_asset,
                            "crossLiab": "0",
                            "disEq": "9439737.0772999514",
                            "eq": "",
                            "eqUsd": "9933041.196999946",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "10000",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        },
                    ],
                    "imr": "3372.2942371050594217",
                    "isoEq": "0",
                    "mgnRatio": "70375.35408747017",
                    "mmr": "134.8917694842024",
                    "notionalUsd": "33722.9423710505978888",
                    "ordFroz": "0",
                    "totalEq": "11172992.1657531589092577",
                    "uTime": "1623392334718"
                }
            ],
            "msg": ""
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "arg": {
                "channel": "account",
                "ccy": "BTC"
            },
            "data": [
                {
                    "uTime": "1597026383085",
                    "totalEq": "41624.32",
                    "isoEq": "3624.32",
                    "adjEq": "41624.32",
                    "ordFroz": "0",
                    "imr": "4162.33",
                    "mmr": "4",
                    "notionalUsd": "",
                    "mgnRatio": "41624.32",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "ccy": self.base_asset,
                            "cashBal": "",
                            "uTime": "1617279471503",
                            "disEq": "50559.01",
                            "eq": "",
                            "eqUsd": "45078.3790756226851775",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "liab": "0",
                            "maxLoan": "",
                            "mgnRatio": "",
                            "notionalLever": "0.0022195262185864",
                            "ordFrozen": "0",
                            "upl": "0",
                            "uplLiab": "0",
                            "crossLiab": "0",
                            "isoLiab": "0",
                            "coinUsdPrice": "60000",
                            "stgyEq": "0",
                            "isoUpl": ""
                        }
                    ]
                }
            ]
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

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
        return "312269865356374016"

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
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = OkxPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            self.passphrase,
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
                    "bal": "8694.2179403378290202",
                    "balChg": "0.0219338232210000",
                    "billId": "623950854533513219",
                    "ccy": self.quote_asset,
                    "clOrdId": "",
                    "execType": "T",
                    "fee": "0",
                    "fillFwdPx": "",
                    "fillIdxPx": "27104.1",
                    "fillMarkPx": "",
                    "fillMarkVol": "",
                    "fillPxUsd": "",
                    "fillPxVol": "",
                    "fillTime": "1695033476166",
                    "from": "",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SWAP",
                    "interest": "0",
                    "mgnMode": "cross",
                    "notes": "",
                    "ordId": "623950854525124608",
                    "pnl": str(self.target_funding_payment_payment_amount),
                    "posBal": "0",
                    "posBalChg": "0",
                    "px": "27105.9",
                    "subType": CONSTANTS.FUNDING_PAYMENT_EXPENSE_SUBTYPE,
                    "sz": "0.021955779",
                    "tag": "",
                    "to": "",
                    "tradeId": "586760148",
                    "ts": str(self.target_funding_payment_timestamp),
                    "type": CONSTANTS.FUNDING_PAYMENT_TYPE
                }
            ]
        }

    @property
    def funding_info_mock_response(self):
        return {
            "code": "0",
            "data": [
                {
                    "fundingRate": "3",
                    "fundingTime": "1703088000000",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SWAP",
                    "method": "next_period",
                    "maxFundingRate": "0.00375",
                    "minFundingRate": "-0.00375",
                    "nextFundingRate": "0.0002061194322149",
                    "nextFundingTime": "1657099053000",
                    "settFundingRate": "0.0001418433662153",
                    "settState": "settled",
                    # TODO: Check if use with target_funding_info_next_funding_utc_str
                    "ts": "1703070685309"
                }
            ],
            "msg": ""
        }

    @property
    def mark_price_mock_response(self):
        return {
            "arg": {
                "channel": "mark-price",
                "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "markPx": "2",
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def index_price_mock_response(self):
        return {
            "arg": {
                "channel": "index-tickers",
                "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
            },
            "data": [
                {
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "idxPx": "1",
                    "high24h": "0.5",
                    "low24h": "0.1",
                    "open24h": "0.1",
                    "sodUtc0": "0.1",
                    "sodUtc8": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_timestamp(self):
        return 1657099053

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
        datetime_str = pd.Timestamp.fromtimestamp(
            self.target_funding_payment_timestamp, tz='UTC'
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
        return datetime_str

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

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
            endpoint=CONSTANTS.REST_CANCEL_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
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
            endpoint=CONSTANTS.REST_CANCEL_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
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
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT],
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_SET_POSITION_MODE[CONSTANTS.ENDPOINT])
        response = {
            "code": "0",
            "data": [
                {
                    "posMode": "long_short_mode"
                }
            ],
            "msg": ""
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_failed_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_SET_POSITION_MODE[CONSTANTS.ENDPOINT],
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(f"^{url}")

        error_code = 1_000
        error_msg = "Some problem"
        mock_response = {
            "code": str(error_code),
            "data": [],
            "msg": error_msg
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"ret_code <{error_code}> - {error_msg}"

    def configure_failed_set_leverage(
        self,
        leverage: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_SET_LEVERAGE[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
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
            endpoint=CONSTANTS.REST_SET_LEVERAGE[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": "0",
            "data": [
                {
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "lever": "5",
                    "mgnMode": "isolated",
                    "posSide": "long"
                }
            ],
            "msg": ""
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SWAP",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(self._format_amount_to_size(Decimal(order.amount))),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "fillSz": "0",
                    "fillPx": "0",
                    "tradeId": "0",
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": "0",
                    "fillFeeCcy": "",
                    "execType": "T",
                    "state": "live",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SWAP",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(self._format_amount_to_size(Decimal(order.amount))),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "fillSz": str(self._format_amount_to_size(Decimal(order.amount))),
                    "fillPx": "0",
                    "tradeId": "0",
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": "0",
                    "fillFeeCcy": "",
                    "execType": "T",
                    "state": "canceled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SWAP",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": self._format_amount_to_size(Decimal(order.amount)),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "short" if (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                    or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE) else "long",
                    "tdMode": "cross",
                    "tgtCcy": "",
                    "fillSz": self._format_amount_to_size(Decimal(order.amount)),
                    "fillPx": str(order.price),
                    "tradeId": self.expected_fill_trade_id,
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": str(-self.expected_fill_fee.flat_fees[0].amount),
                    "fillFeeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "execType": "T",
                    "state": "filled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
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
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT])
        url = f"{url}?instId={self.exchange_trading_pair}&limit=100"
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

    @aioresponses()
    def test_update_positions(self, mock_api):
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
        response = self.position_event_for_full_fill_websocket_update(self.exchange.in_flight_orders["11"], 0.1)
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.REST_GET_POSITIONS[CONSTANTS.ENDPOINT])
        url = f"{url}?instId={self.exchange_trading_pair}"
        regex_url = re.compile(f"^{url}")
        mock_api.get(regex_url, body=json.dumps(response))
        asyncio.get_event_loop().run_until_complete(self.exchange._update_positions())
        # Assert that self._trading_pairs is not empty
        self.assertNotEqual(len(self.exchange._trading_pairs), 0, "No trading pairs fetched")

        # Assert that each parsed response is a dictionary
        for data in response["data"]:
            self.assertIsInstance(data, dict, "Parsed response is not a dictionary")

            # Assert that each parsed response has 'instId', 'upl', 'avgPx', and 'lever' keys
            self.assertTrue(all(key in data for key in ["instId", "upl", "avgPx", "lever"]),
                            "Parsed response does not contain expected keys")

            # Assert that amount is not None and is a Decimal
            self.assertIsNotNone(amount, "Amount is None")
            self.assertIsInstance(amount, Decimal, "Amount is not a Decimal")

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        # position_value = unrealized_pnl + order.amount * order.price * order.leverage
        return {
            "arg": {
                "channel": "positions",
                "uid": order.exchange_order_id,
                "instType": "SWAP"
            },
            "data": [
                {
                    "adl": "1",
                    "availPos": "1",
                    "avgPx": f"{order.price}",
                    "cTime": "1619507758793",
                    "ccy": "ETH",
                    "deltaBS": "",
                    "deltaPA": "",
                    "gammaBS": "",
                    "gammaPA": "",
                    "imr": "",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "instType": "SWAP",
                    "interest": "0",
                    "idxPx": "2566.13",
                    "last": "2566.22",
                    "lever": f"{order.leverage}",
                    "liab": "",
                    "liabCcy": "",
                    "liqPx": "2352.8496681818233",
                    "markPx": "2353.849",
                    "margin": "0.0003896645377994",
                    "mgnMode": "isolated",
                    "mgnRatio": "11.731726509588816",
                    "mmr": "0.0000311811092368",
                    "notionalUsd": f"{order.amount * order.price}",
                    "optVal": "",
                    "pTime": "1619507761462",
                    "pos": "1",
                    "baseBorrowed": "",
                    "baseInterest": "",
                    "quoteBorrowed": "",
                    "quoteInterest": "",
                    "posCcy": "",
                    "posId": "307173036051017730",
                    "posSide": "short" if (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                    or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE) else "long",
                    "spotInUseAmt": "",
                    "bizRefId": "",
                    "bizRefType": "",
                    "spotInUseCcy": "",
                    "thetaBS": "",
                    "thetaPA": "",
                    "tradeId": "109844",
                    "uTime": "1619507761462",
                    "upl": f"{unrealized_pnl}",
                    "uplLastPx": "-0.0000009932766034",
                    "uplRatio": "-0.0025490556801078",
                    "uplRatioLastPx": "-0.0025490556801078",
                    "vegaBS": "",
                    "vegaPA": "",
                    "realizedPnl": "0.001",
                    "pnl": "0.0011",
                    "fee": "-0.0001",
                    "fundingFee": "0",
                    "liqPenalty": "0",
                    "closeOrderAlgo": [
                        {
                            "algoId": "123",
                            "slTriggerPx": "123",
                            "slTriggerPxType": "mark",
                            "tpTriggerPx": "123",
                            "tpTriggerPxType": "mark",
                            "closeFraction": "0.6"
                        },
                        {
                            "algoId": "123",
                            "slTriggerPx": "123",
                            "slTriggerPxType": "mark",
                            "tpTriggerPx": "123",
                            "tpTriggerPxType": "mark",
                            "closeFraction": "0.4"
                        }
                    ]
                }
            ]
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "arg": {
                "channel": "funding-rate",
                "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            },
            "data": [
                {
                    "fundingRate": "0.0001875391284828",
                    "fundingTime": "1700726400000",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SWAP",
                    "method": "next_period",
                    "maxFundingRate": "0.00375",
                    "minFundingRate": "-0.00375",
                    "nextFundingRate": "0.0002608059239328",
                    "nextFundingTime": "1700755200000",
                    "settFundingRate": "0.0001699799259033",
                    "settState": "settled",
                    "ts": "1700724675402"
                }
            ]
        }

    def mark_price_event_for_websocket_update(self):
        return {
            "arg": {
                "channel": "mark-price",
                "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "markPx": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

    def index_price_event_for_websocket_update(self):
        return {
            "arg": {
                "channel": "index-tickers",
                "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            },
            "data": [
                {
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "idxPx": "0.1",
                    "high24h": "0.5",
                    "low24h": "0.1",
                    "open24h": "0.1",
                    "sodUtc0": "0.1",
                    "sodUtc8": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

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

        self.async_run_with_timeout(run_test())

        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        funding_event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
        self.assertEqual(self.target_funding_payment_timestamp, funding_event.timestamp)
        self.assertEqual(self.exchange.name, funding_event.market)
        self.assertEqual(self.trading_pair, funding_event.trading_pair)
        self.assertEqual(self.target_funding_payment_payment_amount, funding_event.amount)
        self.assertEqual(self.target_funding_payment_funding_rate, funding_event.funding_rate)

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = OkxPerpetualDerivative(
            client_config_map=client_config_map,
            okx_perpetual_api_key=self.api_key,
            okx_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )

        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("Error executing request POST https://okx.com/api/v5/order. HTTP status is 401. "
                            'Error: {"code":"50113","msg":"message"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://okx.com/api/v5/order. HTTP status is 401. "
                            'Error: {"code":"50114","msg":"message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        funding_info_url = self.funding_info_url
        mark_price_url = self.mark_price_url
        index_price_url = self.index_price_url

        funding_info_response = self.funding_info_mock_response
        mark_price_response = self.mark_price_mock_response
        index_price_response = self.index_price_mock_response

        mock_api.get(funding_info_url, body=json.dumps(funding_info_response))
        mock_api.get(mark_price_url, body=json.dumps(mark_price_response))
        mock_api.get(index_price_url, body=json.dumps(index_price_response))

        event_messages = [asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

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
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        funding_info_url = self.funding_info_url
        mark_price_url = self.mark_price_url
        index_price_url = self.index_price_url

        funding_info_response = self.funding_info_mock_response
        mark_price_response = self.mark_price_mock_response
        index_price_response = self.index_price_mock_response

        mock_api.get(funding_info_url, body=json.dumps(funding_info_response))
        mock_api.get(mark_price_url, body=json.dumps(mark_price_response))
        mock_api.get(index_price_url, body=json.dumps(index_price_response))

        funding_info_event = self.funding_info_event_for_websocket_update()

        event_messages = [funding_info_event, asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(
                self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

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

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        self._simulate_trading_rules_initialized()
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ccy": "",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price) or "",
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "short" if (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                    or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE) else "long",
                    "tdMode": "cross",
                    "accFillSz": "0",
                    "fillPx": str(order.price),
                    "tradeId": "1",
                    "fillSz": str(self._format_amount_to_size(order.amount)),
                    "fillTime": "0",
                    "state": "filled",
                    "avgPx": str(order.price),
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(-self.expected_fill_fee.flat_fees[0].amount),
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
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
                    "posSide": "short" if (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                    or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE) else "long",
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
                    "posSide": "short" if (order.trade_type == TradeType.SELL and order.position == PositionAction.OPEN)
                    or (order.trade_type == TradeType.BUY and order.position == PositionAction.CLOSE) else "long",
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(-self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                },
            ]
        }

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

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

        for response_scode in (0, 51400, 51401):
            url = self.configure_successful_cancelation_response(
                order=order,
                mock_api=mock_api,
                response_scode=response_scode,
                callback=lambda *args, **kwargs: request_sent_event.set())

            self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
            self.async_run_with_timeout(request_sent_event.wait())

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

    # Starting here, the subsequent tests have been overridden because of URL conflicts with the OKX spot connector.
    # The content remains identical to that of the parent class.
    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
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

        if url:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_api):
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
            self.validate_auth_credentials_present(cancel_request)
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
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
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

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
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
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order1.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order1.client_order_id}."
                )
            )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
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
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
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

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
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

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
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

        urls = self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_erroneous_http_fill_trade_response(
                order=order,
                mock_api=mock_api)

        # Since the trade fill update will fail we need to manually set the event
        # to allow the ClientOrderTracker to process the last status update
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

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
    def test_update_order_status_when_order_has_not_changed(self, mock_api):
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

        urls = self.configure_open_order_status_response(
            order=order,
            mock_api=mock_api)

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(order=order, request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
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

        order_url = self.configure_partially_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        if self.is_order_fill_http_update_included_in_status_update:
            trade_url = self.configure_partial_fill_trade_response(
                order=order,
                mock_api=mock_api)

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

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

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
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

        url = self.configure_http_error_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())

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
    def test_create_order_to_close_short_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
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
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_order_to_close_long_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
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
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        """Open long position"""
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
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
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
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
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
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
    def test_create_sell_limit_order_successfully(self, mock_api):
        """Open short position"""
        self._simulate_trading_rules_initialized()
        self._simulate_contract_sizes_initialized()
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
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_get_last_traded_price(self, mock_api):
        mock_api.get(self.latest_prices_url, body=json.dumps(self.latest_prices_request_mock_response))
        lastprice_response = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))
        self.assertEqual(lastprice_response, 9999.9)
