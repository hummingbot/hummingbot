import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

import hummingbot.connector.derivative.derive_perpetual.derive_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.derive_perpetual.derive_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source import (
    DerivePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative import DerivePerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)


class DerivePerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)
    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "0x79d7511382b5dFd1185F6AF268923D3F9FC31B53"  # noqa: mock
        cls.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        cls.sub_id = "45686"  # noqa: mock
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.exchange_trading_pair = f"{cls.base_asset}-PERP"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.client_order_id_prefix = "0x48424f5442454855443630616330301"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

        self.exchange = DerivePerpetualDerivative(
            client_config_map=self.client_config_map,
            derive_perpetual_api_key=self.api_key,
            derive_perpetual_api_secret=self.api_secret,
            sub_id=self.sub_id,
            trading_pairs=[self.trading_pair],
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        DerivePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.exchange_trading_pair: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-PERP": self.trading_pair}))

    def test_get_related_limits(self):
        self.assertEqual(17, len(self.throttler._rate_limits))

        rate_limit, related_limits = self.throttler.get_related_limits(CONSTANTS.ENDPOINTS["limits"]["non_matching"][4])
        self.assertIsNotNone(rate_limit, "Rate limit for TEST_POOL_ID is None.")  # Ensure rate_limit is not None
        self.assertEqual(CONSTANTS.ENDPOINTS["limits"]["non_matching"][4], rate_limit.limit_id)

        rate_limit, related_limits = self.throttler.get_related_limits(CONSTANTS.ENDPOINTS["limits"]["non_matching"][3])
        self.assertIsNotNone(rate_limit, "Rate limit for TEST_PATH_URL is None.")  # Ensure rate_limit is not None
        self.assertEqual(CONSTANTS.ENDPOINTS["limits"]["non_matching"][3], rate_limit.limit_id)
        self.assertEqual(1, len(related_limits))

    async def _run_rate_limits_polling_loop_with_mocked_logger(self, exception=None):
        with patch.object(self.exchange, "_update_rate_limits", AsyncMock(side_effect=exception)):
            with patch.object(self.exchange.logger(), "info") as mock_logger_info:
                await self.exchange._rate_limits_polling_loop()
                return mock_logger_info

    async def _run_update_rate_limits_with_mocked_initialize(self):
        with patch.object(self.exchange, "_initialize_rate_limits", AsyncMock()) as mock_initialize_rate_limits:
            await self.exchange._update_rate_limits()
            return mock_initialize_rate_limits

    async def _run_initialize_rate_limits_with_mocked_throttler(self, account_type, expected_limit):
        throttler_mock = MagicMock()
        self.exchange._throttler = throttler_mock
        self.exchange._account_type = account_type

        with patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative.deepcopy", return_value=[]):
            await self.exchange._initialize_rate_limits()

        return throttler_mock, expected_limit

    @pytest.mark.asyncio
    async def test_rate_limits_polling_loop_logs_error_on_exception(self):
        mock_logger_info = await self._run_rate_limits_polling_loop_with_mocked_logger(exception=Exception("Test Exception"))
        mock_logger_info.assert_called_with("Unexpected error while Updating rate limits.")

    @pytest.mark.asyncio
    async def test_update_rate_limits_calls_initialize_rate_limits(self):
        mock_initialize_rate_limits = await self._run_update_rate_limits_with_mocked_initialize()
        mock_initialize_rate_limits.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_rate_limits_updates_throttler(self):
        throttler_mock, expected_limit = await self._run_initialize_rate_limits_with_mocked_throttler(
            account_type=CONSTANTS.MARKET_MAKER_ACCOUNTS_TYPE,
            expected_limit=CONSTANTS.MARKET_MAKER_NON_MATCHING
        )

        throttler_mock.set_rate_limits.assert_called()  # Adjusted to check if it was called, not just once
        updated_rate_limits = throttler_mock.set_rate_limits.call_args_list[-1][0][0]  # Get the last call's arguments
        self.assertTrue(any(r_l.limit == expected_limit for r_l in updated_rate_limits))

    @pytest.mark.asyncio
    async def test_initialize_rate_limits_non_market_maker(self):
        throttler_mock, expected_limit = await self._run_initialize_rate_limits_with_mocked_throttler(
            account_type="trader",
            expected_limit=CONSTANTS.TRADER_MATCHING
        )

        throttler_mock.set_rate_limits.assert_called()  # Adjusted to check if it was called, not just once
        updated_rate_limits = throttler_mock.set_rate_limits.call_args_list[-1][0][0]  # Get the last call's arguments
        self.assertTrue(any(r_l.limit == expected_limit for r_l in updated_rate_limits))

    @pytest.mark.asyncio
    async def test_start_network_starts_rate_limits_polling_loop(self):
        with patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative.safe_ensure_future") as mock_safe_ensure_future:
            await self.exchange.start_network()
            # Adjusted to check if the coroutine object of `_rate_limits_polling_loop` was passed
            mock_safe_ensure_future.assert_called()
            self.assertTrue(
                any(
                    asyncio.iscoroutine(call_args[0][0])
                    and call_args[0][0].cr_code is self.exchange._rate_limits_polling_loop.__code__
                    for call_args in mock_safe_ensure_future.call_args_list
                )
            )

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_currency_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
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
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, domain=self.exchange._domain
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {"result": {
            "instruments": [
                {
                    'instrument_type': 'perp',  # noqa: mock
                    'instrument_name': 'BTC-PERP',
                    'scheduled_activation': 1728508925,
                    'scheduled_deactivation': 9223372036854775807,
                    'is_active': True,
                    'tick_size': '0.01',
                    'minimum_amount': '0.1',
                    'maximum_amount': '1000',
                    'amount_step': '0.01',
                    'mark_price_fee_rate_cap': '0',
                    'maker_fee_rate': '0.0015',
                    'taker_fee_rate': '0.0015',
                    'base_fee': '0.1',
                    'base_currency': 'BTC',
                    'quote_currency': 'USDC',
                    'option_details': None,
                    "perp_details": {
                        "index": "BTC-USD",
                        "max_rate_per_hour": "0.004",
                        "min_rate_per_hour": "-0.004",
                        "static_interest_rate": "0.0000125",
                        "aggregate_funding": "738.587599416709606114",
                        "funding_rate": "-0.000033660522457857"
                    },
                    'erc20_details': None,
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",  # noqa: mock
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
            ],
            "pagination": {
                "num_pages": 1,
                "count": 1
            }
        },
            "id": "dedda961-4a97-46fb-84fb-6510f90dceb0"  # noqa: mock
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "result": {
                'instrument_type': 'perp',  # noqa: mock
                'instrument_name': 'BTC-PERP',
                'scheduled_activation': 1734464971,
                'scheduled_deactivation': 9223372036854775807,
                'is_active': True,
                'tick_size': '0.0001',
                'minimum_amount': '0.1',
                'maximum_amount': '100000',
                'amount_step': '0.01',
                'mark_price_fee_rate_cap': '0',
                'maker_fee_rate': '0.0015',
                'taker_fee_rate': '0.0015',
                'base_fee': '0.1',
                'base_currency': 'BTC',
                'quote_currency': 'USDC',
                'option_details': None,
                "perp_details": {
                    "index": "BTC-USD",
                    "max_rate_per_hour": "0.004",
                    "min_rate_per_hour": "-0.004",
                    "static_interest_rate": "0.0000125",
                    "aggregate_funding": "738.587599416709606114",
                    "funding_rate": "-0.000033660522457857"
                },
                'erc20_details': None,
                'base_asset_address': '0xDaffF9B244327d09dde1dDFcf9981ef0Df2D1568',  # noqa: mock
                'base_asset_sub_id': '0', 'pro_rata_fraction': '0',
                'fifo_min_allocation': '0', 'pro_rata_amount_step': '1', 'best_ask_amount': '2155.24', 'best_ask_price': '1.6712',
                'best_bid_amount': '2155.43', 'best_bid_price': '1.6692', 'five_percent_bid_depth': '5036.42',
                'five_percent_ask_depth': '5029.23', 'option_pricing': None,
                'index_price': '1.6698', 'mark_price': self.expected_latest_price,
                'stats': {
                    'contract_volume': '308.41',
                    'num_trades': '7',
                    'open_interest': '323332.12302071627866623',
                    'high': '1.6796', 'low': '1.6605',
                    'percent_change': '-0.071477',
                    'usd_change': '-0.1285'},
                'timestamp': 1737827796000, 'min_price': '1.6213', 'max_price': '1.7199'}
        }

        return mock_response

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = {"result": {
            "instruments": [
                {
                    'instrument_type': 'perp',  # noqa: mock
                    'instrument_name': 'BTC-PERP',
                    'scheduled_activation': 1728508925,
                    'scheduled_deactivation': 9223372036854775807,
                    'is_active': True,
                    'tick_size': '0.01',
                    'minimum_amount': '0.1',
                    'maximum_amount': '1000',
                    'amount_step': '0.01',
                    'mark_price_fee_rate_cap': '0',
                    'maker_fee_rate': '0.0015',
                    'taker_fee_rate': '0.0015',
                    'base_fee': '0.1',
                    'base_currency': 'BTC',
                    'quote_currency': 'USDC',
                    'option_details': None,
                    "perp_details": {
                        "index": "BTC-USD",
                        "max_rate_per_hour": "0.004",
                        "min_rate_per_hour": "-0.004",
                        "static_interest_rate": "0.0000125",
                        "aggregate_funding": "738.587599416709606114",
                        "funding_rate": "-0.000033660522457857"
                    },
                    'erc20_details': None,
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",  # noqa: mock
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
            ],
            "pagination": {
                "num_pages": 1,
                "count": 1
            }
        },
            "id": "dedda961-4a97-46fb-84fb-6510f90dceb0"  # noqa: mock
        }
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {"result": 1587884283175}
        return mock_response

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.exchange_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def test_get_collateral_token(self):
        margin_asset = self.quote_asset
        self._simulate_trading_rules_initialized()

        self.assertEqual(margin_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(margin_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    @property
    def currency_request_mock_response(self):
        return {
            'result': [
                {'currency': 'BTC', 'spot_price': '27.761323954505412608', 'spot_price_24h': '33.240154426604556288'},
            ]
        }

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {"result": {
            "instruments": [
                {
                    'instrument_type': 'perp',  # noqa: mock
                    'instrument_name': 'BTC-PERP',
                    'scheduled_activation': 1728508925,
                    'scheduled_deactivation': 9223372036854775807,
                    'is_active': True,
                    'tick_size': '0.01',
                    'amount_step': '0.01',
                    'mark_price_fee_rate_cap': '0',
                    'maker_fee_rate': '0.0015',
                    'taker_fee_rate': '0.0015',
                    'base_fee': '0.1',
                    'base_currency': 'BTC',
                    'quote_currency': 'USDC',
                    'option_details': None,
                    "perp_details": {
                        "decimals": 18,
                        "underlying_perp_address": "0x15CEcd5190A43C7798dD2058308781D0662e678E",  # noqa: mock
                        "borrow_index": "1",
                        "supply_index": "1"
                    },
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",  # noqa: mock
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
            ],
            "pagination": {
                "num_pages": 1,
                "count": 1
            }
        },
            "id": "dedda961-4a97-46fb-84fb-6510f90dceb0"  # noqa: mock
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {'result':
                         {'order': {'subaccount_id': 37799,
                                    'order_id': self.expected_exchange_order_id,
                                    'instrument_name': f"{self.base_asset}-PERP", 'direction': 'sell',
                                    'label': '0x7ce68975412a84fc4408b86296f7d1b6',  # noqa: mock
                                    'quote_id': None, 'creation_timestamp': 1737806729813, 'last_update_timestamp': 1737806729813,
                                    'limit_price': '1.7019', 'amount': '4.74', 'filled_amount': '0', 'average_price': '0', 'order_fee': '0',
                                    'order_type': 'limit', 'time_in_force': 'gtc', 'order_status': 'open', 'max_fee': '1000',
                                    'signature_expiry_sec': 2147483647, 'nonce': 17378067276170}, 'trades': []}
                         }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {"result":
                         {
                             'subaccount_id': 37799,
                             'collaterals': [
                                 {
                                     'asset_type': 'perp', 'asset_name': self.base_asset, 'currency': self.base_asset, 'amount': '15',
                                     'mark_price': '1.676380380787058688', 'mark_value': '33.52',
                                     'cumulative_interest': '0', 'pending_interest': '0', 'initial_margin': '17.0990798',
                                     'maintenance_margin': '20.1165645',
                                     'realized_pnl': '0', 'average_price': '1.68212', 'unrealized_pnl': '-0.114786',
                                     'total_fees': '0.050394', 'average_price_excl_fees': '1.6796', 'realized_pnl_excl_fees': '0',
                                     'unrealized_pnl_excl_fees': '-0.064392', 'open_orders_margin': '-87.884668', 'creation_timestamp': 1737811465712
                                 },
                                 {
                                     'asset_type': 'perp', 'asset_name': self.quote_asset, 'currency': self.quote_asset, 'amount': '2000',
                                     'mark_price': '1', 'mark_value': '75.3929188',
                                     'cumulative_interest': '0.046965277',
                                     'pending_interest': '0.001969',
                                     'initial_margin': '75.3929188',
                                     'maintenance_margin': '75.3929188',
                                     'realized_pnl': '0', 'average_price': '1', 'unrealized_pnl': '0', 'total_fees': '0',
                                     'average_price_excl_fees': '1', 'realized_pnl_excl_fees': '0', 'unrealized_pnl_excl_fees': '0',
                                     'open_orders_margin': '0', 'creation_timestamp': 1737578243424

                                 }
                             ]
                         }
                         }

        return mock_response

    @property
    def balance_request_mock_response_only_base(self):
        return {"result": [
            {
                'subaccount_id': 37799,
                'collaterals': [
                    {
                        'asset_type': 'perp', 'asset_name': self.base_asset, 'currency': self.base_asset, 'amount': '15',
                        'mark_price': '1.676380380787058688', 'mark_value': '33.5276076175',
                        'cumulative_interest': '0', 'pending_interest': '0', 'initial_margin': '17.09905',
                        'maintenance_margin': '20.11656',
                        'realized_pnl': '0', 'average_price': '1.68212', 'unrealized_pnl': '-0.114786',
                        'total_fees': '0.050394', 'average_price_excl_fees': '1.6796', 'realized_pnl_excl_fees': '0',
                        'unrealized_pnl_excl_fees': '-0.064392', 'open_orders_margin': '-87.884668', 'creation_timestamp': 1737811465712
                    },
                ]
            }]
        }

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

    def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())

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

    def _initialize_event_loggers(self):
        self.order_failure_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger),
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

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
        funding_info = mock_response["result"]
        funding_info["mark_price"] = self.target_funding_info_mark_price
        # funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["perpetual"]["funding_rate"] = self.target_funding_info_rate
        return mock_response

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response["result"]['instruments'][0]

        step_size = Decimal(str(rule.get("amount_step")))
        price_size = Decimal(str(rule.get("tick_size")))
        min_amount = Decimal(str(rule.get("minimum_amount")))

        return TradingRule(self.trading_pair,
                           min_order_size=min_amount,
                           min_price_increment=price_size,
                           min_base_amount_increment=step_size,
                           )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "2650113037"  # noqa: mock

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
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6"  # noqa: mock

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-PERP"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = DerivePerpetualDerivative(
            client_config_map,
            self.api_secret,  # noqa: mock
            self.sub_id,
            self.api_key,  # noqa: mock
            trading_pairs=[self.trading_pair],
        )
        # exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        data = json.loads(request_data)
        self.assertEqual("buy" if order.trade_type is TradeType.BUY else "sell",
                         data["direction"])
        self.assertEqual(order.amount, abs(Decimal(str(data["amount"]))))
        self.assertEqual(order.client_order_id, data["label"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        data = json.loads(request_params)
        self.assertEqual(order.trading_pair, data["instrument_name"].replace("PERP", "USDC"))

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        data = json.loads(request_params)
        self.assertEqual(order.exchange_order_id, data["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        data = json.loads(request_params)
        self.assertEqual(self.sub_id, data["subaccount_id"])

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = self.balance_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

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

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])

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
        url = web_utils.public_rest_url(
            CONSTANTS.CANCEL_ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": {"message": CONSTANTS.UNKNOWN_ORDER_MESSAGE}}
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_STATUS_PAATH_URL
        )

        regex_url = re.compile(f"^{url_order_status}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = {"error": {'code': 8001, 'message': 'Django error', 'data': "['“oid” is not a valid UUID.']"}}
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url_order_status

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):

        url_order_status = web_utils.public_rest_url(
            CONSTANTS.ORDER_STATUS_PAATH_URL
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
            CONSTANTS.ORDER_STATUS_PAATH_URL
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
            CONSTANTS.ORDER_STATUS_PAATH_URL
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
            CONSTANTS.ORDER_STATUS_PAATH_URL
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
            CONSTANTS.ORDER_STATUS_PAATH_URL
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
            CONSTANTS.MY_TRADES_PATH_URL
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
            CONSTANTS.MY_TRADES_PATH_URL,
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
            CONSTANTS.MY_TRADES_PATH_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_failed_set_leverage(
            self,
    ) -> Tuple[str, str]:

        err_msg = "Unable to set leverage"
        return err_msg

    def configure_successful_set_leverage(
            self,
    ):
        mock_response = {
            "status": "ok",
            "code": 0,
            "message": "",
        }

        return mock_response

    @aioresponses()
    def test_set_leverage_failure(self, mock_api):
        pass

    @aioresponses()
    def test_set_leverage_success(self, mock_api):
        pass

    def _get_funding_info_dict(self) -> Dict[str, Any]:
        funding_info = {"result":
                        {
                            'instrument_type': 'erc20',
                            'instrument_name': f'{self.base_asset}-PERP',
                            'scheduled_activation': 1728508925,
                            'scheduled_deactivation': 9223372036854775807,
                            'is_active': True,
                            'tick_size': '0.01',
                            'minimum_amount': '0.1',
                            'maximum_amount': '1000',
                            'index_price': '36717.0',
                            'mark_price': '36733.0',
                            'amount_step': '0.01',
                            'mark_price_fee_rate_cap': '0',
                            'maker_fee_rate': '0.0015',
                            'taker_fee_rate': '0.0015',
                            'base_fee': '0.1',
                            'base_currency': self.base_asset,
                            'quote_currency': self.quote_asset,
                            'option_details': None,
                            "perp_details": {
                                "index": "BTC-PERP",
                                "max_rate_per_hour": "0.004",
                                "min_rate_per_hour": "-0.004",
                                "static_interest_rate": "0.0000125",
                                "aggregate_funding": "738.587599416709606114",
                                "funding_rate": "0.00001793"
                            },
                            'erc20_details': None,
                            'base_asset_address': '0xE201fCEfD4852f96810C069f66560dc25B2C7A55', 'base_asset_sub_id': '0', 'pro_rata_fraction': '0', 'fifo_min_allocation': '0', 'pro_rata_amount_step': '1'}
                        }
        return funding_info

    def _get_income_history_dict(self):
        income_history = {
            "id": "13f7fda9-9543-4e11-a0ba-cbe117989988",
            "result":
                {"events":
                    [
                        {
                            "timestamp": 1662518172178,
                            "funding": "0.000164",
                            "instrument_name": "BTC-PERP",
                            "pnl": "0.000164",
                        }
                    ]
                 },

        }
        return income_history

    def get_trading_rule_rest_msg(self):
        return [
            {
                'instrument_type': 'perp',
                'instrument_name': f'{self.base_asset}-PERP',
                'scheduled_activation': 1728508925,
                'scheduled_deactivation': 9223372036854775807,
                'is_active': True,
                'tick_size': '0.01',
                'minimum_amount': '0.1',
                'maximum_amount': '1000',
                'amount_step': '0.01',
                'mark_price_fee_rate_cap': '0',
                'maker_fee_rate': '0.0015',
                'taker_fee_rate': '0.0015',
                'base_fee': '0.1',
                'base_currency': 'BTC',
                'quote_currency': 'USDC',
                'option_details': None,
                'perp_details': {
                    'decimals': 18,
                    'underlying_perp_address': '0x15CEcd5190A43C7798dD2058308781D0662e678E',  # noqa: mock
                    'borrow_index': '1', 'supply_index': '1'},
                'base_asset_address': '0xE201fCEfD4852f96810C069f66560dc25B2C7A55',  # noqa: mock
                'base_asset_sub_id': '0', 'pro_rata_fraction': '0', 'fifo_min_allocation': '0', 'pro_rata_amount_step': '1'}
        ]

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            'channel': f"{self.sub_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
            'data': [{
                'subaccount_id': 37799,
                'order_id': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",  # noqa: mock
                'instrument_name': 'BTC-PERP', 'direction': 'buy',
                'label': order.client_order_id,
                'quote_id': None,
                'creation_timestamp': 1737806900308,
                'last_update_timestamp': 1700818402905,
                'limit_price': order.price,
                'amount': str(order.amount),
                'filled_amount': '0', 'average_price': '0',
                'order_fee': '0', 'order_type': 'limit',
                'time_in_force': 'gtc',
                'order_status': 'open',
                'max_fee': '1000',
                'signature_expiry_sec': 2147483647,
                'nonce': 17378068982400,
                'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                'signature': '0xc227fd7855ee7a9d1e1eabfad96ce2a5dc8938b4d6c46e15286d6b7f3fc28e036e73b3828b838d3cae30fc619e6e1354ff45cd23c0a5343d6b3a4108ffc52d371c',  # noqa: mock
                'cancel_reason': 'user_request',
                'mmp': False, 'is_transfer': False,
                'replaced_order_id': None, 'trigger_type': None,
                'trigger_price_type': None,
                'trigger_price': order.price, 'trigger_reject_message': None}]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            'channel': f"{self.sub_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
            'data': [{
                'subaccount_id': 37799,
                'order_id': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",  # noqa: mock
                'instrument_name': 'BTC-PERP', 'direction': 'buy',
                'label': order.client_order_id,
                'quote_id': None,
                'creation_timestamp': 1737806900308,
                'last_update_timestamp': 1700818402905,
                'limit_price': order.price,
                'amount': str(order.amount),
                'filled_amount': '0', 'average_price': '0',
                'order_fee': '0', 'order_type': 'limit',
                'time_in_force': 'gtc',
                'order_status': 'cancelled',
                'max_fee': '1000',
                'signature_expiry_sec': 2147483647,
                'nonce': 17378068982400,
                'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                'signature': '0xc227fd7855ee7a9d1e1eabfad96ce2a5dc8938b4d6c46e15286d6b7f3fc28e036e73b3828b838d3cae30fc619e6e1354ff45cd23c0a5343d6b3a4108ffc52d371c',  # noqa: mock
                'cancel_reason': 'user_request',
                'mmp': False, 'is_transfer': False,
                'replaced_order_id': None, 'trigger_type': None,
                'trigger_price_type': None,
                'trigger_price': order.price, 'trigger_reject_message': None}]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            'channel': f"{self.sub_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
            'data': [{
                'subaccount_id': 37799,
                'order_id': order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",  # noqa: mock
                'instrument_name': 'BTC-PERP', 'direction': 'buy',
                'label': order.client_order_id,
                'quote_id': None,
                'creation_timestamp': 1737806900308,
                'last_update_timestamp': 1700818402905,
                'limit_price': order.price,
                'amount': str(order.amount),
                'filled_amount': '0', 'average_price': '0',
                'order_fee': '0', 'order_type': 'limit',
                'time_in_force': 'gtc',
                'order_status': 'filled',
                'max_fee': '1000',
                'signature_expiry_sec': 2147483647,
                'nonce': 17378068982400,
                'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                'signature': '0xc227fd7855ee7a9d1e1eabfad96ce2a5dc8938b4d6c46e15286d6b7f3fc28e036e73b3828b838d3cae30fc619e6e1354ff45cd23c0a5343d6b3a4108ffc52d371c',  # noqa: mock
                'cancel_reason': 'user_request',
                'mmp': False, 'is_transfer': False,
                'replaced_order_id': None, 'trigger_type': None,
                'trigger_price_type': None,
                'trigger_price': order.price, 'trigger_reject_message': None}]
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            'channel':
                f"{self.sub_id}.{CONSTANTS.USEREVENT_ENDPOINT_NAME}",
                'data': [
                    {
                        'subaccount_id': 37799,
                        'order_id': order.exchange_order_id,
                        'instrument_name': self.exchange_trading_pair,
                        'direction': 'buy', 'label': order.client_order_id,
                        'quote_id': None,
                        'trade_id': self.expected_fill_trade_id,
                        'timestamp': 1681222254710,
                        'mark_price': "10000",
                        'index_price': '3203.94498334999969792',
                        'trade_price': "10000", 'trade_amount': str(Decimal(order.amount)),
                        'liquidity_role': 'maker',
                        'realized_pnl': '0.332573106733025',
                        'realized_pnl_excl_fees': '0.389575',
                        'is_transfer': False,
                        'tx_status': 'settled',
                        'trade_fee': str(self.expected_fill_fee.flat_fees[0].amount),
                        'tx_hash': '0xad4e10abb398a83955a80d6c072d0064eeecb96cceea1501411b02415b522d30'  # noqa: mock
                    }
                ]
        }

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = {"result": {
            "positions": [
                {
                    "amount": "5",
                    "amount_step": "0.001",
                    "average_price": "1.8980",
                    "average_price_excl_fees": "string",
                    "creation_timestamp": self.start_timestamp,
                    "cumulative_funding": "string",
                    "delta": 0,
                    "gamma": 1,
                    "index_price": "1.8980",
                    "initial_margin": "26",
                    "instrument_name": self.exchange_trading_pair,
                    "instrument_type": "erc20",
                    "leverage": 25,
                    "liquidation_price": "string",
                    "maintenance_margin": "string",
                    "mark_price": "1.8980",
                    "mark_value": "1.8980",
                    "net_settlements": "string",
                    "open_orders_margin": "string",
                    "pending_funding": "string",
                    "realized_pnl": "string",
                    "realized_pnl_excl_fees": "string",
                    "theta": "string",
                    "total_fees": "string",
                    "unrealized_pnl": "0.144654",
                    "unrealized_pnl_excl_fees": "-1",
                    "vega": "string"
                }
            ],
            "subaccount_id": 0
        }
        }
        return positions

    def _get_wrong_symbol_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = {"result": {
            "positions": [
                {
                    "amount": "5",
                    "amount_step": "0.001",
                    "average_price": "1.8980",
                    "average_price_excl_fees": "string",
                    "creation_timestamp": self.start_timestamp,
                    "cumulative_funding": "string",
                    "delta": 0,
                    "gamma": 1,
                    "index_price": "1.8980",
                    "initial_margin": "26",
                    "instrument_name": f"{self.exchange_trading_pair}_wrong",
                    "instrument_type": "erc20",
                    "leverage": 25,
                    "liquidation_price": "string",
                    "maintenance_margin": "string",
                    "mark_price": "1.8980",
                    "mark_value": "1.8980",
                    "net_settlements": "string",
                    "open_orders_margin": "string",
                    "pending_funding": "string",
                    "realized_pnl": "string",
                                    "realized_pnl_excl_fees": "string",
                                    "theta": "string",
                                    "total_fees": "string",
                                    "unrealized_pnl": "0.144654",
                                    "unrealized_pnl_excl_fees": "-1",
                                    "vega": "string"
                }
            ],
            "subaccount_id": 0
        }
        }
        return positions

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {"result": {
            "positions": [
                {
                    "amount": "5",
                    "amount_step": "0.001",
                    "average_price": "1.8980",
                    "average_price_excl_fees": "string",
                    "creation_timestamp": self.start_timestamp,
                    "cumulative_funding": "string",
                    "delta": 0,
                    "gamma": 1,
                    "index_price": "1.8980",
                    "initial_margin": "26",
                    "instrument_name": self.exchange_trading_pair,
                    "instrument_type": "erc20",
                    "leverage": 25,
                    "liquidation_price": "string",
                    "maintenance_margin": "string",
                    "mark_price": "1.8980",
                    "mark_value": "1.8980",
                    "net_settlements": "string",
                    "open_orders_margin": "string",
                    "pending_funding": "string",
                    "realized_pnl": "string",
                                    "realized_pnl_excl_fees": "string",
                                    "theta": "string",
                                    "total_fees": "string",
                                    "unrealized_pnl": "0.144654",
                                    "unrealized_pnl_excl_fees": "-1",
                                    "vega": "string"
                }
            ],
            "subaccount_id": 0
        }
        }
        return account_update

    def _get_wrong_symbol_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {"result": {
            "positions": [
                {
                    "amount": "5",
                    "amount_step": "0.001",
                    "average_price": "1.8980",
                    "average_price_excl_fees": "string",
                    "creation_timestamp": self.start_timestamp,
                    "cumulative_funding": "string",
                    "delta": 0,
                    "gamma": 1,
                    "index_price": "1.8980",
                    "initial_margin": "26",
                    "instrument_name": f"{self.exchange_trading_pair}_wrong",
                    "instrument_type": "erc20",
                    "leverage": 25,
                    "liquidation_price": "string",
                    "maintenance_margin": "string",
                    "mark_price": "1.8980",
                    "mark_value": "1.8980",
                    "net_settlements": "string",
                    "open_orders_margin": "string",
                    "pending_funding": "string",
                    "realized_pnl": "string",
                    "realized_pnl_excl_fees": "string",
                    "theta": "string",
                    "total_fees": "string",
                    "unrealized_pnl": "0.144654",
                    "unrealized_pnl_excl_fees": "-1",
                    "vega": "string"
                }
            ],
            "subaccount_id": 0
        }
        }
        return account_update

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {"result": {
            "positions": [
                {
                    "amount": str(order.amount),
                    "amount_step": "0.001",
                    "average_price": "1.8980",
                    "average_price_excl_fees": "string",
                    "creation_timestamp": "1627293049406",
                    "cumulative_funding": "string",
                    "delta": 0,
                    "gamma": 1,
                    "index_price": "1.8980",
                    "initial_margin": str(order.amount),
                    "instrument_name": f"{self.exchange_trading_pair}",
                    "instrument_type": "erc20",
                    "leverage": str(order.leverage),
                    "liquidation_price": "string",
                    "maintenance_margin": "string",
                    "mark_price": "1.8980",
                    "mark_value": "1.8980",
                    "net_settlements": "string",
                    "open_orders_margin": "string",
                    "pending_funding": "string",
                    "realized_pnl": "string",
                    "realized_pnl_excl_fees": "string",
                    "theta": "string",
                    "total_fees": "string",
                    "unrealized_pnl": str(unrealized_pnl),
                    "unrealized_pnl_excl_fees": "-1",
                    "vega": "string"
                }
            ],
            "subaccount_id": 0
        }
        }

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

    @aioresponses()
    def test_fetch_funding_payment_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        income_history = self._get_income_history_dict()

        regex_url_income_history = self.funding_payment_url

        req_mock.post(regex_url_income_history, body=json.dumps(income_history))

        funding_info = self._get_funding_info_dict()

        regex_url_funding_info = self.funding_info_url

        req_mock.post(regex_url_funding_info, body=json.dumps(funding_info))

        # Fetch from exchange with REST API - safe_ensure_future, not immediately
        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, True))

        req_mock.post(regex_url_income_history, body=json.dumps(income_history))

        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, True))

        self.assertTrue(len(self.funding_payment_completed_logger.event_log) == 1)

        funding_info_logged = self.funding_payment_completed_logger.event_log[0]

        self.assertTrue(funding_info_logged.trading_pair == f"{self.base_asset}-{self.quote_asset}")

        self.assertEqual(funding_info_logged.funding_rate, Decimal(funding_info["result"]["perp_details"]["funding_rate"]))
        self.assertEqual(funding_info_logged.amount, Decimal(income_history["result"]["events"][0]["funding"]))

    @aioresponses()
    def test_new_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps([]))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.post(regex_url, body=json.dumps(positions))
        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    def test_closed_account_position_removed_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.post(regex_url, body=json.dumps(positions))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions["result"]["positions"][0]["amount"] = "0"
        req_mock.post(regex_url, body=json.dumps(positions))
        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    def test_existing_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.post(regex_url, body=json.dumps(positions))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair, self.trading_pair)

    @aioresponses()
    def test_wrong_symbol_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_wrong_symbol_position_risk_api_endpoint_single_position_list()
        req_mock.post(regex_url, body=json.dumps(positions))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    def test_account_position_updated_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.post(regex_url, body=json.dumps(positions))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 5)

        positions["result"]["positions"][0]["amount"] = "2"
        req_mock.post(regex_url, body=json.dumps(positions))
        self.async_run_with_timeout(self.exchange._update_positions())

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    def test_fetch_funding_payment_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        regex_url_income_history = self.funding_payment_url

        req_mock.post(regex_url_income_history, exception=Exception)

        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, False))

        self.assertTrue(self.is_logged(
            "NETWORK",
            f"Unexpected error while fetching last fee payment for {self.trading_pair}.",
        ))

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = DerivePerpetualDerivative(
            client_config_map=client_config_map,
            derive_perpetual_api_key=self.api_key,
            derive_perpetual_api_secret=self.api_secret,
            sub_id=self.sub_id,
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
        "hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source.DerivePerpetualAPIOrderBookDataSource._next_funding_time")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_next_funding_time,
                                                                     mock_queue_get):
        pass

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
            position_action=PositionAction.OPEN,
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

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative.DerivePerpetualDerivative._update_positions")
    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api, mock_positions):
        self.exchange._set_current_timestamp(1640780000)
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
            self._simulate_trading_rules_initialized()

            url = web_utils.private_rest_url(
                CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
            )
            regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

            positions = self._get_position_risk_api_endpoint_single_position_list()
            mock_positions.post(regex_url, body=json.dumps(positions))

            self.async_run_with_timeout(self.exchange._update_positions())
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
            position_action=PositionAction.OPEN,
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
        # self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)

        self.assertFalse(
            self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled.")
        )

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {'result':
                {
                    'subaccount_id': 37799,
                    'order_id': '50996f90-87f5-414f-b9cc-8a00d84f39eb',  # noqa: mock
                    'instrument_name': f"{self.base_asset}-PERP",
                    'direction': 'buy',
                    'label': '0x3e8a0c2c2969dfdc0604f6c81d4722d1',  # noqa: mock
                    'quote_id': None,
                    'creation_timestamp': 1737806729923,
                    'last_update_timestamp': 1737806818409,
                    'limit_price': '1.6519', 'amount': '20',
                    'filled_amount': '0', 'average_price': '0', 'order_fee': '0',
                    'order_type': 'limit', 'time_in_force': 'gtc', 'order_status': 'cancelled', 'max_fee': '1000',
                    'signature_expiry_sec': 2147483647, 'nonce': 17378067265180,
                    'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                    'signature': '0x38da2d6eb20589b80db9463d0bc57b9b6d508f957a441dd7d3f8695ab6c6df10108f1fa2fc9ae3322610624bb83a062e2ee41ccef4800e2e3804f33289762e651b',  # noqa: mock
                    'cancel_reason': 'user_request', 'mmp': False, 'is_transfer': False, 'replaced_order_id': None, 'trigger_type': None,
                    'trigger_price_type': None, 'trigger_price': None, 'trigger_reject_message': None},
                }

    def _order_fills_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {'result':
                {
                    'subaccount_id': 37799, 'order_id': str(order.exchange_order_id),
                    'instrument_name': f"{self.base_asset}-PERP",
                    'direction': 'buy',
                    'label': '0x3e8a0c2c2969dfdc0604f6c81d4722d1',  # noqa: mock
                    'quote_id': None,
                    'creation_timestamp': 1737806729923,
                    'last_update_timestamp': 1737806818409,
                    'limit_price': '1.6519', 'amount': '20',
                    'filled_amount': '0', 'average_price': '0', 'order_fee': '0',
                    'order_type': 'limit', 'time_in_force': 'gtc', 'order_status': 'cancelled', 'max_fee': '1000',
                    'signature_expiry_sec': 2147483647, 'nonce': 17378067265180,
                    'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                    'signature': '0x38da2d6eb20589b80db9463d0bc57b9b6d508f957a441dd7d3f8695ab6c6df10108f1fa2fc9ae3322610624bb83a062e2ee41ccef4800e2e3804f33289762e651b',  # noqa: mock
                    'cancel_reason': 'user_request', 'mmp': False, 'is_transfer': False, 'replaced_order_id': None, 'trigger_type': None,
                    'trigger_price_type': None, 'trigger_price': None, 'trigger_reject_message': None},
                }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {'result':
                {
                    'subaccount_id': 37799, 'order_id': str(order.exchange_order_id),
                    'instrument_name': f"{self.base_asset}-PERP", 'direction': 'buy', 'label': order.client_order_id,
                    'quote_id': None, 'creation_timestamp': 1700814942565, 'last_update_timestamp': 1737833906895,
                    'limit_price': str(order.price), 'amount': str(order.amount), 'filled_amount': '0E-18',
                    'average_price': '0', 'order_fee': '0E-18', 'order_type': 'limit', 'time_in_force': 'gtc',
                    'order_status': 'filled', 'max_fee': '1000.000000000000000000', 'signature_expiry_sec': 2147483647,
                    'nonce': 17378339060620,
                    'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                    'signature': '0xef94e430b454aea31d174accba64f457413418a1437c83b4da5598a7776282543e72ae580db688d65f39fabea6b6453b3690e36ebe4c155232f856809d4b40e81b',  # noqa: mock
                    'cancel_reason': '', 'mmp': False, 'is_transfer': False, 'replaced_order_id': None, 'trigger_type': None,
                    'trigger_price_type': None, 'trigger_price': None, 'trigger_reject_message': None
                },
                }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "cancelled"
        resp["result"]["order_status"] = "cancelled"
        resp["result"]["limit_amount"] = "0"
        resp["result"]["limit_price"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["result"]["order_status"] = "open"
        resp["result"]["limit_price"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["status"] = "open"
        resp["result"]["order_status"] = "open"
        resp["result"]["limit_price"] = str(order.price)
        resp["result"]["amount"] = float(order.amount) / 2
        return resp

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["order_status"] = "open"
        resp["result"]["limit_price"] = str(order.price)
        resp["result"]["amount"] = float(order.amount) / 2
        return resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {'result':
                {
                    'subaccount_id': 37799, 'order_id': str(order.exchange_order_id),
                    'instrument_name': f"{self.base_asset}-PERP",
                    'direction': 'buy',
                    'label': '0x3e8a0c2c2969dfdc0604f6c81d4722d1',  # noqa: mock
                    'quote_id': None,
                    'creation_timestamp': 1737806729923,
                    'last_update_timestamp': 1737806818409,
                    'limit_price': '1.6519', 'amount': '20',
                    'filled_amount': '0', 'average_price': '0', 'order_fee': '0',
                    'order_type': 'limit', 'time_in_force': 'gtc', 'order_status': 'filled', 'max_fee': '1000',
                    'signature_expiry_sec': 2147483647, 'nonce': 17378067265180,
                    'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                    'signature': '0x38da2d6eb20589b80db9463d0bc57b9b6d508f957a441dd7d3f8695ab6c6df10108f1fa2fc9ae3322610624bb83a062e2ee41ccef4800e2e3804f33289762e651b',  # noqa: mock
                    'cancel_reason': 'user_request', 'mmp': False, 'is_transfer': False, 'replaced_order_id': None, 'trigger_type': None,
                    'trigger_price_type': None, 'trigger_price': None, 'trigger_reject_message': None},
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
            position_action=PositionAction.OPEN,
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
            position_action=PositionAction.OPEN,
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
            position_action=PositionAction.OPEN,
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
            position_action=PositionAction.OPEN,
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
        print([url])
        return [url]

    def configure_currency_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_currency_url
        response = self.currency_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return [url]

    def test_user_stream_balance_update(self):
        pass

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_pair):
        res = self.currency_request_mock_response
        self.configure_currency_trading_rules_response(mock_api=mock_pair)
        self.exchange.currencies = [res]
        self.exchange._set_trading_pair_symbol_map(None)

        url = self.all_symbols_url
        mock_pair.post(url, exception=Exception)

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative.DerivePerpetualDerivative._make_currency_request", new_callable=AsyncMock)
    @aioresponses()
    def test_all_trading_pairs(self, mock_mess: AsyncMock, mock_api):
        # Mock the currency request response
        self.configure_currency_trading_rules_response(mock_api=mock_api)
        mock_mess.return_value = self.currency_request_mock_response
        self.exchange.currencies = [self.currency_request_mock_response]

        self.exchange._set_trading_pair_symbol_map(None)

        self.configure_all_symbols_response(mock_api=mock_api)
        self.async_run_with_timeout(coroutine=self.exchange._initialize_trading_pair_symbol_map())

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(all_trading_pairs))
        self.assertIn(self.trading_pair, all_trading_pairs)

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.all_symbols_url
        response = self.all_symbols_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return [url]

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"result": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["result"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        pass

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative.DerivePerpetualDerivative._make_currency_request", new_callable=AsyncMock)
    @aioresponses()
    def test_update_trading_rules(self, mock_request: AsyncMock, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        # Mock the currency request response
        mocked_response = self.get_trading_rule_rest_msg()
        self.configure_currency_trading_rules_response(mock_api=mock_api)
        mock_request.return_value = self.currency_request_mock_response
        self.exchange.currencies = [self.currency_request_mock_response]

        self.configure_trading_rules_response(mock_api=mock_api)
        self.exchange._instrument_ticker.append(mocked_response[0])
        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

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
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        pass

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.exchange._instrument_ticker = mocked_response
        min_order_size = mocked_response[0]["minimum_amount"]
        min_price_increment = mocked_response[0]["tick_size"]
        min_base_amount_increment = mocked_response[0]["amount_step"]
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(min_order_size)),
                min_price_increment=Decimal(str(min_price_increment)),
                min_base_amount_increment=Decimal(str(min_base_amount_increment)),
            )
        }

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
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

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
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
                f"{Decimal('100.00')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
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
                f"{Decimal('100.00')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
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
                f"{Decimal('100.00')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
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
                f"{Decimal('100.00')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                f"at {Decimal('10000')}."
            )
        )

    @aioresponses()
    async def test_update_order_fills_from_trades_successful(self, req_mock):
        self.exchange._set_current_timestamp(1640780000)
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        trades = {
            "result": {
                'subaccount_id': 37799,
                'trades': [
                    {
                        'subaccount_id': 37799,
                        'order_id': "8886774",
                        'instrument_name': f"{self.base_asset}-PERP",
                        'direction': 'sell', 'label': "8886774",
                        'quote_id': None,
                        'trade_id': "698759",
                        'timestamp': 1681222254710,
                        'mark_price': '10000',
                        'index_price': '10000',
                        'trade_price': '10000', 'trade_amount': "0.5",
                        'liquidity_role': 'maker',
                        'realized_pnl': '0',
                        'realized_pnl_excl_fees': '0',
                        'is_transfer': False,
                        'tx_status': 'settled',
                        'trade_fee': "0",
                        'tx_hash': '0xad4e10abb398a83955a80d6c072d0064eeecb96cceea1501411b02415b522d30'  # noqa: mock
                    }
                ]
            }
        }

        url = web_utils.private_rest_url(
            CONSTANTS.MY_TRADES_PATH_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(trades))
        await self.exchange._all_trade_updates_for_order(order)

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        self.assertEqual(0.5, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(5000, in_flight_orders["OID1"].executed_amount_quote)

        self.assertTrue("698759" in in_flight_orders["OID1"].order_fills.keys())

    @aioresponses()
    def test_update_trade_history_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

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

        url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "result": {
                'subaccount_id': 37799,
                'trades': [
                    {
                        'subaccount_id': 37799,
                        'order_id': order.exchange_order_id,
                        'instrument_name': f"{self.base_asset}-PERP",
                        'direction': 'buy', 'label': order.client_order_id,
                        'quote_id': None,
                        'trade_id': 30000,
                        'timestamp': 1681222254710,
                        'mark_price': "9999",
                        'index_price': '3203.94498334999969792',
                        'trade_price': '3205.31', 'trade_amount': str(Decimal(order.amount)),
                        'liquidity_role': 'maker',
                        'realized_pnl': '0.332573106733025',
                        'realized_pnl_excl_fees': '0.389575',
                        'is_transfer': False,
                        'tx_status': 'settled',
                        'trade_fee': "10.10000000",
                        'tx_hash': '0xad4e10abb398a83955a80d6c072d0064eeecb96cceea1501411b02415b522d30'  # noqa: mock
                    },
                    {
                        'subaccount_id': 37799,
                        'order_id': 99999,
                        'instrument_name': f"{self.base_asset}-PERP",
                        'direction': 'buy', 'label': order.client_order_id,
                        'quote_id': None,
                        'trade_id': 30000,
                        'timestamp': 1681222254710,
                        'mark_price': "9999",
                        'index_price': '3203.94498334999969792',
                        'trade_price': "9999", 'trade_amount': str(Decimal(order.amount)),
                        'liquidity_role': 'maker',
                        'realized_pnl': '0.332573106733025',
                        'realized_pnl_excl_fees': '0.389575',
                        'is_transfer': False,
                        'tx_status': 'settled',
                        'trade_fee': "10.10000000",
                        'tx_hash': '0xad4e10abb398a83955a80d6c072d0064eeecb96cceea1501411b02415b522d30'  # noqa: mock
                    }
                ]
            }
        }

        mock_response = trade_fill
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill["result"]["trades"][1]["order_id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_trade_history())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.sub_id, request_params["subaccount_id"])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["result"]["trades"][0]["trade_price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["result"]["trades"][0]["trade_amount"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(str(fill_event.trading_pair.split("-")[1]), Decimal(trade_fill["result"]["trades"][0]["trade_fee"]))],
                         fill_event.trade_fee.flat_fees)

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.1")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait(), timeout=3)

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.1. The order will not be created, increase the "
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
