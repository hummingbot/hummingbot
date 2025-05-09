import asyncio
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import GateIoPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class GateIoPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.user_id = "someUserId"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(endpoint=CONSTANTS.EXCHANGE_INFO_URL)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.TICKER_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(endpoint=CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(endpoint=CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_CREATE_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(endpoint=CONSTANTS.USER_BALANCES_PATH_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.MARK_PRICE_URL.format(id=self.exchange_trading_pair)
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
            {
                "name": self.exchange_trading_pair,
                "type": "direct",
                "quanto_multiplier": "0.0001",
                "ref_discount_rate": "0",
                "order_price_deviate": "0.5",
                "maintenance_rate": "0.005",
                "mark_type": "index",
                "last_price": "38026",
                "mark_price": "37985.6",
                "index_price": "37954.92",
                "funding_rate_indicative": "0.000219",
                "mark_price_round": "0.01",
                "funding_offset": 0,
                "in_delisting": False,
                "risk_limit_base": "1000000",
                "interest_rate": "0.0003",
                "order_price_round": "0.1",
                "order_size_min": 1,
                "ref_rebate_rate": "0.2",
                "funding_interval": 28800,
                "risk_limit_step": "1000000",
                "leverage_min": "1",
                "leverage_max": "100",
                "risk_limit_max": "8000000",
                "maker_fee_rate": "-0.00025",
                "taker_fee_rate": "0.00075",
                "funding_rate": "0.002053",
                "order_size_max": 1000000,
                "funding_next_apply": 1610035200,
                "short_users": 977,
                "config_change_time": 1609899548,
                "trade_size": 28530850594,
                "position_size": 5223816,
                "long_users": 455,
                "funding_impact_value": "60000",
                "orders_limit": 50,
                "trade_id": 10851092,
                "orderbook_id": 2129638396
            }
        ]
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = [
            {
                "contract": self.exchange_trading_pair,
                "last": str(self.expected_latest_price),
                "low_24h": "6278",
                "high_24h": "6790",
                "change_percentage": "4.43",
                "total_size": "32323904",
                "volume_24h": "184040233284",
                "volume_24h_btc": "28613220",
                "volume_24h_usd": "184040233284",
                "volume_24h_base": "28613220",
                "volume_24h_quote": "184040233284",
                "volume_24h_settle": "28613220",
                "mark_price": "6534",
                "funding_rate": "3",
                "funding_next_apply": self.target_funding_info_next_funding_utc_timestamp,
                "funding_rate_indicative": "3",
                "index_price": "6531"
            }
        ]
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = [
            {
                "name": f"{self.base_asset}_{self.quote_asset}",
                "type": "direct",
                "quanto_multiplier": "0.0001",
                "ref_discount_rate": "0",
                "order_price_deviate": "0.5",
                "maintenance_rate": "0.005",
                "mark_type": "index",
                "last_price": "38026",
                "mark_price": "37985.6",
                "index_price": "37954.92",
                "funding_rate_indicative": "0.000219",
                "mark_price_round": "0.01",
                "funding_offset": 0,
                "in_delisting": True,
                "risk_limit_base": "1000000",
                "interest_rate": "0.0003",
                "order_price_round": "0.1",
                "order_size_min": 1,
                "ref_rebate_rate": "0.2",
                "funding_interval": 28800,
                "risk_limit_step": "1000000",
                "leverage_min": "1",
                "leverage_max": "100",
                "risk_limit_max": "8000000",
                "maker_fee_rate": "-0.00025",
                "taker_fee_rate": "0.00075",
                "funding_rate": "0.002053",
                "order_size_max": 1000000,
                "funding_next_apply": 1610035200,
                "short_users": 977,
                "config_change_time": 1609899548,
                "trade_size": 28530850594,
                "position_size": 5223816,
                "long_users": 455,
                "funding_impact_value": "60000",
                "orders_limit": 50,
                "trade_id": 10851092,
                "orderbook_id": 2129638396
            }
        ]
        return "INVALID-PAIR", mock_response

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = [
            {
                "name": self.exchange_trading_pair,
                "type": "direct",
                "quanto_multiplier": "0.0001",
                "ref_discount_rate": "0",
                "order_price_deviate": "0.5",
                "maintenance_rate": "0.005",
                "mark_type": "index",
                "last_price": "38026",
                "mark_price": "37985.6",
                "index_price": "37954.92",
                "funding_rate_indicative": "0.000219",
                "mark_price_round": "0.01",
                "funding_offset": 0,
                "in_delisting": False,
                "risk_limit_base": "1000000",
                "interest_rate": "0.0003",
                "order_price_round": "0.1",
                "order_size_min": 1,
                "ref_rebate_rate": "0.2",
                "funding_interval": 28800,
                "risk_limit_step": "1000000",
                "leverage_min": "1",
                "leverage_max": "100",
                "risk_limit_max": "8000000",
                "maker_fee_rate": "-0.00025",
                "taker_fee_rate": "0.00075",
                "funding_rate": "0.002053",
                "order_size_max": 1000000,
                "funding_next_apply": 1610035200,
                "short_users": 977,
                "config_change_time": 1609899548,
                "trade_size": 28530850594,
                "position_size": 5223816,
                "long_users": 455,
                "funding_impact_value": "60000",
                "orders_limit": 50,
                "trade_id": 10851092,
                "orderbook_id": 2129638396
            }
        ]
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = [
            {
                "name": self.exchange_trading_pair,
                "type": "direct",
                "mark_type": "index",
                "last_price": "38026",
                "mark_price": "37985.6",
                "index_price": "37954.92",
                "in_delisting": False,
            }
        ]
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "id": self.expected_exchange_order_id,
            "user": 100000,
            "contract": self.exchange_trading_pair,
            "create_time": 1546569968,
            "size": 6024,
            "iceberg": 0,
            "left": 6024,
            "price": "3765",
            "fill_price": "0",
            "mkfr": "-0.00025",
            "tkfr": "0.00075",
            "tif": "gtc",
            "refu": 0,
            "is_reduce_only": False,
            "is_close": False,
            "is_liq": False,
            "text": get_new_client_order_id(
                is_buy=True,
                trading_pair=self.trading_pair,
                hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
                max_id_len=CONSTANTS.MAX_ID_LEN,
            ),
            "status": "open",
            "finish_time": 1514764900,
            "finish_as": ""
        }
        return mock_response

    @property
    def limit_maker_order_creation_request_successful_mock_response(self):
        mock_response = {
            "id": self.expected_exchange_order_id,
            "user": 100000,
            "contract": self.exchange_trading_pair,
            "create_time": 1546569968,
            "size": 6024,
            "iceberg": 0,
            "left": 6024,
            "price": "3765",
            "fill_price": "0",
            "mkfr": "-0.00025",
            "tkfr": "0.00075",
            "tif": "poc",
            "refu": 0,
            "is_reduce_only": False,
            "is_close": False,
            "is_liq": False,
            "text": get_new_client_order_id(
                is_buy=True,
                trading_pair=self.trading_pair,
                hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
                max_id_len=CONSTANTS.MAX_ID_LEN,
            ),
            "status": "open",
            "finish_time": 1514764900,
            "finish_as": ""
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "user": 1666,
            "currency": self.quote_asset,
            "total": "2000",
            "unrealised_pnl": "3371.248828",
            "position_margin": "38.712189181",
            "order_margin": "0",
            "available": "2000",
            "point": "0",
            "bonus": "0",
            "in_dual_mode": False,
            "history": {
                "dnw": "10000",
                "pnl": "68.3685",
                "fee": "-1.645812875",
                "refr": "0",
                "fund": "-358.919120009855",
                "point_dnw": "0",
                "point_fee": "0",
                "point_refr": "0",
                "bonus_dnw": "0",
                "bonus_offset": "0"
            }
        }
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

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "channel": "futures.balances",
            "event": "update",
            "time": 1541505434,
            "result": [
                {
                    "balance": 15,
                    "change": 5,
                    "text": "BTC_USD:3914424",
                    "time": 1547199246,
                    "time_ms": 1547199246123,
                    "type": "fee",
                    "user": "211xxx"
                }
            ]
        }
        return mock_response

    @property
    def position_event_websocket_update(self):
        mock_response = {
            "time": 1588212926,
            "time_ms": 1588212926123,
            "channel": "futures.positions",
            "event": "update",
            "result": [
                {
                    "contract": "BTC_USDT",
                    "cross_leverage_limit": 0,
                    "entry_price": 40000.36666661111,
                    "history_pnl": -0.000108569505,
                    "history_point": 0,
                    "last_close_pnl": -0.000050123368,
                    "leverage": 0,
                    "leverage_max": 100,
                    "liq_price": 0.1,
                    "maintenance_rate": 0.005,
                    "margin": 49.999890611186,
                    "mode": "single",
                    "realised_pnl": -1.25e-8,
                    "realised_point": 0,
                    "risk_limit": 100,
                    "size": 3,
                    "time": 1628736848,
                    "time_ms": 1628736848321,
                    "user": "110xxxxx"
                }
            ]
        }
        return mock_response

    @property
    def position_event_websocket_update_zero(self):
        mock_response = {
            "time": 1588212926,
            "time_ms": 1588212926123,
            "channel": "futures.positions",
            "event": "update",
            "result": [
                {
                    "contract": "BTC_USDT",
                    "cross_leverage_limit": 0,
                    "entry_price": 40000.36666661111,
                    "history_pnl": -0.000108569505,
                    "history_point": 0,
                    "last_close_pnl": -0.000050123368,
                    "leverage": 0,
                    "leverage_max": 100,
                    "liq_price": 0.1,
                    "maintenance_rate": 0.005,
                    "margin": 49.999890611186,
                    "mode": "single",
                    "realised_pnl": -1.25e-8,
                    "realised_point": 0,
                    "risk_limit": 100,
                    "size": 0,
                    "time": 1628736848,
                    "time_ms": 1628736848321,
                    "user": "110xxxxx"
                }
            ]
        }
        return mock_response

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
        funding_info = mock_response[0]
        funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["mark_price"] = self.target_funding_info_mark_price
        funding_info["predicted_funding_rate"] = self.target_funding_info_rate
        return funding_info

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response[0]

        min_amount_inc = Decimal(f"{rule['quanto_multiplier']}")
        min_price_inc = Decimal(f"{rule['order_price_round']}")
        min_amount = min_amount_inc
        min_notional = Decimal(str(1))

        return TradingRule(self.trading_pair,
                           min_order_size=min_amount,
                           min_price_increment=min_price_inc,
                           min_base_amount_increment=min_amount_inc,
                           min_notional_size=min_notional,
                           min_order_value=min_notional,
                           )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "335fd977-e5a5-4781-b6d0-c772d5bfb95b"

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
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = GateIoPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            self.user_id,
            trading_pairs=[self.trading_pair],
        )
        # exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", request_headers["Content-Type"])

        self.assertIn("Timestamp", request_headers)
        self.assertIn("KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["KEY"])
        self.assertIn("SIGN", request_headers)

    def _format_amount_to_size(self, amount: Decimal) -> Decimal:
        # trading_rule = self.trading_rules_request_mock_response[0]
        trading_rule = self.exchange._trading_rules[self.trading_pair]
        size = amount / Decimal(str(trading_rule.min_base_amount_increment))
        return size

    def _format_size_to_amount(self, size: Decimal) -> Decimal:
        self._simulate_trading_rules_initialized()
        # trading_rule = self.trading_rules_request_mock_response[0]
        trading_rule = self.exchange._trading_rules[self.trading_pair]
        amount = Decimal(str(size)) * Decimal(str(trading_rule.min_base_amount_increment))
        return amount

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.trade_type.name.lower(), "buy" if request_data["size"] > 0 else "sell")
        self.assertEqual(self.exchange_trading_pair, request_data["contract"])
        self.assertEqual(order.amount, self._format_size_to_amount(abs(Decimal(str(request_data["size"])))))
        self.assertEqual(order.client_order_id, request_data["text"])

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
        self.assertEqual(self.exchange_trading_pair, request_params["contract"])
        self.assertEqual(order.exchange_order_id, request_params["order"])

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
            endpoint=CONSTANTS.ORDER_DELETE_PATH_URL.format(id=order.exchange_order_id)
        )
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_DELETE_PATH_URL.format(id=order.exchange_order_id)
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.delete(regex_url, status=400, callback=callback)
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )

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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.MY_TRADES_PATH_URL,
        )
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
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=order.exchange_order_id),
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.SET_POSITION_MODE_URL
        )
        regex_url = re.compile(f"^{url}")
        get_position_url = web_utils.public_rest_url(
            endpoint=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_get_position_url = re.compile(f"^{get_position_url}")
        get_position_mock_response = [
            {"mode": 'dual'} if position_mode is PositionMode.ONEWAY else {"mode": 'single'}
        ]
        response = {
            "user": 1666,
            "currency": "USDT",
            "total": "9707.803567115145",
            "size": "9707.803567115145",
            "unrealised_pnl": "3371.248828",
            "position_margin": "38.712189181",
            "order_margin": "0",
            "available": "9669.091377934145",
            "point": "0",
            "bonus": "0",
            "in_dual_mode": True if position_mode is PositionMode.HEDGE else False,
            "mode": "single" if position_mode is PositionMode.ONEWAY else "dual_long",
            "history": {
                "dnw": "10000",
                "pnl": "68.3685",
                "fee": "-1.645812875",
                "refr": "0",
                "fund": "-358.919120009855",
                "point_dnw": "0",
                "point_fee": "0",
                "point_refr": "0",
                "bonus_dnw": "0",
                "bonus_offset": "0"
            }
        }
        mock_api.get(regex_get_position_url, body=json.dumps(get_position_mock_response), callback=callback)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.public_rest_url(
            endpoint=CONSTANTS.SET_POSITION_MODE_URL
        )
        get_position_url = web_utils.public_rest_url(
            endpoint=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_url = re.compile(f"^{url}")
        regex_get_position_url = re.compile(f"^{get_position_url}")

        error_msg = ""
        get_position_mock_response = [
            {"mode": 'single'}
        ]
        mock_response = {
            "label": "1666",
            "detail": "",
        }
        mock_api.get(regex_get_position_url, body=json.dumps(get_position_mock_response), callback=callback)
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"{error_msg}"

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        if self.exchange.position_mode is PositionMode.ONEWAY:
            endpoint = CONSTANTS.ONEWAY_SET_LEVERAGE_PATH_URL.format(contract=self.exchange_trading_pair)
        else:
            endpoint = CONSTANTS.HEDGE_SET_LEVERAGE_PATH_URL.format(contract=self.exchange_trading_pair)
        url = web_utils.public_rest_url(
            endpoint=endpoint
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        err_msg = "leverage is diff"
        mock_response = [
            {
                "user": 10000,
                "contract": "BTC_USDT",
                "size": -9440,
                "leverage": 200,
                "risk_limit": "100",
                "leverage_max": "100",
                "maintenance_rate": "0.005",
                "value": "2.497143098997",
                "margin": "4.431548146258",
                "entry_price": "3779.55",
                "liq_price": "99999999",
                "mark_price": "3780.32",
                "unrealised_pnl": "-0.000507486844",
                "realised_pnl": "0.045543982432",
                "history_pnl": "0",
                "last_close_pnl": "0",
                "realised_point": "0",
                "history_point": "0",
                "adl_ranking": 5,
                "pending_orders": 16,
                "close_order": {
                    "id": 232323,
                    "price": "3779",
                    "is_liq": False
                },
                "mode": "single",
                "cross_leverage_limit": "0"
            }
        ]
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)
        return url, err_msg

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        if self.exchange.position_mode is PositionMode.ONEWAY:
            endpoint = CONSTANTS.ONEWAY_SET_LEVERAGE_PATH_URL.format(contract=self.exchange_trading_pair)
        else:
            endpoint = CONSTANTS.HEDGE_SET_LEVERAGE_PATH_URL.format(contract=self.exchange_trading_pair)
        url = web_utils.public_rest_url(
            endpoint=endpoint
        )
        regex_url = re.compile(f"^{url}")

        mock_response = [
            {
                "user": 10000,
                "contract": "BTC_USDT",
                "size": -9440,
                "leverage": str(leverage),
                "risk_limit": "100",
                "leverage_max": "100",
                "maintenance_rate": "0.005",
                "value": "2.497143098997",
                "margin": "4.431548146258",
                "entry_price": "3779.55",
                "liq_price": "99999999",
                "mark_price": "3780.32",
                "unrealised_pnl": "-0.000507486844",
                "realised_pnl": "0.045543982432",
                "history_pnl": "0",
                "last_close_pnl": "0",
                "realised_point": "0",
                "history_point": "0",
                "adl_ranking": 5,
                "pending_orders": 16,
                "close_order": {
                    "id": 232323,
                    "price": "3779",
                    "is_liq": False
                },
                "mode": "single",
                "cross_leverage_limit": "0"
            }
        ]

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "futures.orders",
            "event": "update",
            "time": 1541505434,
            "result": [
                {
                    "contract": self.exchange_trading_pair,
                    "create_time": 1628736847,
                    "create_time_ms": 1628736847325,
                    "fill_price": 40000.4,
                    "finish_as": "",
                    "finish_time": 1628736848,
                    "finish_time_ms": 1628736848321,
                    "iceberg": 0,
                    "id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "is_close": False,
                    "is_liq": False,
                    "is_reduce_only": False,
                    "left": 0,
                    "mkfr": -0.00025,
                    "price": order.price,
                    "refr": 0,
                    "refu": 0,
                    "size": float(order.amount),
                    "status": "open",
                    "text": order.client_order_id or "",
                    "tif": "gtc",
                    "tkfr": 0.0005,
                    "user": "110xxxxx"
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "futures.orders",
            "event": "update",
            "time": 1541505434,
            "result": [
                {
                    "contract": self.exchange_trading_pair,
                    "create_time": 1628736847,
                    "create_time_ms": 1628736847325,
                    "fill_price": 40000.4,
                    "finish_as": "cancelled",
                    "finish_time": 1628736848,
                    "finish_time_ms": 1628736848321,
                    "iceberg": 0,
                    "id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "is_close": False,
                    "is_liq": False,
                    "is_reduce_only": False,
                    "left": 0,
                    "mkfr": -0.00025,
                    "price": order.price,
                    "refr": 0,
                    "refu": 0,
                    "size": float(order.amount),
                    "status": "finished",
                    "text": order.client_order_id or "",
                    "tif": "gtc",
                    "tkfr": 0.0005,
                    "user": "110xxxxx"
                }
            ]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()

        return {
            "channel": "futures.orders",
            "event": "update",
            "time": 1541505434,
            "result": [
                {
                    "contract": self.exchange_trading_pair,
                    "create_time": 2628736847,
                    "create_time_ms": 1628736847325,
                    "fill_price": 40000.4,
                    "finish_as": "filled",
                    "finish_time": 1628736848,
                    "finish_time_ms": 1628736848321,
                    "iceberg": 0,
                    "id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "is_close": False,
                    "is_liq": False,
                    "is_reduce_only": False,
                    "left": 0,
                    "mkfr": -0.00025,
                    "price": order.price,
                    "refr": 0,
                    "refu": 0,
                    "size": self._format_amount_to_size(Decimal(order.amount)),
                    "status": "finished",
                    "text": order.client_order_id or "",
                    "tif": "gtc",
                    "tkfr": 0.0005,
                    "user": "110xxxxx"
                }
            ]
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "time": 1543205083,
            "channel": "futures.usertrades",
            "event": "update",
            "error": None,
            "result": [
                {
                    "id": self.expected_fill_trade_id,
                    "create_time": 2628736848,
                    "create_time_ms": 1628736848321,
                    "contract": self.exchange_trading_pair,
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "size": self._format_amount_to_size(Decimal(order.amount)),
                    "price": str(order.price),
                    "role": "maker",
                    "text": order.client_order_id or "",
                    "fee": Decimal(self.expected_fill_fee.flat_fees[0].amount),
                    "point_fee": 0
                }
            ]
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        pass

    def funding_info_event_for_websocket_update(self):
        return {
            "time": 1541659086,
            "channel": "futures.tickers",
            "event": "update",
            "error": None,
            "result": [
                {
                    "contract": self.exchange_trading_pair,
                    "last": "118.4",
                    "change_percentage": "0.77",
                    "funding_rate": "-0.000114",
                    "funding_rate_indicative": self.target_funding_info_rate_ws_updated * 1e6,
                    "mark_price": self.target_funding_info_mark_price_ws_updated,
                    "index_price": self.target_funding_info_index_price_ws_updated,
                    "total_size": "73648",
                    "volume_24h": "745487577",
                    "volume_24h_btc": "117",
                    "volume_24h_usd": "419950",
                    "quanto_base_rate": "",
                    "volume_24h_quote": "1665006",
                    "volume_24h_settle": "178",
                    "volume_24h_base": "5526",
                    "low_24h": "99.2",
                    "high_24h": "132.5"
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

    def test_user_stream_update_for_new_order(self):
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

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertTrue(order.is_open)

    def test_user_stream_balance_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = GateIoPerpetualDerivative(
            client_config_map=client_config_map,
            gate_io_perpetual_api_key=self.api_key,
            gate_io_perpetual_secret_key=self.api_secret,
            gate_io_perpetual_user_id=self.user_id,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.quote_asset))

    def test_user_stream_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = GateIoPerpetualDerivative(
            client_config_map=client_config_map,
            gate_io_perpetual_api_key=self.api_key,
            gate_io_perpetual_secret_key=self.api_secret,
            gate_io_perpetual_user_id=self.user_id,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        self._simulate_trading_rules_initialized()
        self.exchange.account_positions[self.trading_pair] = Position(

            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        amount_precision = Decimal(self.exchange.trading_rules[self.trading_pair].min_base_amount_increment)
        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 3 * amount_precision)

    def test_user_stream_remove_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = GateIoPerpetualDerivative(
            client_config_map=client_config_map,
            gate_io_perpetual_api_key=self.api_key,
            gate_io_perpetual_secret_key=self.api_secret,
            gate_io_perpetual_user_id=self.user_id,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update_zero
        self._simulate_trading_rules_initialized()
        self.exchange.account_positions[self.trading_pair] = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        self.assertEqual(len(self.exchange.account_positions), 0)

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = GateIoPerpetualDerivative(
            client_config_map=client_config_map,
            gate_io_perpetual_api_key=self.api_key,
            gate_io_perpetual_secret_key=self.api_secret,
            gate_io_perpetual_user_id=self.user_id,
            trading_pairs=[self.trading_pair],
        )

        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, buy_collateral_token)
        self.assertEqual(self.quote_asset, sell_collateral_token)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_first_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        duplicate["quanto_multiplier"] = str(float(duplicate["quanto_multiplier"]) + 1)
        results.append(duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_second_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        duplicate["quanto_multiplier"] = str(float(duplicate["quanto_multiplier"]) + 1)
        results.insert(0, duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_cannot_resolve(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response
        first_duplicate = deepcopy(results[0])
        first_duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        first_duplicate["quanto_multiplier"] = (
            str(float(first_duplicate["quanto_multiplier"]) + 1)
        )
        second_duplicate = deepcopy(results[0])
        second_duplicate["name"] = f"{self.exchange_trading_pair}_67890"
        second_duplicate["quanto_multiplier"] = (
            str(float(second_duplicate["quanto_multiplier"]) + 2)
        )
        results.pop(0)
        results.append(first_duplicate)
        results.append(second_duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertNotIn(self.trading_pair, self.exchange.trading_rules)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=(
                    f"Could not resolve the exchange symbols"
                    f" {self.exchange_trading_pair}_67890"
                    f" and {self.exchange_trading_pair}_12345"
                ),
            )
        )

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
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
        order = self.exchange.in_flight_orders["11"]

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
        self.validate_auth_credentials_present(cancel_request)
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
            "id": order.exchange_order_id,
            "user": self.user_id,
            "contract": self.exchange_trading_pair,
            "create_time": 1546569968,
            "size": float(order.amount),
            "iceberg": 0,
            "left": 6024,
            "price": str(order.price),
            "fill_price": "0",
            "mkfr": "-0.00025",
            "tkfr": "0.00075",
            "tif": "gtc",
            "refu": 0,
            "is_reduce_only": False,
            "is_close": False,
            "is_liq": False,
            "text": order.client_order_id or "",
            "status": "finished",
            "finish_time": 1514764900,
            "finish_as": "cancelled"
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": order.exchange_order_id,
            "user": 100000,
            "contract": self.exchange_trading_pair,
            "create_time": 1546569968,
            "size": float(order.amount),
            "iceberg": 0,
            "left": 0,
            "price": str(order.price),
            "fill_price": str(order.price),
            "mkfr": "-0.00025",
            "tkfr": "0.00075",
            "tif": "gtc",
            "refu": 0,
            "is_reduce_only": False,
            "is_close": False,
            "is_liq": False,
            "text": order.client_order_id or "2b1d811c-8ff0-4ef0-92ed-b4ed5fd6de34",
            "status": "finished",
            "finish_time": 1514764900,
            "finish_as": "filled"
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["finish_as"] = "cancelled"
        resp["left"] = float(order.amount)
        resp["fill_price"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["finish_as"] = ""
        resp["left"] = float(order.amount)
        resp["fill_price"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["finish_as"] = ""
        resp["left"] = float(order.amount) / 2
        resp["fill_price"] = str(order.price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["finish_as"] = ""
        resp["left"] = float(order.amount) / 2
        resp["fill_price"] = str(order.price)
        return resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return [
            {
                "id": self.expected_fill_trade_id,
                "create_time": 1514764800.123,
                "contract": self.exchange_trading_pair,
                "order_id": order.exchange_order_id,
                "size": str(self._format_amount_to_size(Decimal(order.amount))),
                "price": str(order.price),
                "text": order.client_order_id,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "point_fee": "0",
                "role": "taker"
            }
        ]

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @aioresponses()
    def test_start_network_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        duplicate["quanto_multiplier"] = str(float(duplicate["quanto_multiplier"]) + 1)
        results.append(duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange.start_network())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    def place_limit_maker_buy_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT_MAKER,
            price=price,
            position_action=position_action,
        )
        return order_id

    @aioresponses()
    def test_create_buy_limit_maker_order_successfully(self, mock_api):
        """Open long position"""
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.limit_maker_order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_limit_maker_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp,
                         create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
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
                f"Created {OrderType.LIMIT_MAKER.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_update_position_mode(
            self,
            mock_api: aioresponses,
    ):
        self._simulate_trading_rules_initialized()
        get_position_url = web_utils.public_rest_url(
            endpoint=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_get_position_url = re.compile(f"^{get_position_url}")
        response = [
            {
                "user": 10000,
                "contract": "BTC_USDT",
                "size": 9440,
                "leverage": "0",
                "risk_limit": "100",
                "leverage_max": "100",
                "maintenance_rate": "0.005",
                "value": "2.497143098997",
                "margin": "4.431548146258",
                "entry_price": "3779.55",
                "liq_price": "99999999",
                "mark_price": "3780.32",
                "unrealised_pnl": "-0.000507486844",
                "realised_pnl": "0.045543982432",
                "history_pnl": "0",
                "last_close_pnl": "0",
                "realised_point": "0",
                "history_point": "0",
                "adl_ranking": 5,
                "pending_orders": 16,
                "close_order": {
                    "id": 232323,
                    "price": "3779",
                    "is_liq": False
                },
                "mode": "single",
                "update_time": 1684994406,
                "cross_leverage_limit": "0"
            }
        ]
        mock_api.get(regex_get_position_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_positions())

        position: Position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.LONG, position.position_side)

        get_position_url = web_utils.public_rest_url(
            endpoint=CONSTANTS.POSITION_INFORMATION_URL
        )
        regex_get_position_url = re.compile(f"^{get_position_url}")
        response = [
            {
                "user": 10000,
                "contract": "BTC_USDT",
                "size": 9440,
                "leverage": "0",
                "risk_limit": "100",
                "leverage_max": "100",
                "maintenance_rate": "0.005",
                "value": "2.497143098997",
                "margin": "4.431548146258",
                "entry_price": "3779.55",
                "liq_price": "99999999",
                "mark_price": "3780.32",
                "unrealised_pnl": "-0.000507486844",
                "realised_pnl": "0.045543982432",
                "history_pnl": "0",
                "last_close_pnl": "0",
                "realised_point": "0",
                "history_point": "0",
                "adl_ranking": 5,
                "pending_orders": 16,
                "close_order": {
                    "id": 232323,
                    "price": "3779",
                    "is_liq": False
                },
                "mode": "dual_long",
                "update_time": 1684994406,
                "cross_leverage_limit": "0"
            }
        ]
        mock_api.get(regex_get_position_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_positions())
        position: Position = self.exchange.account_positions[f"{self.trading_pair}LONG"]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.LONG, position.position_side)
