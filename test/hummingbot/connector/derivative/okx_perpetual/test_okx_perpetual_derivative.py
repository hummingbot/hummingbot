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
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import FundingPaymentCompletedEvent, OrderCancelledEvent


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
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_LATEST_SYMBOL_INFORMATION[CONSTANTS.ENDPOINT])
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

    # -------------------------------------------------------
    # TRADING RULES PROPERTIES, MOCKS AND TESTS
    # -------------------------------------------------------

    @property
    def trading_rules_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT])
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
                    "fee": "",
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
        return 1657099053000

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
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["instId"])
        self.assertEqual("cross", request_data["tdMode"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.order_type.name.lower(), request_data["ordType"])
        self.assertEqual(Decimal("100"), Decimal(request_data["sz"]))
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
        request_params = request_call.kwargs["params"]
        self.assertEqual("SWAT", request_params["instType"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["instId"])
        self.assertEqual(order.exchange_order_id, request_params["ordId"])

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
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT], domain=CONSTANTS.DEFAULT_DOMAIN
        )
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
                    "sz": str(order.amount),
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
                    "sz": str(order.amount),
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
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SPOT",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "fillSz": str(order.amount),
                    "fillPx": str(order.price),
                    "tradeId": self.expected_fill_trade_id,
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": str(self.expected_fill_fee.flat_fees[0].amount),
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

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {}

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        position_value = unrealized_pnl + order.amount * order.price * order.leverage
        return {
            "topic": "position",
            "data": [
                {
                    "user_id": 533285,
                    "symbol": self.exchange_trading_pair,
                    "size": float(order.amount),
                    "side": order.trade_type.name.capitalize(),
                    "position_value": str(position_value),
                    "entry_price": str(order.price),
                    "liq_price": "489",
                    "bust_price": "489",
                    "leverage": str(order.leverage),
                    "order_margin": "0",
                    "position_margin": "0.39929535",
                    "available_balance": "0.39753405",
                    "take_profit": "0",
                    "stop_loss": "0",
                    "realised_pnl": "0.00055631",
                    "trailing_stop": "0",
                    "trailing_active": "0",
                    "wallet_balance": "0.40053971",
                    "risk_id": 1,
                    "occ_closing_fee": "0.0002454",
                    "occ_funding_fee": "0",
                    "auto_add_margin": 1,
                    "cum_realised_pnl": "0.00055105",
                    "position_status": "Normal",
                    "position_seq": 0,
                    "Isolated": False,
                    "mode": 0,
                    "position_idx": 0,
                    "tp_sl_mode": "Partial",
                    "tp_order_num": 0,
                    "sl_order_num": 0,
                    "tp_free_size_x": 200,
                    "sl_free_size_x": 200
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
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": str(order.amount),
                    "fillTime": "0",
                    "state": "filled",
                    "avgPx": str(order.price + Decimal(2)),
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
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
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": "0",
                    "fillTime": "0",
                    "state": "canceled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
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
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": "0",
                    "fillTime": "0",
                    "state": "live",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
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
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": str(self.expected_partial_fill_price),
                    "tradeId": "1",
                    "fillSz": str(self.expected_partial_fill_amount),
                    "fillTime": "0",
                    "state": "partially_filled",
                    "avgPx": str(order.price + Decimal(2)),
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

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
                    "fillSz": str(self.expected_partial_fill_amount),
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                },
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
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
                    "fillSz": str(order.amount),
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
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
