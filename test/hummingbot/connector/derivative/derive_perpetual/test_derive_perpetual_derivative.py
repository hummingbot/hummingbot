import asyncio
import json
import logging
import re
import time
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
from hummingbot.connector.other.derive_common_utils import RESTING_ORDER_VALIDITY_SEC, SESSION_KEY_EXPIRY_MARGIN_SEC
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
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
        cls.wallet_address = "0x79d7511382b5dFd1185F6AF268923D3F9FC31B53"  # noqa: mock
        cls.session_private_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        cls.subacct_id = "45686"  # noqa: mock
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
            derive_perpetual_wallet_address=self.wallet_address,
            session_private_key=self.session_private_key,
            subacct_id=self.subacct_id,
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
        self.assertEqual(len(CONSTANTS.RATE_LIMITS), len(self.throttler._rate_limits))

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
        # v3 slim ticker, as returned by public/get_ticker.
        mock_response = {
            "result": {
                't': 1737827796000,
                'A': '2155.24', 'a': '1.6712',
                'B': '2155.43', 'b': '1.6692',
                'f': '0.00001793',
                'option_pricing': None,
                'I': '1.6698',
                'M': str(self.expected_latest_price),
                'stats': {
                    'c': '308.41', 'v': '514.6', 'pr': '0', 'n': 7,
                    'oi': '323332.12302071627866623',
                    'h': '1.6796', 'l': '1.6605', 'p': '-0.071477',
                },
                'minp': '1.6213', 'maxp': '1.7199',
            }
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
                log_level="INFO",
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
        funding_info["M"] = self.target_funding_info_mark_price
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
        # An opening fill takes AddedToCostTradeFee; only a close takes DeductedFromReturns.
        # This used to expect DeductedFromReturns because position_side was compared against the
        # string "LONG" while holding a PositionSide enum, so every fill was classified CLOSE.
        return AddedToCostTradeFee(
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
        exchange = DerivePerpetualDerivative(
            session_private_key=self.session_private_key,  # noqa: mock
            derive_perpetual_wallet_address=self.wallet_address,  # noqa: mock
            subacct_id=self.subacct_id,
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
        self.assertEqual(int(self.subacct_id), data["subaccount_id"])

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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
            CONSTANTS.ORDER_STATUS_PATH_URL
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
        # v3 slim ticker: "f" is the current hourly funding rate, "I" the index and "M" the mark.
        # perp_details is not part of the slim payload.
        funding_info = {
            "result": {
                "t": 1662518172178,
                "A": "2155.24", "a": "36734.0",
                "B": "2155.43", "b": "36732.0",
                "f": "0.00001793",
                "option_pricing": None,
                "I": "36717.0",
                "M": "36733.0",
                "stats": {
                    "c": "308.41", "v": "514.6", "pr": "0", "n": 7,
                    "oi": "323332.12302071627866623",
                    "h": "36796.0", "l": "36605.0", "p": "-0.071477",
                },
                "minp": "36213.0", "maxp": "37199.0",
            }
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
            'channel': f"{self.subacct_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
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
            'channel': f"{self.subacct_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
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
            'channel': f"{self.subacct_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
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
                f"{self.subacct_id}.{CONSTANTS.USEREVENT_ENDPOINT_NAME}",
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
                    "M": "1.8980",
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
                    "M": "1.8980",
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
                    "M": "1.8980",
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
                    "M": "1.8980",
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
                    "M": "1.8980",
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

        # v3 slim ticker: the hourly funding rate is "f".
        self.assertEqual(funding_info_logged.funding_rate, Decimal(funding_info["result"]["f"]))
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
        linear_connector = DerivePerpetualDerivative(
            derive_perpetual_wallet_address=self.wallet_address,
            session_private_key=self.session_private_key,
            subacct_id=self.subacct_id,
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
        self.assertEqual(Decimal(str(self.expected_latest_price)), latest_prices[self.trading_pair])

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
        # Mock the currency request response
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

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        # Mock the currency request response
        mocked_response = self.get_trading_rule_rest_msg()

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

    @aioresponses()
    def test_update_trading_rules_filters_non_perp_instruments(self, mock_api):
        """Test line 804: Filter non-perp instrument types"""
        self.exchange._set_current_timestamp(1640780000)

        # Mock response with mixed instrument types
        mocked_response = {
            "result": {
                "instruments": [
                    {
                        'instrument_type': 'option',  # Should be filtered out - line 804
                        'instrument_name': 'ETH-25DEC',
                        'tick_size': '0.01',
                        'minimum_amount': '0.1',
                        'amount_step': '0.01',
                    },
                    {
                        'instrument_type': 'perp',  # Should be included
                        'instrument_name': f'{self.base_asset}-PERP',
                        'tick_size': '0.01',
                        'minimum_amount': '0.1',
                        'maximum_amount': '1000',
                        'amount_step': '0.01',
                        'base_currency': self.base_asset,
                        'quote_currency': self.quote_asset,
                    }
                ]
            }
        }

        # Mock the API call
        url = self.trading_rules_url
        mock_api.post(url, body=json.dumps(mocked_response))

        # Set _instrument_ticker with both instrument types
        self.exchange._instrument_ticker = mocked_response["result"]["instruments"]
        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        # Only perp instrument should be in trading rules (option filtered out by line 804)
        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

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
    async def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        await asyncio.sleep(0.00001)
        await request_sent_event.wait()

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
                f"at {Decimal('10000.00')}."
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
                f"at {Decimal('10000.00')}."
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
                f"at {Decimal('10000.00')}."
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
                f"at {Decimal('10000.00')}."
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
        # _all_trade_updates_for_order returns the updates for the caller to apply; that is the
        # contract ExchangePyBase._update_orders_fills relies on. It used to apply them itself
        # and return None, which made that caller raise TypeError and drop every fill.
        trade_updates = await self.exchange._all_trade_updates_for_order(order)
        self.assertEqual(1, len(trade_updates))
        for trade_update in trade_updates:
            self.exchange._order_tracker.process_trade_update(trade_update)

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
        self.assertEqual(int(self.subacct_id), request_params["subaccount_id"])

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
    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
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
        await asyncio.sleep(0.00001)
        await request_sent_event.wait()

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

    @aioresponses()
    def test_make_trading_rules_request(self, mock_api):
        """Trading rules come from the paged instrument fetch, in the v3 {instruments, pagination} shape."""
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "result": {
                "pagination": {"num_pages": 1, "count": 1},
                "instruments": [
                    {
                        "instrument_type": "perp",
                        "instrument_name": f"{self.base_asset}-PERP",
                        "tick_size": "0.01",
                        "minimum_amount": "0.1",
                        "maximum_amount": "1000",
                        "amount_step": "0.01",
                        "base_currency": self.base_asset,
                        "quote_currency": "USDC",
                        "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",  # noqa: mock
                        "base_asset_sub_id": "0",
                    }
                ]
            }
        }

        mock_api.post(regex_url, body=json.dumps(response))
        result = self.async_run_with_timeout(self.exchange._make_trading_rules_request())

        self.assertEqual(response["result"]["instruments"], result)

    @aioresponses()
    def test_get_all_pairs_prices_with_empty_instrument_ticker(self, mock_api):
        """Test get_all_pairs_prices when _instrument_ticker is empty to cover line 187"""
        self.exchange._instrument_ticker = []

        # Mock _make_trading_pairs_request
        pairs_url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        pairs_regex = re.compile(f"^{pairs_url}".replace(".", r"\.").replace("?", r"\?"))

        pairs_response = {
            "result": {
                "instruments": [
                    {
                        "instrument_name": f"{self.base_asset}-PERP",
                        "instrument_type": "perp",
                    }
                ]
            }
        }
        mock_api.post(pairs_regex, body=json.dumps(pairs_response))

        # Mock ticker price requests
        ticker_url = web_utils.private_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        ticker_regex = re.compile(f"^{ticker_url}".replace(".", r"\.").replace("?", r"\?"))

        ticker_response = {
            "result": {
                "instrument_name": f"{self.base_asset}-PERP",
                "best_bid_price": "10000",
                "best_ask_price": "10001",
            }
        }
        mock_api.post(ticker_regex, body=json.dumps(ticker_response))

        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())

        self.assertEqual(1, len(result))
        self.assertEqual(f"{self.base_asset}-PERP", result[0]["symbol"]["instrument_name"])

    @aioresponses()
    def test_place_order_with_empty_instrument_ticker(self, mock_api):
        """Test _place_order when _instrument_ticker is empty to cover line 475"""
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._instrument_ticker = []

        # Mock _make_trading_pairs_request
        pairs_url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        pairs_regex = re.compile(f"^{pairs_url}".replace(".", r"\.").replace("?", r"\?"))

        pairs_response = {
            "result": {
                "instruments": [
                    {
                        "instrument_name": f"{self.base_asset}-PERP",
                        "instrument_type": "perp",
                        "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",
                        "base_asset_sub_id": "0",
                    }
                ]
            }
        }
        mock_api.post(pairs_regex, body=json.dumps(pairs_response))

        # Mock order creation
        url = self.order_creation_url
        creation_response = self.order_creation_request_successful_mock_response
        mock_api.post(url, body=json.dumps(creation_response))

        order_id = self.place_buy_order()
        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("10000"),
            position_action=PositionAction.OPEN,
        ))

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))

    @aioresponses()
    def test_get_last_traded_price(self, mock_api):
        """Test _get_last_traded_price to cover line 918"""
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "result": {
                "instrument_name": f"{self.base_asset}-PERP",
                "M": "10500.50",
            }
        }

        mock_api.post(regex_url, body=json.dumps(response))

        price = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))

        self.assertEqual(float(response["result"]["M"]), price)

    @aioresponses()
    async def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        """
        Overrides the base test only to give the order a PositionAction.

        Fills take their position action from the order rather than from the fill direction, and
        the base helper starts tracking without one, leaving it PositionAction.NIL. A perpetual
        order always carries OPEN or CLOSE in practice, so NIL would exercise a state the
        connector never actually sees.
        """
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
            await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)

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
            self.configure_full_fill_trade_response(order=order, mock_api=mock_api)

        try:
            await self.exchange._user_stream_event_listener()
        except asyncio.CancelledError:
            pass
        await order.wait_until_completely_filled()
        await asyncio.sleep(0.1)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    def test_closing_fills_keep_the_orders_position_action(self):
        """
        The fill's direction always matches the order's trade type, so deriving the position
        action from it is tautological: it classified everything CLOSE while the comparison was
        against a string, and everything OPEN once that was fixed. A SELL that closes a long has
        to stay CLOSE, and take DeductedFromReturns rather than opening-fee treatment.
        """
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID-CLOSE",
            exchange_order_id="EX-CLOSE",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.CLOSE,
        )
        order = self.exchange.in_flight_orders["OID-CLOSE"]

        fill = {
            "order_id": "EX-CLOSE",
            "instrument_name": f"{self.base_asset}-PERP",
            "direction": "sell",
            "trade_id": "TID-CLOSE",
            "trade_price": "10000",
            "trade_amount": "1",
            "trade_fee": "0.1",
            "timestamp": 1640780000000,
        }

        self.async_run_with_timeout(
            self.exchange._process_trade_rs_event_message(
                order_fill=fill,
                all_fillable_order={"EX-CLOSE": order},
            )
        )

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(PositionAction.CLOSE.value, fill_event.position)
        self.assertIsInstance(fill_event.trade_fee, DeductedFromReturnsTradeFee)

    def _private_url(self, path_url: str) -> re.Pattern:
        return re.compile("^" + re.escape(web_utils.private_rest_url(path_url, domain=self.exchange._domain)))

    def _sent_body(self, mock_api: aioresponses, url, index: int = 0) -> Dict[str, Any]:
        return json.loads(self._all_executed_requests(mock_api, url)[index].kwargs["data"])

    @aioresponses()
    def test_request_bodies_carry_the_subaccount_id_as_an_integer(self, mock_api):
        """
        Credentials reach the connector as strings, which is how this fixture builds it. v3
        declares the subaccount id an integer and most routes hold to it - public/get_trade_history
        answers the string with -32602 "invalid type: string, expected i64" - so every private
        request body has to carry the integer, the balance poll first among them.
        """
        self.assertIsInstance(self.subacct_id, str)
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID-TYPE",
            exchange_order_id="EX-TYPE",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID-TYPE"]

        urls = {
            "balances": self._private_url(CONSTANTS.ACCOUNTS_PATH_URL),
            "positions": self._private_url(CONSTANTS.POSITION_INFORMATION_URL),
            "order status": self._private_url(CONSTANTS.ORDER_STATUS_PATH_URL),
            "funding history": self._private_url(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL),
        }
        mock_api.post(urls["balances"], body=json.dumps(self.balance_request_mock_response_for_base_and_quote))
        mock_api.post(urls["positions"], body=json.dumps(self._get_position_risk_api_endpoint_single_position_list()))
        mock_api.post(urls["order status"], body=json.dumps(self._order_status_request_open_mock_response(order)))
        mock_api.post(urls["funding history"], body=json.dumps(self._get_income_history_dict()))
        mock_api.post(self.funding_info_url, body=json.dumps(self._get_funding_info_dict()))

        self.async_run_with_timeout(self.exchange._update_balances())
        self.async_run_with_timeout(self.exchange._update_positions())
        self.async_run_with_timeout(self.exchange._request_order_status(order))
        self.async_run_with_timeout(self.exchange._fetch_last_fee_payment(self.trading_pair))

        for name, url in urls.items():
            sent = self._sent_body(mock_api, url)["subaccount_id"]
            self.assertEqual(45686, sent, name)
            self.assertIs(int, type(sent), name)

    @aioresponses()
    def test_reduce_only_is_sent_only_where_v3_accepts_it(self, mock_api):
        """
        reduce_only is "supported only for market orders and non-resting limit orders (ioc or
        fok)". On an order that can rest it is refused with 11024, so setting it on every close
        would have rejected every GTC and post-only close - a take-profit limit, for one.
        """
        self._simulate_trading_rules_initialized()
        cases = [
            (OrderType.MARKET, PositionAction.CLOSE, True),
            (OrderType.LIMIT, PositionAction.CLOSE, False),
            (OrderType.LIMIT_MAKER, PositionAction.CLOSE, False),
            (OrderType.MARKET, PositionAction.OPEN, False),
            (OrderType.LIMIT, PositionAction.OPEN, False),
        ]
        url = self.order_creation_url
        for index, (order_type, position_action, _) in enumerate(cases):
            mock_api.post(url, body=json.dumps(self.order_creation_request_successful_mock_response))
            self.async_run_with_timeout(self.exchange._place_order(
                order_id=f"0x{index:032x}",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.SELL,
                order_type=order_type,
                price=Decimal("10000"),
                position_action=position_action,
            ))

        self.assertEqual(len(cases), len(self._all_executed_requests(mock_api, url)))
        for index, (order_type, position_action, expected) in enumerate(cases):
            sent = self._sent_body(mock_api, url, index)
            self.assertIs(expected, sent["reduce_only"], f"{order_type.name} {position_action.name}")
            # Never alongside a time in force that lets the order rest.
            if sent["reduce_only"]:
                self.assertNotIn(sent["time_in_force"], CONSTANTS.RESTING_TIME_IN_FORCE)

    @aioresponses()
    def test_resting_orders_are_signed_to_live_until_filled_or_cancelled(self, mock_api):
        """
        "Orders always expire at signature_expiry_sec regardless of time-in-force." Signing every
        order for an hour pulled each resting order from the book an hour after it was placed.
        """
        self._simulate_trading_rules_initialized()
        cases = [
            (OrderType.LIMIT, RESTING_ORDER_VALIDITY_SEC),
            (OrderType.LIMIT_MAKER, RESTING_ORDER_VALIDITY_SEC),
            (OrderType.MARKET, CONSTANTS.SIGNATURE_VALIDITY_SEC),
        ]
        url = self.order_creation_url
        placed_at = time.time()
        for index, (order_type, _) in enumerate(cases):
            mock_api.post(url, body=json.dumps(self.order_creation_request_successful_mock_response))
            self.async_run_with_timeout(self.exchange._place_order(
                order_id=f"0x{index:032x}",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=order_type,
                price=Decimal("10000"),
                position_action=PositionAction.OPEN,
            ))

        for index, (order_type, expected_validity) in enumerate(cases):
            sent = self._sent_body(mock_api, url, index)
            self.assertAlmostEqual(
                expected_validity, sent["signature_expiry_sec"] - placed_at, delta=30, msg=order_type.name
            )

    @aioresponses()
    def test_position_without_a_leverage_figure_does_not_break_the_poll(self, req_mock):
        """
        leverage is nullable and optional in the v3 Position schema. A null used to reach
        Decimal(None) and take the whole positions poll down with a TypeError.
        """
        self._simulate_trading_rules_initialized()
        url = self._private_url(CONSTANTS.POSITION_INFORMATION_URL)

        for variant in ("null", "absent"):
            positions = self._get_position_risk_api_endpoint_single_position_list()
            if variant == "null":
                positions["result"]["positions"][0]["leverage"] = None
            else:
                del positions["result"]["positions"][0]["leverage"]
            req_mock.post(url, body=json.dumps(positions))
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, 7)

            self.async_run_with_timeout(self.exchange._update_positions())

            position = list(self.exchange.account_positions.values())[0]
            # The figure already held is kept rather than replaced with a meaningless zero.
            self.assertEqual(Decimal("7"), position.leverage, variant)
            self.assertEqual(7, self.exchange._perpetual_trading.get_leverage(self.trading_pair), variant)

        # A figure the exchange does report still takes precedence.
        req_mock.post(url, body=json.dumps(self._get_position_risk_api_endpoint_single_position_list()))
        self.async_run_with_timeout(self.exchange._update_positions())
        position = list(self.exchange.account_positions.values())[0]
        self.assertEqual(Decimal("25"), position.leverage)
        self.assertEqual(25, self.exchange._perpetual_trading.get_leverage(self.trading_pair))

    @aioresponses()
    def test_last_fee_payment_takes_the_latest_event_and_sends_only_v3_parameters(self, req_mock):
        self._simulate_trading_rules_initialized()
        income_history = self._get_income_history_dict()
        latest = income_history["result"]["events"][0]
        older = dict(latest, timestamp=latest["timestamp"] - 3_600_000, funding="0.5")
        # Oldest first: the order is not specified, so the first entry cannot be assumed latest.
        income_history["result"]["events"] = [older, latest]
        url = self._private_url(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)
        req_mock.post(url, body=json.dumps(income_history))
        req_mock.post(self.funding_info_url, body=json.dumps(self._get_funding_info_dict()))

        timestamp, _, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair)
        )

        self.assertEqual(Decimal(latest["funding"]), payment)
        self.assertEqual(latest["timestamp"] * 1e-3, timestamp)
        # "period" was a v2 parameter; v3's private/get_funding_history does not define it.
        self.assertEqual(
            {"page", "page_size", "start_timestamp", "instrument_name", "subaccount_id"},
            set(self._sent_body(req_mock, url)),
        )

    def _use_session_key(self, address: str = "0xSESSIONKEY") -> None:
        self.exchange._trading_required = True
        self.exchange._auth.session_key_wallet = MagicMock()
        self.exchange._auth.session_key_wallet.address = address

    def test_session_key_expiry_is_read_so_orders_cannot_outlive_the_key(self) -> None:
        """
        Resting orders are signed for as long as the API allows, and an action that outlives its
        key is refused with 14038 - so the key's own expiry has to be known before signing.
        """
        self._use_session_key()
        self.exchange._api_post = AsyncMock(side_effect=[
            {"result": {"wallets": [self.wallet_address]}},
            {"result": {"public_session_keys": [
                {"public_session_key": "0xANOTHERKEY", "expiry_sec": 1},
                {"public_session_key": "0xsessionkey", "expiry_sec": 1893456000},  # case differs
            ]}},
        ])

        self.async_run_with_timeout(self.exchange._verify_session_key())

        self.assertEqual(1893456000, self.exchange._auth.session_key_expiry_sec)
        lookup = self.exchange._api_post.call_args_list[1].kwargs
        self.assertEqual(CONSTANTS.SESSION_KEYS_PATH_URL, lookup["path_url"])
        self.assertEqual({"wallet": self.wallet_address}, lookup["data"])
        self.assertTrue(lookup["is_auth_required"])
        self.assertEqual([], [r for r in self.log_records if r.levelname == "ERROR"])

    def test_unreadable_session_key_expiry_does_not_stop_the_connector(self) -> None:
        unreadable = [
            IOError("connection reset"),
            {"error": {"code": 14031, "message": "Unauthorized Key Scope"}},
            {"result": {"public_session_keys": []}},
            {"result": {"public_session_keys": [{"public_session_key": "0xSESSIONKEY"}]}},
        ]
        for response in unreadable:
            self._use_session_key()
            self.exchange._api_post = AsyncMock(side_effect=[
                {"result": {"wallets": [self.wallet_address]}},
                response,
            ])

            self.async_run_with_timeout(self.exchange._verify_session_key())

            self.assertIsNone(self.exchange._auth.session_key_expiry_sec, response)
        self.assertEqual([], [r for r in self.log_records if r.levelname == "ERROR"])

    def test_owner_wallet_signing_for_itself_is_not_looked_up_as_a_session_key(self) -> None:
        """
        Signing with the owner wallet is valid and involves no session key. Looking the wallet up
        as one reported a correctly configured account as "session key not found".
        """
        self._use_session_key(self.wallet_address.upper().replace("0X", "0x"))
        self.exchange._api_post = AsyncMock()

        self.async_run_with_timeout(self.exchange._verify_session_key())

        self.exchange._api_post.assert_not_called()
        self.assertEqual([], [r for r in self.log_records if r.levelname == "ERROR"])

    def test_session_key_registered_to_another_wallet_names_both(self) -> None:
        """The commonest setup mistake: entering the session key's own address as the wallet."""
        self._use_session_key()
        self.exchange._api_post = AsyncMock(return_value={"result": {"wallets": ["0xTHEREALWALLET"]}})

        self.async_run_with_timeout(self.exchange._verify_session_key())

        logged = [r.getMessage() for r in self.log_records if r.levelname == "ERROR"]
        self.assertTrue(any("registered to 0xtherealwallet" in m for m in logged), logged)
        self.assertTrue(any(self.wallet_address in m for m in logged), logged)
        # The expiry of a key that does not belong to this wallet is not asked for.
        self.assertEqual(1, self.exchange._api_post.call_count)

    def test_max_fee_is_costed_off_the_index_price(self):
        """
        The engine costs the fee off max(limit price, index price). The connector used the local
        order book mid in place of the index, which on a book with no orders does not exist - so
        a bid below the market was costed off its own limit price and signed under the intended
        headroom.
        """
        self._simulate_trading_rules_initialized()
        instrument = {"taker_fee_rate": "0.0003", "maker_fee_rate": "0.0001", "base_fee": "0.01", "amount_step": "0.1"}
        limit_price = Decimal("50")

        def max_fee():
            return self.exchange._estimate_order_max_fee(
                instrument=instrument, trading_pair=self.trading_pair, limit_price=limit_price
            )

        def expected(reference_price):
            # The rate term off the reference price, plus the base fee over one amount step.
            return 3 * 2 * Decimal("0.0003") * Decimal(reference_price) + Decimal("0.01") / Decimal("0.1")

        # No funding info and no order book: only the limit price is left to go on.
        self.assertEqual(expected(50), max_fee())

        # A local mid, but still no funding info: the mid stands in.
        with patch.object(DerivePerpetualDerivative, "get_mid_price", return_value=Decimal("90")):
            self.assertEqual(expected(90), max_fee())

            # Once the index is known it is what the fee is costed off, not the mid.
            self.exchange._perpetual_trading._funding_info[self.trading_pair] = MagicMock(index_price=Decimal("100"))
            self.assertEqual(expected(100), max_fee())

        # The index alone is enough: an empty book no longer drops the cap to the limit price.
        self.assertEqual(expected(100), max_fee())

        # An index that has not been populated yet is not trusted.
        for unusable in (Decimal("0"), Decimal("NaN"), None, "not a number"):
            self.exchange._perpetual_trading._funding_info[self.trading_pair] = MagicMock(index_price=unusable)
            self.assertEqual(expected(50), max_fee(), unusable)

    @aioresponses()
    def test_post_only_orders_are_signed_without_the_base_fee_term(self, mock_api):
        """
        The exchange's own suggested cap adds base_fee / amount_step to any order that can take
        and nothing to a post-only one, which never pays the base fee.
        """
        self._simulate_trading_rules_initialized()
        instrument = self.exchange._instrument_ticker[0]
        url = self.order_creation_url
        for index, order_type in enumerate((OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET)):
            mock_api.post(url, body=json.dumps(self.order_creation_request_successful_mock_response))
            self.async_run_with_timeout(self.exchange._place_order(
                order_id=f"0x{index:032x}",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=order_type,
                price=Decimal("10000"),
                position_action=PositionAction.OPEN,
            ))
        limit, post_only, market = (Decimal(self._sent_body(mock_api, url, i)["max_fee"]) for i in range(3))

        base_fee_over_one_step = Decimal(instrument["base_fee"]) / Decimal(instrument["amount_step"])
        self.assertEqual(base_fee_over_one_step, limit - post_only)
        self.assertEqual(limit, market)
        self.assertEqual(
            3 * 2 * Decimal(instrument["taker_fee_rate"]) * Decimal("10000"), post_only
        )

    def _track_order(self, order_id: str = "OID-ERR", exchange_order_id: str = "EX-ERR") -> InFlightOrder:
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        return self.exchange.in_flight_orders[order_id]

    def test_order_status_error_other_than_not_found_keeps_the_order(self):
        """
        The base class counts every error raised from the status poll as "order not found" and
        retires the order after a few. A rate limit or a backend hiccup must not do that, so
        the order is reported in the state it is already tracked in.
        """
        order = self._track_order()
        for error in (
            {"code": -32000, "message": "Rate limit exceeded"},
            {"code": 9002, "message": "Backend temporarily unavailable, retry"},
        ):
            self.exchange._api_post = AsyncMock(return_value={"error": error})

            update = self.async_run_with_timeout(self.exchange._request_order_status(order))

            self.assertEqual(order.current_state, update.new_state, error)
            self.assertEqual(order.client_order_id, update.client_order_id)
            self.assertEqual(order.exchange_order_id, update.exchange_order_id)
        warnings = [r.getMessage() for r in self.log_records if r.levelname == "WARNING"]
        self.assertTrue(any("code=-32000 Rate limit exceeded" in m for m in warnings), warnings)

    def test_order_status_not_found_is_raised_with_its_code(self):
        order = self._track_order()
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 11006, "message": "Does not exist"}})

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._request_order_status(order))

        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(context.exception))

    def test_order_status_the_connector_does_not_map_keeps_the_order(self):
        order = self._track_order()
        self.exchange._api_post = AsyncMock(return_value={"result": {
            "order_status": "a_status_added_later",
            "last_update_timestamp": 1640780000000,
            "order_id": "EX-ERR",
            "label": "",
        }})

        update = self.async_run_with_timeout(self.exchange._request_order_status(order))

        self.assertEqual(order.current_state, update.new_state)
        # An empty label falls back to the id the order is tracked under.
        self.assertEqual(order.client_order_id, update.client_order_id)

    def test_order_rejections_are_reported_by_code(self):
        """
        Rejections used to be recognised by matching the message text and reading error["data"],
        which is optional: an error without it surfaced as a KeyError instead of the rejection.
        """
        self._simulate_trading_rules_initialized()
        cases = [
            ({"code": 11007, "message": "Self-crossing disallowed"}, "would have crossed one of this account's own orders"),
            ({"code": 11008, "message": "Post only order cannot cross the market"}, "would have crossed the book"),
            ({"code": 11023, "message": "Max fee order param is too low"}, "the signed max_fee was below the fee"),
            ({"code": 14031, "message": "Unauthorized Key Scope"}, "Derive session key error 14031"),
            ({"code": 11000, "message": "Insufficient funds"}, "code=11000 Insufficient funds"),
        ]
        for error, expected in cases:
            self.log_records.clear()
            self.exchange._api_post = AsyncMock(return_value={"error": error})

            with self.assertRaises(IOError) as context:
                self.async_run_with_timeout(self.exchange._place_order(
                    order_id="0xabc",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("10000"),
                    position_action=PositionAction.OPEN,
                ))

            reported = str(context.exception) + " " + " ".join(r.getMessage() for r in self.log_records)
            self.assertIn(expected, reported, error)
            self.assertIn("Error submitting order 0xabc", str(context.exception))

    def test_cancel_errors_carry_the_code_and_only_not_found_counts_as_gone(self):
        self._simulate_trading_rules_initialized()
        order = self._track_order()

        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 11006, "message": "Does not exist"}})
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._place_cancel(order.client_order_id, order))
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(context.exception))

        self.exchange._api_post = AsyncMock(return_value={"error": {"code": -32000, "message": "Rate limit exceeded"}})
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._place_cancel(order.client_order_id, order))
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(context.exception))
        self.assertEqual("code=-32000 Rate limit exceeded", str(context.exception))

    def test_positions_and_funding_report_the_exchange_error(self):
        """
        The positions poll used to return quietly on an API error, leaving the connector
        reporting whatever it last saw; the funding lookup died with a bare KeyError.
        """
        self._simulate_trading_rules_initialized()
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 14030, "message": "Session key expired"}})

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._update_positions())
        self.assertIn("Derive session key error 14030", str(context.exception))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._fetch_last_fee_payment(self.trading_pair))
        self.assertIn("code=14030 Session key expired", str(context.exception))

    def test_balance_error_names_the_cause_and_assets_no_longer_held_are_dropped(self):
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 14026, "message": "Session key not found"}})
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._update_balances())
        self.assertIn("code=14026", str(context.exception))
        errors = [r.getMessage() for r in self.log_records if r.levelname == "ERROR"]
        self.assertTrue(any("Derive session key error 14026" in m for m in errors), errors)

        # The owner wallet's own key skips the session-key lookup, so a wallet with no account on
        # this network comes back as 14000. `connect` shows only the exception text, so the
        # explanation has to be in it.
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 14000, "message": "Account not found"}})
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._update_balances())
        self.assertIn("code=14000 Account not found. Derive account error 14000", str(context.exception))
        self.assertIn("Mainnet and testnet accounts are separate", str(context.exception))
        self.assertIn("first deposit", str(context.exception))

        self.exchange._account_balances["OLD"] = Decimal("1")
        self.exchange._account_available_balances["OLD"] = Decimal("1")
        self.exchange._api_post = AsyncMock(return_value={"result": {"collaterals": [{"asset_name": "USDC", "amount": "15"}]}})

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertNotIn("OLD", self.exchange._account_balances)
        self.assertNotIn("OLD", self.exchange._account_available_balances)
        self.assertEqual(Decimal("15"), self.exchange._account_balances["USDC"])

    def test_trading_fees_come_from_the_instrument_definitions(self):
        self._simulate_trading_rules_initialized()
        instrument = self.exchange._instrument_ticker[0]
        # An instrument with no rates published, and one this connector has no pair for.
        self.exchange._instrument_ticker = [
            instrument,
            dict(instrument, instrument_name="NORATES-PERP", maker_fee_rate=None),
            dict(instrument, instrument_name="UNMAPPED-PERP"),
        ]

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        fees = self.exchange._trading_fees[self.trading_pair]
        self.assertEqual(Decimal(instrument["maker_fee_rate"]), fees.maker_percent_fee_decimal)
        self.assertEqual(Decimal(instrument["taker_fee_rate"]), fees.taker_percent_fee_decimal)
        self.assertEqual([self.trading_pair], list(self.exchange._trading_fees))

    def test_leverage_cannot_be_set_and_the_instrument_ceiling_is_reported(self):
        self._simulate_trading_rules_initialized()
        self.assertIsNone(self.exchange.get_max_leverage(self.trading_pair))      # not published for this fixture
        self.assertIsNone(self.exchange.get_max_leverage("NOT-LISTED"))
        self.assertIsNone(self.exchange.get_max_leverage("malformed"))

        self.exchange._instrument_ticker[0]["perp_details"]["srm_perp_margin_requirements"] = {
            "im_perp_req": "0.066", "mm_perp_req": "0.05", "max_leverage": "15.15",
        }
        self.assertEqual(Decimal("15.15"), self.exchange.get_max_leverage(self.trading_pair))

        success, message = self.async_run_with_timeout(self.exchange._set_trading_pair_leverage(self.trading_pair, 20))

        # Reporting success would have the base class cache 20x as if the exchange had applied it.
        self.assertFalse(success)
        self.assertIn("the requested 20x was not applied", message)
        self.assertIn(f"The maximum for {self.trading_pair} is 15.15x", message)

    def test_market_orders_are_priced_through_the_mid(self):
        """
        Priced at the bare mid, an IOC market order cannot cross the spread: it is refused with
        11009 "no liquidity within the limit price". A limit beyond the exchange's price band is
        accepted and simply fills at the book, so the buffer does not need to stay inside it.
        """
        self._simulate_trading_rules_initialized()
        with patch.object(DerivePerpetualDerivative, "get_mid_price", return_value=Decimal("10000")), \
                patch.object(DerivePerpetualDerivative, "_create_order", new_callable=AsyncMock) as create_order:
            self.exchange.buy(self.trading_pair, Decimal("1"), OrderType.MARKET)
            self.exchange.sell(self.trading_pair, Decimal("1"), OrderType.MARKET)
            self.async_run_with_timeout(asyncio.sleep(0.01))

        buy, sell = (call.kwargs for call in create_order.call_args_list)
        self.assertEqual(Decimal("10500"), buy["price"])
        self.assertEqual(Decimal("9500"), sell["price"])
        self.assertEqual(TradeType.BUY, buy["trade_type"])
        self.assertEqual(TradeType.SELL, sell["trade_type"])

    def test_instruments_are_fetched_across_every_page(self):
        first, second = {"instrument_name": "A-PERP"}, {"instrument_name": "B-PERP"}
        self.exchange._api_post = AsyncMock(side_effect=[
            {"result": {"instruments": [first], "pagination": {"num_pages": 2, "count": 2}}},
            {"result": {"instruments": [second], "pagination": {"num_pages": 2, "count": 2}}},
        ])

        instruments = self.async_run_with_timeout(self.exchange._make_trading_pairs_request())

        self.assertEqual([first, second], instruments)
        self.assertEqual([1, 2], [call.kwargs["data"]["page"] for call in self.exchange._api_post.call_args_list])

    def test_session_key_not_registered_is_reported_clearly(self) -> None:
        self._use_session_key()
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 14026, "message": "Session key not found"}})

        self.async_run_with_timeout(self.exchange._verify_session_key())

        errors = [r.getMessage() for r in self.log_records if r.levelname == "ERROR"]
        self.assertTrue(any(m.startswith("Derive session key error 14026: The session key is not registered") for m in errors), errors)
        self.assertTrue(any("your own EOA or multisig" in m for m in errors), errors)
        self.assertIsNone(self.exchange._auth.session_key_expiry_sec)

    def test_session_key_check_does_not_stop_the_connector_when_it_cannot_run(self) -> None:
        # Not trading: nothing to verify.
        self.exchange._trading_required = False
        self.exchange._api_post = AsyncMock()
        self.async_run_with_timeout(self.exchange._verify_session_key())
        self.exchange._api_post.assert_not_called()

        # The lookup itself failing, an error with no hint for its code, and an empty answer.
        for response in (IOError("connection reset"), {"error": {"code": -32603, "message": "Internal error"}}, {"result": {"wallets": []}}):
            self._use_session_key()
            self.exchange._api_post = AsyncMock(side_effect=[response])
            self.async_run_with_timeout(self.exchange._verify_session_key())
            self.assertEqual(1, self.exchange._api_post.call_count)
        errors = [r.getMessage() for r in self.log_records if r.levelname == "ERROR"]
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Derive rejected the session key", errors[0])

    def test_session_key_expiry_lookup_can_be_cancelled(self) -> None:
        self.exchange._api_post = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._update_session_key_expiry("0xSESSIONKEY"))

    @aioresponses()
    def test_position_changes_from_the_user_stream_update_the_tracked_position(self, req_mock):
        self._simulate_trading_rules_initialized()
        req_mock.post(self._private_url(CONSTANTS.POSITION_INFORMATION_URL),
                      body=json.dumps(self._get_position_risk_api_endpoint_single_position_list()))
        self.async_run_with_timeout(self.exchange._update_positions())
        position = list(self.exchange.account_positions.values())[0]
        self.assertEqual(Decimal("5"), position.amount)

        update = {"instrument_name": self.exchange_trading_pair, "amount": "2", "average_price": "100", "unrealized_pnl": "1.5"}
        self.async_run_with_timeout(self.exchange._process_update_positions({"positions": [update]}))

        self.assertEqual(Decimal("2"), position.amount)
        self.assertEqual(Decimal("100"), position.entry_price)       # the average price, not the index
        self.assertEqual(Decimal("1.5"), position.unrealized_pnl)

        self.async_run_with_timeout(self.exchange._process_update_positions({"positions": [dict(update, amount="0")]}))
        self.assertEqual(0, len(self.exchange.account_positions))

    def test_cancel_of_a_missing_order_is_counted_as_not_found_once(self):
        """
        The base class counts the order as not found when it recognises the code in the error.
        _place_cancel used to count it as well, so every such cancel counted twice and the order
        was written off after two attempts instead of the four the tracker allows.
        """
        self._simulate_trading_rules_initialized()
        order = self._track_order()
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 11006, "message": "Does not exist"}})
        limit = self.exchange._order_tracker.lost_order_count_limit

        self.async_run_with_timeout(self.exchange._execute_order_cancel(order))
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

        for _ in range(limit - 1):
            self.async_run_with_timeout(self.exchange._execute_order_cancel(order))
        self.assertEqual(limit, self.exchange._order_tracker._order_not_found_records[order.client_order_id])
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_order_refused_for_outliving_the_session_key_is_signed_again(self, mock_api):
        """
        The key's expiry is read once at startup. If that lookup failed, resting orders are signed
        for the longest the API allows and a shorter-lived key has every one of them refused with
        14038. The refusal now makes the connector read the expiry and sign the order again.
        """
        self._simulate_trading_rules_initialized()
        self.assertIsNone(self.exchange._auth.session_key_expiry_sec)        # as after a failed lookup
        key_expiry = int(time.time()) + 30 * 24 * 60 * 60
        url = self.order_creation_url
        mock_api.post(url, body=json.dumps({"error": {"code": 14038, "message": "Action expiry exceeds session key expiry"}}))
        mock_api.post(self._private_url(CONSTANTS.SESSION_KEYS_PATH_URL), body=json.dumps({"result": {"public_session_keys": [
            {"public_session_key": self.exchange._auth.session_key_wallet.address, "expiry_sec": key_expiry},
        ]}}))
        mock_api.post(url, body=json.dumps(self.order_creation_request_successful_mock_response))

        exchange_order_id, _ = self.async_run_with_timeout(self.exchange._place_order(
            order_id="0xabc",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10000"),
            position_action=PositionAction.OPEN,
        ))

        first, second = self._sent_body(mock_api, url, 0), self._sent_body(mock_api, url, 1)
        self.assertAlmostEqual(RESTING_ORDER_VALIDITY_SEC, first["signature_expiry_sec"] - time.time(), delta=30)
        self.assertEqual(key_expiry - SESSION_KEY_EXPIRY_MARGIN_SEC, second["signature_expiry_sec"])
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotEqual(first["signature"], second["signature"])
        self.assertEqual(str(self.expected_exchange_order_id), exchange_order_id)
        self.assertEqual(key_expiry, self.exchange._auth.session_key_expiry_sec)

    @aioresponses()
    def test_order_outliving_the_session_key_is_reported_when_the_expiry_cannot_be_read(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = self.order_creation_url
        mock_api.post(url, body=json.dumps({"error": {"code": 14038, "message": "Action expiry exceeds session key expiry"}}))
        mock_api.post(self._private_url(CONSTANTS.SESSION_KEYS_PATH_URL),
                      body=json.dumps({"error": {"code": 14031, "message": "Unauthorized Key Scope"}}))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._place_order(
                order_id="0xabc",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("10000"),
                position_action=PositionAction.OPEN,
            ))

        self.assertIn("Derive session key error 14038", str(context.exception))
        # Sending the same order again would only be refused again, so it is not sent twice.
        self.assertEqual(1, len(self._all_executed_requests(mock_api, url)))
        warnings = [r.getMessage() for r in self.log_records if r.levelname == "WARNING"]
        self.assertTrue(any(
            "Could not read the expiry of the Derive session key (code=14031 Unauthorized Key Scope)" in m for m in warnings
        ), warnings)

    @aioresponses()
    def test_order_outliving_the_session_key_is_not_resent_when_the_expiry_is_unchanged(self, mock_api):
        """Reading the expiry again only helps if it changed; otherwise the refusal would repeat."""
        self._simulate_trading_rules_initialized()
        key_expiry = int(time.time()) + 30 * 24 * 60 * 60
        self.exchange._auth.session_key_expiry_sec = key_expiry
        url = self.order_creation_url
        mock_api.post(url, body=json.dumps({"error": {"code": 14038, "message": "Action expiry exceeds session key expiry"}}))
        mock_api.post(self._private_url(CONSTANTS.SESSION_KEYS_PATH_URL), body=json.dumps({"result": {"public_session_keys": [
            {"public_session_key": self.exchange._auth.session_key_wallet.address, "expiry_sec": key_expiry},
        ]}}))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._place_order(
                order_id="0xabc",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("10000"),
                position_action=PositionAction.OPEN,
            ))

        self.assertIn("Derive session key error 14038", str(context.exception))
        self.assertEqual(1, len(self._all_executed_requests(mock_api, url)))

    def test_closed_position_leaves_once_the_exchange_stops_listing_it(self):
        """
        v3 lists active positions only: on testnet none of 128 listed positions had a zero amount.
        The poll used to return early on an empty list and otherwise only removed a position that
        came back with amount 0, so a position closed in full stayed in the connector.
        """
        self._simulate_trading_rules_initialized()
        self.exchange._api_post = AsyncMock(return_value=self._get_position_risk_api_endpoint_single_position_list())
        for _ in range(2):      # still listed on the second poll, so still held
            self.async_run_with_timeout(self.exchange._update_positions())
            self.assertEqual(1, len(self.exchange.account_positions))

        self.exchange._api_post = AsyncMock(return_value={"result": {"positions": []}})
        self.async_run_with_timeout(self.exchange._update_positions())
        self.assertEqual(0, len(self.exchange.account_positions))

    def test_position_opened_while_the_poll_is_in_flight_is_kept(self):
        self._simulate_trading_rules_initialized()

        async def answer_after_a_position_appears(*args, **kwargs):
            self.exchange._perpetual_trading.set_position("ETH-USDC", MagicMock())
            return {"result": {"positions": []}}

        self.exchange._api_post = AsyncMock(side_effect=answer_after_a_position_appears)
        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(["ETH-USDC"], list(self.exchange.account_positions))

    def test_overlapping_position_polls_are_applied_in_the_order_they_were_made(self):
        """
        The status poll and the user stream both poll positions, so two polls can be in flight at
        once. Applied as they arrived, an older answer that came back late - here one taken while
        the position was closed - removed a position the newer answer had just restored.
        """
        self._simulate_trading_rules_initialized()
        listed = self._get_position_risk_api_endpoint_single_position_list()
        self.exchange._api_post = AsyncMock(return_value=listed)
        self.async_run_with_timeout(self.exchange._update_positions())
        self.assertEqual(1, len(self.exchange.account_positions))

        older_answer_released = asyncio.Event()
        requests = []

        async def answer(*args, **kwargs):
            requests.append(len(requests))
            if len(requests) == 1:
                # The older poll: taken while the position was closed, and answered late.
                await older_answer_released.wait()
                return {"result": {"positions": []}}
            return listed       # the newer poll: the position is open again

        async def overlap():
            self.exchange._api_post = AsyncMock(side_effect=answer)
            older = asyncio.ensure_future(self.exchange._update_positions())
            await asyncio.sleep(0)
            newer = asyncio.ensure_future(self.exchange._update_positions())
            for _ in range(5):
                await asyncio.sleep(0)      # the newer poll would finish here if nothing held it
            older_answer_released.set()
            await asyncio.gather(older, newer)

        self.async_run_with_timeout(overlap())

        self.assertEqual(2, len(requests))
        self.assertEqual(1, len(self.exchange.account_positions))

    def test_resting_close_warns_once_that_it_cannot_be_reduce_only(self):
        """
        reduce_only is refused on an order that can rest, so nothing the connector sends protects a
        limit close from filling after its position has gone. The exposure is stated once.
        """
        self._simulate_trading_rules_initialized()
        self.exchange._api_post = AsyncMock(return_value=self.order_creation_request_successful_mock_response)

        def close(order_type):
            self.async_run_with_timeout(self.exchange._place_order(
                order_id="0xabc",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.SELL,
                order_type=order_type,
                price=Decimal("10000"),
                position_action=PositionAction.CLOSE,
            ))

        def warnings():
            return [r.getMessage() for r in self.log_records if r.levelname == "WARNING" and "is not reduce-only" in r.getMessage()]

        close(OrderType.MARKET)             # reduce-only, so nothing to warn about
        self.assertEqual(0, len(warnings()))
        close(OrderType.LIMIT)
        close(OrderType.LIMIT_MAKER)
        self.assertEqual(1, len(warnings()))

    def test_account_not_found_names_the_wallet_when_the_session_key_address_was_entered(self):
        """
        A session key has an address of its own, and it is easily entered as the wallet address.
        The key then signs as the owner of an account it does not have, so the exchange answers
        14000 and says nothing about session keys. Which wallet the key belongs to is one public
        lookup away, so the error names it.
        """
        # Built as `connect` builds it: trading is not required, so there is no session_key_wallet.
        exchange = DerivePerpetualDerivative(
            session_private_key=self.session_private_key,  # noqa: mock
            derive_perpetual_wallet_address=self.wallet_address,  # noqa: mock
            subacct_id=self.subacct_id,
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        exchange.derive_perpetual_wallet_address = exchange._auth.signer_address
        owner = "0x52908400098527886E0F7030069857D2E4169EE7"  # noqa: mock
        exchange._api_post = AsyncMock(side_effect=[
            {"error": {"code": 14000, "message": "Account not found"}},
            {"result": {"wallets": [owner]}},
        ])

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(exchange._update_balances())

        self.assertIn("code=14000 Account not found. Derive account error 14000", str(context.exception))
        self.assertIn(f"{exchange._auth.signer_address}, is the address of the session key itself", str(context.exception))
        self.assertIn(f"registered to {owner}: enter that as the wallet address", str(context.exception))
        lookup = exchange._api_post.call_args_list[1].kwargs
        self.assertEqual(CONSTANTS.SESSION_KEY_WALLETS_PATH_URL, lookup["path_url"])
        self.assertEqual({"public_session_key": exchange._auth.signer_address}, lookup["data"])
        self.assertNotIn("is_auth_required", lookup)

    def test_account_not_found_keeps_the_general_hint_when_no_wallet_can_be_named(self):
        # The owner's own key, signing for a wallet that has not deposited yet: the address is not
        # a session key, so the general explanation stands.
        self.exchange.derive_perpetual_wallet_address = self.exchange._auth.signer_address
        self.exchange._api_post = AsyncMock(side_effect=[
            {"error": {"code": 14000, "message": "Account not found"}},
            {"error": {"code": 14026, "message": "Session key not found"}},
        ])
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._update_balances())
        self.assertIn("first deposit", str(context.exception))
        self.assertNotIn("session key itself", str(context.exception))

        # The lookup failing is no reason to lose the error it was meant to explain.
        self.exchange._api_post = AsyncMock(side_effect=[
            {"error": {"code": 14000, "message": "Account not found"}},
            IOError("connection reset"),
        ])
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.exchange._update_balances())
        self.assertIn("code=14000 Account not found", str(context.exception))

        # A wallet address that is not the signer's is not this mistake, so nothing is looked up.
        self.exchange.derive_perpetual_wallet_address = self.wallet_address
        self.exchange._api_post = AsyncMock(return_value={"error": {"code": 14000, "message": "Account not found"}})
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.exchange._update_balances())
        self.assertEqual(1, self.exchange._api_post.call_count)
