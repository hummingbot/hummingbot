import asyncio
import functools
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source import (
    BackpackPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import BackpackPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class BackpackPerpetualDerivativeUnitTest(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}_{cls.quote_asset}_PERP"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = BackpackPerpetualDerivative(
            backpack_api_key="testAPIKey",
            backpack_api_secret="sKmC5939f6W9/viyhwyaNHa0f7j5wSMvZsysW5BB9L4=",  # Valid 32-byte Ed25519 key
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        BackpackPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PING_PATH_URL, domain=self.domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BALANCE_PATH_URL, domain=self.domain)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARK_PRICE_PATH_URL, domain=self.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.FUNDING_PAYMENTS_PATH_URL, domain=self.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BackpackPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = [
            {
                'breakEvenPrice': '126.9307',
                'cumulativeFundingPayment': '-0.000105',
                'cumulativeInterest': '0',
                'entryPrice': '126.93',
                'estLiquidationPrice': '0',
                'imf': '0.01',
                'imfFunction': {
                    'base': '0.02',
                    'factor': '0.00006',
                    'type': 'sqrt'
                },
                'markPrice': '121.98',
                'mmf': '0.0135',
                'mmfFunction': {
                    'base': '0.0135',
                    'factor': '0.000036',
                    'type': 'sqrt'
                },
                'netCost': '-1.2697',
                'netExposureNotional': '1.2198',
                'netExposureQuantity': '0.01',
                'netQuantity': '-0.01',
                'pnlRealized': '0.051',
                'pnlUnrealized': '0.0048',
                'positionId': '28563667732',
                'subaccountId': None,
                'symbol': self.symbol,
                'userId': 1905955}
        ]
        return positions

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            'data': {
                'B': '126.97',
                'E': 1769366599828079,
                'M': '120.96',
                'P': '0.0009',
                'Q': '0.01',
                'T': 1769366599828078,
                'b': '126.9307',
                'f': '0.02',
                'i': 28563667732,
                'l': '0',
                'm': '0.0135',
                'n': '1.2096',
                'p': '0.0592',
                'q': '-0.01',
                's': self.symbol
            },
            'stream': 'account.positionUpdate'
        }
        return account_update

    def _get_income_history_dict(self) -> List:
        income_history = [
            {
                'fundingRate': '-0.0000273',
                'intervalEndTimestamp': '2026-01-25T18:00:00',
                'quantity': '-0.000034',
                'subaccountId': 0,
                'symbol': self.symbol,
                'userId': 1905955
            }
        ]
        return income_history

    def _get_funding_info_dict(self) -> Dict[str, Any]:
        funding_info = [{
            "indexPrice": "1000",
            "markPrice": "1001",
            "nextFundingTimestamp": int(self.start_timestamp * 1e3) + 8 * 60 * 60 * 1000,
            "fundingRate": "0.0001"
        }]
        return funding_info

    def _get_exchange_info_mock_response(
            self,
            min_order_size: float = 0.01,
            min_price_increment: float = 0.01,
            min_base_amount_increment: float = 0.01,
    ) -> List[Dict[str, Any]]:
        mocked_exchange_info = [
            {
                'baseSymbol': self.base_asset,
                'createdAt': '2025-01-21T06:34:54.691858',
                'filters': {
                    'price': {
                        'borrowEntryFeeMaxMultiplier': None,
                        'borrowEntryFeeMinMultiplier': None,
                        'maxImpactMultiplier': '1.03',
                        'maxMultiplier': '1.25',
                        'maxPrice': None,
                        'meanMarkPriceBand': {
                            'maxMultiplier': '1.03',
                            'minMultiplier': '0.97'
                        },
                        'meanPremiumBand': None,
                        'minImpactMultiplier': '0.97',
                        'minMultiplier': '0.75',
                        'minPrice': '0.01',
                        'tickSize': str(min_price_increment)
                    },
                    'quantity': {
                        'maxQuantity': None,
                        'minQuantity': str(min_order_size),
                        'stepSize': str(min_base_amount_increment)
                    }
                },
                'fundingInterval': None,
                'fundingRateLowerBound': None,
                'fundingRateUpperBound': None,
                'imfFunction': None,
                'marketType': 'PERP',
                'mmfFunction': None,
                'openInterestLimit': '0',
                'orderBookState': 'Open',
                'positionLimitWeight': None,
                'quoteSymbol': self.quote_asset,
                'symbol': self.symbol,
                'visible': True
            }
        ]
        return mocked_exchange_info

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal("0.01"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.01"),
                min_notional_size=Decimal("0"),
            )
        }

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative._initialize_leverage_if_needed")
    async def test_existing_account_position_detected_on_positions_update(self, req_mock, mock_leverage):
        self._simulate_trading_rules_initialized()
        mock_leverage.return_value = None
        self.exchange._leverage = Decimal("1")
        self.exchange._leverage_initialized = True

        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair, self.trading_pair)

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative._initialize_leverage_if_needed")
    async def test_account_position_updated_on_positions_update(self, req_mock, mock_leverage):
        self._simulate_trading_rules_initialized()
        mock_leverage.return_value = None
        self.exchange._leverage = Decimal("1")
        self.exchange._leverage_initialized = True

        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, Decimal("0.01"))

        positions[0]["netQuantity"] = "2.01"
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, Decimal("2.01"))

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative._initialize_leverage_if_needed")
    async def test_new_account_position_detected_on_positions_update(self, req_mock, mock_leverage):
        self._simulate_trading_rules_initialized()
        mock_leverage.return_value = None
        self.exchange._leverage = Decimal("1")
        self.exchange._leverage_initialized = True

        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps([]))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative._initialize_leverage_if_needed")
    async def test_closed_account_position_removed_on_positions_update(self, req_mock, mock_leverage):
        self._simulate_trading_rules_initialized()
        mock_leverage.return_value = None
        self.exchange._leverage = Decimal("1")
        self.exchange._leverage_initialized = True

        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions[0]["netQuantity"] = "0"
        req_mock.get(regex_url, body=json.dumps(positions))
        await self.exchange._update_positions()

        self.assertEqual(len(self.exchange.account_positions), 0)

    async def test_supported_position_modes(self):
        linear_connector = self.exchange
        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    async def test_set_position_mode_oneway(self):
        self._simulate_trading_rules_initialized()
        self.assertIsNone(self.exchange._position_mode)

        await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)

        self.assertEqual(PositionMode.ONEWAY, self.exchange._position_mode)

    async def test_set_position_mode_hedge_fails(self):
        self.exchange._position_mode = PositionMode.ONEWAY

        await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)

        # Should remain ONEWAY since HEDGE is not supported
        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)
        self.assertTrue(self._is_logged(
            "DEBUG",
            f"Backpack encountered a problem switching position mode to "
            f"{PositionMode.HEDGE} for {self.trading_pair}"
            f" (Backpack only supports the ONEWAY position mode)"
        ))

    async def test_format_trading_rules(self):
        min_order_size = 0.01
        min_price_increment = 0.01
        min_base_amount_increment = 0.01
        mocked_response = self._get_exchange_info_mock_response(
            min_order_size, min_price_increment, min_base_amount_increment
        )
        self._simulate_trading_rules_initialized()
        trading_rules = await self.exchange._format_trading_rules(mocked_response)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(Decimal(str(min_order_size)), trading_rule.min_order_size)
        self.assertEqual(Decimal(str(min_price_increment)), trading_rule.min_price_increment)
        self.assertEqual(Decimal(str(min_base_amount_increment)), trading_rule.min_base_amount_increment)

    async def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("2200123")

        partial_fill = {
            "data": {
                "e": "orderFill",
                "E": 1694687692980000,
                "s": self.symbol,
                "c": order.client_order_id,
                "S": "Bid",
                "X": "PartiallyFilled",
                "i": "8886774",
                "l": "0.1",
                "L": "10000",
                "N": "USDC",
                "n": "20",
                "T": 1694687692980000,
                "t": "1",
            },
            "stream": "account.orderUpdate"
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["data"]["N"], Decimal(partial_fill["data"]["n"]))], fill_event.trade_fee.flat_fees
        )

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative.current_timestamp")
    async def test_update_order_fills_from_trades_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        trades = [{
            "orderId": "8886774",
            "price": "10000",
            "quantity": "0.5",
            "feeSymbol": self.quote_asset,
            "fee": "5",
            "tradeId": "698759",
            "timestamp": "2021-01-01T00:00:01.000Z",
        }]

        url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(trades))

        await self.exchange._update_order_status()

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("2200123" in in_flight_orders)

        self.assertEqual("2200123", in_flight_orders["2200123"].client_order_id)
        self.assertEqual(Decimal("0.5"), in_flight_orders["2200123"].executed_amount_base)

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative."
           "BackpackPerpetualDerivative.current_timestamp")
    async def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = {
            "clientId": "2200123",
            "id": "8886774",
            "status": "PartiallyFilled",
            "createdAt": 1000,
        }

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        # Also mock the trades endpoint
        trades_url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL, domain=self.domain)
        trades_regex_url = re.compile(f"^{trades_url}".replace(".", r"\.").replace("?", r"\?"))
        req_mock.get(trades_regex_url, body=json.dumps([]))

        await self.exchange._update_order_status()
        await asyncio.sleep(0.001)

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("2200123" in in_flight_orders)
        self.assertEqual(OrderState.PARTIALLY_FILLED, in_flight_orders["2200123"].current_state)

    @aioresponses()
    async def test_set_leverage_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        leverage = 5

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Backpack returns 200 with no content
        req_mock.patch(regex_url, status=200, body="")

        success, msg = await self.exchange._set_trading_pair_leverage(trading_pair, leverage)
        self.assertEqual(success, True)
        self.assertEqual(msg, '')

    @aioresponses()
    async def test_set_leverage_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        leverage = 5

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.patch(regex_url, status=400, body="Bad Request")

        success, message = await self.exchange._set_trading_pair_leverage(trading_pair, leverage)
        self.assertEqual(success, False)
        self.assertIn("Error setting leverage", message)

    @aioresponses()
    async def test_fetch_funding_payment_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        income_history = self._get_income_history_dict()

        url = web_utils.private_rest_url(CONSTANTS.FUNDING_PAYMENTS_PATH_URL, domain=self.domain)
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        timestamp, rate, amount = await self.exchange._fetch_last_fee_payment(self.trading_pair)

        self.assertEqual(rate, Decimal(income_history[0]["fundingRate"]))
        self.assertEqual(amount, Decimal(income_history[0]["quantity"]))

    @aioresponses()
    async def test_cancel_all_successful(self, mocked_api):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"status": "Cancelled"}
        mocked_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.assertTrue("2200123" in self.exchange._order_tracker._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = await self.exchange.cancel_all(timeout_seconds=1)

        self.assertEqual(2, len(cancellation_results))

    @aioresponses()
    async def test_cancel_order_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"status": "Cancelled"}
        mock_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("2200123")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("2200123" in self.exchange._order_tracker._in_flight_orders)

        canceled_order_id = await self.exchange._execute_cancel(trading_pair=self.trading_pair, order_id="2200123")
        await asyncio.sleep(0.01)

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual("2200123", canceled_order_id)

    @aioresponses()
    async def test_create_order_successful(self, req_mock):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {
            "createdAt": int(self.start_timestamp * 1e3),
            "status": "New",
            "id": "8886774"
        }
        req_mock.post(regex_url, body=json.dumps(create_response))
        self._simulate_trading_rules_initialized()

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="2200123",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        self.assertTrue("2200123" in self.exchange._order_tracker._in_flight_orders)

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils.get_current_server_time")
    async def test_place_order_manage_server_overloaded_error_unknown_order(self, mock_api, mock_seconds_counter: MagicMock):
        mock_seconds_counter.return_value = 1640780000
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": "SERVICE_UNAVAILABLE", "message": "Unknown error, please check your request or try again later."}

        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)
        self._simulate_trading_rules_initialized()

        o_id, timestamp = await self.exchange._place_order(
            trade_type=TradeType.BUY,
            order_id="2200123",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    async def test_create_order_exception(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        error_response = {"error": "Insufficient balance"}
        req_mock.post(regex_url, body=json.dumps(error_response), status=400)

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="2200123",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        self.assertEqual(1, len(self.exchange._order_tracker.active_orders))
        order = list(self.exchange._order_tracker.active_orders.values())[0]
        await asyncio.sleep(0.01)
        self.assertEqual(OrderState.FAILED, order.current_state)

    async def test_create_order_min_order_size_failure(self):
        self._simulate_trading_rules_initialized()

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="2200123",
            trading_pair=self.trading_pair,
            amount=Decimal("0.001"),  # Below min
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        await asyncio.sleep(0.)
        self.assertEqual(0, len(self.exchange._order_tracker.active_orders))
        self.assertTrue(self._is_logged(
            "INFO",
            "Order 2200123 has failed. Order Update: OrderUpdate(trading_pair='COINALPHA-HBOT', "
            "update_timestamp=1640780000.0, new_state=<OrderState.FAILED: 6>, client_order_id='2200123', "
            "exchange_order_id=None, misc_updates={'error_message': 'Order amount 0.001 is lower than minimum order size 0.01 "
            "for the pair COINALPHA-HBOT. The order will not be created.', 'error_type': 'ValueError'})"
        ))

    async def test_create_order_min_notional_size_failure(self):
        # feature disabled
        pass

    async def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="2200123",
            exchange_order_id="E2200123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("2200123", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative.get_new_numeric_client_order_id")
    async def test_client_order_id_on_order(self, mock_id_get):
        mock_id_get.return_value = 123

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action=PositionAction.NIL,
        )
        expected_client_order_id = "123"

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action=PositionAction.NIL,
        )
        expected_client_order_id = "123"

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    async def test_update_balances(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            self.quote_asset: {
                "available": "100.5",
                "locked": "50.5",
                "staked": "0"
            }
        }

        mock_api.get(regex_url, body=json.dumps(response))
        await self.exchange._update_balances()

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("100.5"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("151"), total_balances[self.quote_asset])

    async def test_user_stream_logs_errors(self):
        mock_user_stream = AsyncMock()
        account_update = self._get_account_update_ws_event_single_position_dict()
        del account_update["data"]["P"]
        mock_user_stream.get.side_effect = functools.partial(
            self._return_calculation_and_set_done_event,
            lambda: account_update
        )

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        # Patch _parse_and_process_order_message to raise an exception
        with patch.object(self.exchange, '_parse_and_process_position_message', side_effect=Exception("Test Error")):
            self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
            await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error in user stream listener loop."))

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils.get_current_server_time")
    async def test_time_synchronizer_related_request_error_detection(self, req_mock, mock_time):
        mock_time.return_value = 1640780000
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        error_response = {"code": "TIMESTAMP_OUT_OF_RANGE", "message": "Timestamp for this request is outside of the recvWindow."}
        req_mock.post(regex_url, body=json.dumps(error_response), status=400)

        self._simulate_trading_rules_initialized()

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="2200123",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
            price=Decimal("10000"))

        self.assertEqual(1, len(self.exchange._order_tracker.active_orders))

    async def test_user_stream_update_for_order_failure(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.NIL,
        )

        # Set the order to OPEN state so it can receive updates
        tracked_order = self.exchange._order_tracker.fetch_order("2200123")
        tracked_order.current_state = OrderState.OPEN

        order_update = {
            "data": {
                "e": "triggerFailed",
                "E": 1694687692980000,
                "s": self.symbol,
                "c": "2200123",
                "S": "Bid",
                "X": "TriggerFailed",
                "i": "8886774",
                "z": "0",
                "T": 1694687692980000,
            },
            "stream": "account.orderUpdate"
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(
            self._return_calculation_and_set_done_event, lambda: order_update
        )

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        # Yield control to allow the event loop to process the order update
        await asyncio.sleep(0)

        # Check that the order failure event was triggered
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual("2200123", failure_event.order_id)

    async def test_property_getters(self):
        """Test simple property getter methods"""
        # Test to_hb_order_type
        self.assertEqual(OrderType.LIMIT, self.exchange.to_hb_order_type("LIMIT"))
        self.assertEqual(OrderType.MARKET, self.exchange.to_hb_order_type("MARKET"))

        # Test name property
        self.assertEqual("backpack_perpetual", self.exchange.name)

        # Test domain property
        self.assertEqual(self.domain, self.exchange.domain)

        # Test client_order_id_max_length
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, self.exchange.client_order_id_max_length)

        # Test client_order_id_prefix
        self.assertEqual(CONSTANTS.HBOT_ORDER_ID_PREFIX, self.exchange.client_order_id_prefix)

        # Test trading_rules_request_path
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_rules_request_path)

        # Test trading_pairs_request_path
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_pairs_request_path)

        # Test check_network_request_path
        self.assertEqual(CONSTANTS.PING_PATH_URL, self.exchange.check_network_request_path)

        # Test is_cancel_request_in_exchange_synchronous
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)

        # Test funding_fee_poll_interval
        self.assertEqual(120, self.exchange.funding_fee_poll_interval)

    async def test_is_order_not_found_during_status_update_error(self):
        """Test detection of order not found error during status update"""
        error_with_code = Exception(f"Error code: {CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE}, message: {CONSTANTS.ORDER_NOT_EXIST_MESSAGE}")
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(error_with_code))

        # Test with different error
        other_error = Exception("Some other error")
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(other_error))

    @aioresponses()
    async def test_place_order_limit_maker_rejection(self, req_mock):
        """Test LIMIT_MAKER order rejection when it would take liquidity"""
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        error_response = {
            "code": "INVALID_ORDER",
            "message": "Order would immediately match and take liquidity"
        }
        req_mock.post(regex_url, body=json.dumps(error_response), status=400)

        with self.assertRaises(ValueError) as context:
            await self.exchange._place_order(
                order_id="2200123",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT_MAKER,
                price=Decimal("10000")
            )

        self.assertIn("LIMIT_MAKER order would immediately match", str(context.exception))

    async def test_position_update_via_websocket(self):
        """Test position update through websocket message"""
        self._simulate_trading_rules_initialized()

        position_update = self._get_account_update_ws_event_single_position_dict()

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(
            self._return_calculation_and_set_done_event, lambda: position_update
        )

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

        # Give time for position processing
        await asyncio.sleep(0.01)

    async def test_order_matching_by_exchange_order_id_fallback(self):
        """Test order matching when client_order_id is missing but exchange_order_id is present"""
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.NIL,
        )

        # Order update without client_order_id ('c' field)
        order_update = {
            "data": {
                "e": "orderAccepted",
                "E": 1694687692980000,
                "s": self.symbol,
                "S": "Bid",
                "X": "New",
                "i": "8886774",  # Only exchange order id
                "T": 1694687692980000,
            },
            "stream": "account.orderUpdate"
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(
            self._return_calculation_and_set_done_event, lambda: order_update
        )

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.local_event_loop.create_task(self.exchange._user_stream_event_listener())
        await self.resume_test_event.wait()

    @aioresponses()
    async def test_update_balances_with_asset_removal(self, mock_api):
        """Test balance update that removes assets no longer present"""
        url = web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # First update with two assets
        response = {
            self.quote_asset: {
                "available": "100.5",
                "locked": "50.5",
                "staked": "0"
            },
            self.base_asset: {
                "available": "200.0",
                "locked": "0",
                "staked": "0"
            }
        }

        mock_api.get(regex_url, body=json.dumps(response))
        await self.exchange._update_balances()

        self.assertIn(self.quote_asset, self.exchange.available_balances)
        self.assertIn(self.base_asset, self.exchange.available_balances)

        # Second update with only one asset (base_asset removed)
        response2 = {
            self.quote_asset: {
                "available": "100.5",
                "locked": "50.5",
                "staked": "0"
            }
        }

        mock_api.get(regex_url, body=json.dumps(response2))
        await self.exchange._update_balances()

        self.assertIn(self.quote_asset, self.exchange.available_balances)
        self.assertNotIn(self.base_asset, self.exchange.available_balances)

    async def test_collateral_token_getters(self):
        """Test buy and sell collateral token getters"""
        self._simulate_trading_rules_initialized()

        # Collateral tokens come from trading rules
        buy_collateral = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral = self.exchange.get_sell_collateral_token(self.trading_pair)

        # Both should return values from trading rules
        self.assertIsNotNone(buy_collateral)
        self.assertIsNotNone(sell_collateral)

    @aioresponses()
    async def test_leverage_initialization_failure(self, req_mock):
        """Test leverage initialization when API call fails"""
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        error_response = {"error": "Unauthorized"}
        req_mock.get(regex_url, body=json.dumps(error_response), status=401)

        with self.assertRaises(Exception):
            await self.exchange._initialize_leverage_if_needed()

        self.assertFalse(self.exchange._leverage_initialized)

    @aioresponses()
    async def test_update_positions_with_leverage_init_failure(self, req_mock):
        """Test position update when leverage initialization fails"""
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        error_response = {"error": "Unauthorized"}
        req_mock.get(regex_url, body=json.dumps(error_response), status=401)

        # Should return early without updating positions
        await self.exchange._update_positions()

        self.assertEqual(0, len(self.exchange.account_positions))

    @aioresponses()
    async def test_fetch_funding_payment_empty_result(self, req_mock):
        """Test funding payment fetch when no payments exist - should return sentinel values gracefully"""
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(CONSTANTS.FUNDING_PAYMENTS_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Empty list response - should be handled gracefully without raising IndexError
        req_mock.get(regex_url, body=json.dumps([]))

        timestamp, rate, amount = await self.exchange._fetch_last_fee_payment(self.trading_pair)

        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("-1"), rate)
        self.assertEqual(Decimal("-1"), amount)

    @aioresponses()
    async def test_initialize_trading_pair_symbols_from_exchange_info(self, req_mock):
        """Test trading pair symbol initialization"""
        exchange_info = self._get_exchange_info_mock_response()

        self.exchange._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        # Check that mapping was created - trading_pair_symbol_map is an async method that returns a dict
        symbol_map = await self.exchange.trading_pair_symbol_map()
        self.assertIsNotNone(symbol_map)
        self.assertIn(self.symbol, symbol_map)

    @aioresponses()
    async def test_get_last_traded_price(self, req_mock):
        """Test fetching last traded price"""
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "lastPrice": "10500.50",
            "symbol": self.symbol
        }

        req_mock.get(regex_url, body=json.dumps(response))

        price = await self.exchange._get_last_traded_price(self.trading_pair)

        self.assertEqual(10500.50, price)

    @aioresponses()
    async def test_cancel_order_false_return_path(self, mock_api):
        """Test cancel order when status is not 'Cancelled'"""
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Response with different status
        cancel_response = {"status": "Failed"}
        mock_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="2200123",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange._order_tracker.fetch_order("2200123")
        result = await self.exchange._place_cancel("2200123", tracked_order)

        self.assertFalse(result)

    async def test_format_trading_rules_with_exception(self):
        """Test trading rules formatting when an exception occurs"""
        # Create malformed exchange info that will cause an exception
        malformed_info = [
            {
                "symbol": self.symbol,
                "baseSymbol": self.base_asset,
                "quoteSymbol": self.quote_asset,
                # Missing 'filters' key - will cause exception
            }
        ]

        trading_rules = await self.exchange._format_trading_rules(malformed_info)

        # Should return empty list when exception occurs
        self.assertEqual(0, len(trading_rules))
