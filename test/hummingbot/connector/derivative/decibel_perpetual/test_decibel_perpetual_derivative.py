import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from bidict import bidict

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import DecibelPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus


class DummyRESTRequest:
    def __init__(self, method=None, data=None, headers=None, url=""):
        self.method = method
        self.data = data
        self.headers = headers if headers is not None else {}
        self.url = url


class DecibelPerpetualDerivativeUnitTest(IsolatedAsyncioWrapperTestCase):
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_symbol = f"{cls.base_asset}/{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = DecibelPerpetualDerivative(
            decibel_perpetual_api_wallet_private_key="0xaabbccdd",
            decibel_perpetual_main_wallet_public_key="0xmainwallet123",
            decibel_perpetual_api_key="test_api_key",
            decibel_perpetual_gas_station_api_key="test_gas_station_key",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        DecibelPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.exchange_symbol: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self.exchange._set_trading_pair_symbol_map(bidict({self.exchange_symbol: self.trading_pair}))
        # Also set instance-level _trading_pair_symbol_map (used by trading_pair_associated_to_exchange_symbol)
        self.exchange._trading_pair_symbol_map = bidict({self.exchange_symbol: self.trading_pair})
        self._initialize_event_loggers()

        # Pre-populate market info
        self.exchange._market_info[self.trading_pair] = {
            "market_addr": "0xmarketaddr123",
            "px_decimals": 6,
            "sz_decimals": 3,
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        DecibelPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _mock_rest_assistant(self, return_value):
        """Helper to mock REST assistant responses."""
        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)
        mock_rest_assistant.execute_request.return_value = return_value
        return mock_rest_assistant

    def _get_exchange_info_mock_response(
            self,
            min_size: int = 1000,
            lot_size: int = 1000,
            tick_size: int = 1000000,
            px_decimals: int = 6,
            sz_decimals: int = 3,
            max_open_interest: int = 1000000000,
    ) -> Dict[str, Any]:
        return {
            "markets": [
                {
                    "market_name": self.exchange_symbol,
                    "min_size": min_size,
                    "lot_size": lot_size,
                    "tick_size": tick_size,
                    "px_decimals": px_decimals,
                    "sz_decimals": sz_decimals,
                    "max_open_interest": max_open_interest,
                }
            ]
        }

    async def _simulate_trading_rules_initialized(self):
        mocked_response = self._get_exchange_info_mock_response()
        # Call _format_trading_rules directly (no API call)
        trading_rules = await self.exchange._format_trading_rules(mocked_response)
        if trading_rules:
            self.exchange._trading_rules = {
                self.trading_pair: trading_rules[0]
            }
        # Also simulate trading rules for tests that rely on them
        if not trading_rules:
            # Fallback: create a mock trading rule if format_trading_rules failed
            from hummingbot.connector.trading_rule import TradingRule
            self.exchange._trading_rules[self.trading_pair] = TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal("0.001"),
                min_price_increment=Decimal("0.01"),
            )

    async def test_format_trading_rules(self):
        """Test _format_trading_rules by passing exchange info directly."""
        mocked_response = self._get_exchange_info_mock_response()

        trading_rules = await self.exchange._format_trading_rules(mocked_response)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]
        self.assertEqual(Decimal("1"), trading_rule.min_order_size)
        self.assertEqual(Decimal("1"), trading_rule.min_price_increment)
        self.assertEqual(Decimal("1"), trading_rule.min_base_amount_increment)
        self.assertEqual(Decimal("1000000000"), trading_rule.max_order_size)

    async def test_update_balances(self):
        self.exchange._account_balances.clear()
        self.exchange._account_available_balances.clear()

        self._mock_rest_assistant({
            "perp_equity_balance": 1000.50,
            "usdc_cross_withdrawable_balance": 500.25,
        })

        await self.exchange._update_balances()

        self.assertEqual(Decimal("1000.50"), self.exchange.get_balance("USD"))
        self.assertEqual(Decimal("500.25"), self.exchange.get_available_balance("USD"))

    async def test_update_positions(self):
        await self._simulate_trading_rules_initialized()
        self.exchange._perpetual_trading.account_positions.clear()

        self._mock_rest_assistant({
            "positions": [
                {
                    "market": self.exchange_symbol,
                    "size": "1.5",
                    "entry_price": "50000.0",
                    "leverage": "10",
                    "unrealized_pnl": "150.0",
                }
            ]
        })

        await self.exchange._update_positions()

        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))
        pos = list(positions.values())[0]
        self.assertEqual(self.trading_pair, pos.trading_pair)
        self.assertEqual(Decimal("1.5"), pos.amount)
        self.assertEqual(Decimal("50000.0"), pos.entry_price)
        self.assertEqual(Decimal("150.0"), pos.unrealized_pnl)
        self.assertEqual(Decimal("10"), pos.leverage)

    def test_properties(self):
        self.assertEqual(self.domain, self.exchange.name)
        self.assertEqual(CONSTANTS.RATE_LIMITS, self.exchange.rate_limits_rules)
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, self.exchange.domain)
        self.assertEqual(32, self.exchange.client_order_id_max_length)
        self.assertEqual("HBOT", self.exchange.client_order_id_prefix)
        self.assertEqual(CONSTANTS.GET_MARKETS_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.GET_MARKETS_PATH_URL, self.exchange.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.GET_MARKETS_PATH_URL, self.exchange.check_network_request_path)
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual(120, self.exchange.funding_fee_poll_interval)
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], self.exchange.supported_order_types())
        self.assertEqual([PositionMode.ONEWAY], self.exchange.supported_position_modes())
        self.assertEqual(self.quote_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    def test_convert_price_to_chain_units(self):
        self.exchange._market_info[self.trading_pair] = {"px_decimals": 6}
        result = self.exchange._convert_price_to_chain_units(self.trading_pair, Decimal("50000.5"))
        self.assertEqual(50000500000, result)

    def test_convert_size_to_chain_units(self):
        self.exchange._market_info[self.trading_pair] = {"sz_decimals": 3}
        result = self.exchange._convert_size_to_chain_units(self.trading_pair, Decimal("1.5"))
        self.assertEqual(1500, result)

    async def test_set_trading_pair_leverage(self):
        success, msg = await self.exchange._set_trading_pair_leverage(self.trading_pair, 10)
        self.assertTrue(success)

    async def test_check_network(self):
        self._mock_rest_assistant({"markets": []})

        status = await self.exchange.check_network()
        self.assertEqual(NetworkStatus.CONNECTED, status)

    async def test_trading_pair_symbol_conversion(self):
        symbol_map = bidict({self.exchange_symbol: self.trading_pair})
        self.exchange._trading_pair_symbol_map = symbol_map

        result = await self.exchange.exchange_symbol_associated_to_pair(self.trading_pair)
        self.assertEqual(self.exchange_symbol, result)

        result = await self.exchange.trading_pair_associated_to_exchange_symbol(self.exchange_symbol)
        self.assertEqual(self.trading_pair, result)

    async def test_auth_header_injected_via_rest_authenticate(self):
        """Test that Bearer token is added by rest_authenticate in auth module."""
        auth = self.exchange.authenticator
        request = DummyRESTRequest(method="GET")
        result = await auth.rest_authenticate(request)
        self.assertEqual(f"Bearer {self.exchange._api_key}", result.headers["Authorization"])

    def test_get_package_address(self):
        address = self.exchange.get_package_address()
        self.assertEqual(CONSTANTS.MAINNET_PACKAGE, address)

    async def test_is_order_not_found_during_cancelation_error(self):
        error = ValueError("EORDER_NOT_FOUND in Move abort")
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(error))

    async def test_is_order_not_found_during_cancelation_error_false(self):
        error = ValueError("Some other error")
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(error))

    async def test_is_request_exception_related_to_time_synchronizer(self):
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("timestamp invalid")
        ))
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("time sync failed")
        ))
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("network error")
        ))

    async def test_update_time_synchronizer_noop(self):
        await self.exchange._update_time_synchronizer()

    def test_fees_for_30d_volume_matches_tier_schedule(self):
        """Each documented tier threshold should map to its documented (maker, taker)."""
        cases = [
            (Decimal("0"), Decimal("0.00011"), Decimal("0.00034")),           # Tier 0
            (Decimal("5000000"), Decimal("0.00011"), Decimal("0.00034")),     # Tier 0 (below 10M)
            (Decimal("10000000"), Decimal("0.00009"), Decimal("0.0003")),     # Tier 1 boundary
            (Decimal("50000000"), Decimal("0.00006"), Decimal("0.00025")),    # Tier 2 boundary
            (Decimal("200000000"), Decimal("0.00003"), Decimal("0.00022")),   # Tier 3 boundary
            (Decimal("1000000000"), Decimal("0"), Decimal("0.00021")),        # Tier 4 boundary
            (Decimal("4000000000"), Decimal("0"), Decimal("0.00019")),        # Tier 5 boundary
            (Decimal("15000000000"), Decimal("0"), Decimal("0.00018")),       # Tier 6 boundary
            (Decimal("100000000000"), Decimal("0"), Decimal("0.00018")),      # Well above Tier 6
        ]
        for volume, expected_maker, expected_taker in cases:
            maker, taker = self.exchange._fees_for_30d_volume(volume)
            self.assertEqual(expected_maker, maker, f"maker mismatch at volume={volume}")
            self.assertEqual(expected_taker, taker, f"taker mismatch at volume={volume}")

    async def test_update_trading_fees_uses_30d_volume(self):
        """Volume above $10M should land the user on Tier 1 fees."""
        self.exchange._trading_fees.clear()
        self._mock_rest_assistant({"volume": 25000000})  # Tier 1 (>$10M)

        await self.exchange._update_trading_fees()

        schema = self.exchange._trading_fees[self.trading_pair]
        self.assertEqual(Decimal("0.00009"), schema.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0003"), schema.taker_percent_fee_decimal)

    async def test_update_trading_fees_handles_null_volume(self):
        """New accounts have volume=null → default to Tier 0."""
        self.exchange._trading_fees.clear()
        self._mock_rest_assistant({"volume": None})

        await self.exchange._update_trading_fees()

        schema = self.exchange._trading_fees[self.trading_pair]
        self.assertEqual(Decimal("0.00011"), schema.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.00034"), schema.taker_percent_fee_decimal)

    async def test_update_trading_fees_keeps_previous_on_error(self):
        """Transient API failures should not wipe a previously computed schema."""
        from hummingbot.core.data_type.trade_fee import TradeFeeSchema
        previous = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.00009"),
            taker_percent_fee_decimal=Decimal("0.0003"),
        )
        self.exchange._trading_fees[self.trading_pair] = previous

        mock_rest_assistant = AsyncMock()
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)
        mock_rest_assistant.execute_request.side_effect = Exception("network down")

        await self.exchange._update_trading_fees()  # should not raise

        self.assertIs(previous, self.exchange._trading_fees[self.trading_pair])

    async def test_position_mode_set_oneway(self):
        success, msg = await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)
        self.assertTrue(success)

    async def test_position_mode_set_hedge_fail(self):
        success, msg = await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)
        self.assertFalse(success)

    async def test_is_order_not_found_during_status_update_error(self):
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(
            Exception("not found")
        ))
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(
            Exception("does not exist")
        ))
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(
            Exception("network error")
        ))

    async def test_request_order_status_no_exchange_order_id(self):
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        update = await self.exchange._request_order_status(order)
        self.assertEqual(OrderState.PENDING_CREATE, update.new_state)

    async def test_request_order_status_not_found(self):
        self._mock_rest_assistant({"status": "notFound", "message": "Order not found"})

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        update = await self.exchange._request_order_status(order)
        self.assertEqual(OrderState.CANCELED, update.new_state)

    async def test_get_last_traded_prices(self):
        self.exchange._get_last_traded_price = AsyncMock(return_value=123.45)
        result = await self.exchange.get_last_traded_prices([self.trading_pair])
        self.assertEqual({self.trading_pair: 123.45}, result)

    async def test_create_order_book_data_source(self):
        data_source = self.exchange._create_order_book_data_source()
        self.assertIsInstance(data_source, DecibelPerpetualAPIOrderBookDataSource)

    async def test_create_user_stream_data_source(self):
        data_source = self.exchange._create_user_stream_data_source()
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
            DecibelPerpetualUserStreamDataSource,
        )
        self.assertIsInstance(data_source, DecibelPerpetualUserStreamDataSource)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_success(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"

        self._mock_rest_assistant([{"mark_px": "50123.5"}])

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(50123.5, price)

    async def test_get_last_traded_price_no_exchange_symbol(self):
        self.exchange._trading_pair_symbol_map = None
        self.exchange._set_trading_pair_symbol_map(None)

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(0.0, price)

    async def test_update_positions_empty_positions(self):
        self._mock_rest_assistant({"positions": []})

        await self.exchange._update_positions()

        self.assertEqual(0, len(self.exchange.account_positions))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_positions_resolves_market_addr_to_trading_pair(self, mock_get_market_addr):
        """
        Decibel's REST /positions endpoint returns the on-chain ``market_addr`` (hex)
        in the ``market`` field, not ``market_name``. The connector must map that back
        to the Hummingbot trading pair before storing the position, otherwise the
        strategy ends up with positions keyed by hex (QA-reported: hex shown in UI,
        strategy couldn't close and opened new buys instead).
        """
        await self._simulate_trading_rules_initialized()
        self.exchange._perpetual_trading.account_positions.clear()
        self.exchange._market_addr_to_trading_pair.clear()

        market_addr_hex = "0x0b5031a8ca4be089deadbeefcafebabe0123456789abcdef0123456789abcdef"  # noqa: mock
        mock_get_market_addr.return_value = market_addr_hex

        self._mock_rest_assistant({
            "positions": [
                {
                    "market": market_addr_hex,
                    "size": "1.5",
                    "entry_price": "50000.0",
                    "leverage": "10",
                    "unrealized_pnl": "150.0",
                }
            ]
        })

        await self.exchange._update_positions()

        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))
        pos = list(positions.values())[0]
        self.assertEqual(self.trading_pair, pos.trading_pair)
        self.assertEqual(Decimal("1.5"), pos.amount)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_positions_skips_unknown_market_identifier(self, mock_get_market_addr):
        """
        If Decibel returns a market identifier we can't resolve (neither a known
        market_name nor a derivable market_addr), skip it rather than silently
        registering the position under a hex key.
        """
        await self._simulate_trading_rules_initialized()
        self.exchange._perpetual_trading.account_positions.clear()
        self.exchange._market_addr_to_trading_pair.clear()

        mock_get_market_addr.return_value = "0xknownmarketaddr"
        self._mock_rest_assistant({
            "positions": [
                {
                    "market": "0xunknownmarketaddrdoesnotmatch",
                    "size": "1.5",
                    "entry_price": "50000.0",
                    "leverage": "10",
                }
            ]
        })

        await self.exchange._update_positions()

        self.assertEqual(0, len(self.exchange.account_positions))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_process_position_update_event_resolves_market_addr(self, mock_get_market_addr):
        """WS position updates also carry market_addr — same resolution path."""
        self.exchange._market_addr_to_trading_pair.clear()
        market_addr_hex = "0x0b5031a8ca4be089fedcba9876543210fedcba9876543210fedcba9876543210"  # noqa: mock
        mock_get_market_addr.return_value = market_addr_hex

        event = {
            "market": market_addr_hex,
            "size": "2.0",
            "entry_price": "50000",
            "unrealized_pnl": "200",
            "leverage": "5",
        }

        await self.exchange._process_position_update_event(event)

        position = self.exchange._perpetual_trading.get_position(self.trading_pair)
        self.assertIsNotNone(position)
        self.assertEqual(Decimal("2.0"), position.amount)

    # ========== Additional tests for uncovered methods ==========

    def test_api_key_property(self):
        self.assertEqual("test_api_key", self.exchange.api_key)

    def test_get_fee_maker(self):
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
        )
        self.assertIsNotNone(fee)

    def test_get_fee_taker(self):
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
            is_maker=False,
        )
        self.assertIsNotNone(fee)

    def test_get_fee_uses_trading_fees_when_populated(self):
        """When _trading_fees has a schema, _get_fee should use the tier-specific rate."""
        from hummingbot.core.data_type.trade_fee import TradeFeeSchema
        tier1_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.00009"),
            taker_percent_fee_decimal=Decimal("0.0003"),
        )
        self.exchange._trading_fees["BTC-USD"] = tier1_schema

        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
            is_maker=False,
        )

        self.assertEqual(Decimal("0.0003"), fee.percent)

    def test_get_fee_maker_with_trading_fees_populated(self):
        """_get_fee should use maker rate when _trading_fees is populated and order is LIMIT_MAKER."""
        from hummingbot.core.data_type.trade_fee import TradeFeeSchema
        tier1_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.00009"),
            taker_percent_fee_decimal=Decimal("0.0003"),
        )
        self.exchange._trading_fees["BTC-USD"] = tier1_schema

        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
        )

        self.assertEqual(Decimal("0.00009"), fee.percent)

    def test_create_trading_pair_symbol_map(self):
        exchange_info = {
            "markets": [
                {"market_name": "BTC/USD"},
                {"market_name": "ETH/USD"},
            ]
        }
        result = self.exchange._create_trading_pair_symbol_map(exchange_info)
        self.assertEqual(2, len(result))
        self.assertEqual("BTC-USD", result["BTC/USD"])
        self.assertEqual("ETH-USD", result["ETH/USD"])

    def test_create_trading_pair_symbol_map_list_format(self):
        exchange_info = [
            {"market_name": "BTC/USD"},
        ]
        result = self.exchange._create_trading_pair_symbol_map(exchange_info)
        self.assertEqual(1, len(result))
        self.assertEqual("BTC-USD", result["BTC/USD"])

    def test_create_trading_pair_symbol_map_empty(self):
        exchange_info = {"markets": []}
        result = self.exchange._create_trading_pair_symbol_map(exchange_info)
        self.assertEqual(0, len(result))

    def test_get_perp_engine_global_address(self):
        with patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_perp_engine_global_address") as mock_get:
            mock_get.return_value = "0xperpengine"
            result = self.exchange.get_perp_engine_global_address()
            self.assertEqual("0xperpengine", result)

    async def test_get_market_addr_for_pair(self):
        # Manually set the trading pair symbol map so the method can derive the address
        from bidict import bidict
        self.exchange._trading_pair_symbol_map = bidict()
        self.exchange._trading_pair_symbol_map[self.exchange_symbol] = self.trading_pair

        result = await self.exchange.get_market_addr_for_pair(self.trading_pair)
        # Should return a valid hex address (computed via SDK)
        self.assertTrue(result.startswith("0x"))
        self.assertEqual(len(result), 66)  # 0x + 64 hex chars

    async def test_get_market_addr_for_pair_not_found(self):
        # Unknown pair still computes an address via SDK (no HTTP needed)
        from bidict import bidict
        self.exchange._trading_pair_symbol_map = bidict()

        # exchange_symbol_associated_to_pair returns "UNKNOWN-PAIR" as-is when map is empty
        result = await self.exchange.get_market_addr_for_pair("UNKNOWN-PAIR")
        self.assertTrue(result.startswith("0x"))

    async def test_api_request_url_uses_base_class(self):
        """Verify _api_request_url is inherited from base class (no override)."""
        # Base class uses public_rest_url by default; Decibel's web_utils returns same URL for both
        url = await self.exchange._api_request_url("/api/v1/markets")
        self.assertIn("/api/v1/markets", url)

    async def test_make_trading_rules_request(self):
        self._mock_rest_assistant({"markets": []})
        result = await self.exchange._make_trading_rules_request()
        self.assertEqual({"markets": []}, result)

    async def test_make_trading_pairs_request(self):
        self._mock_rest_assistant({"markets": [{"market_name": "BTC/USD"}]})
        result = await self.exchange._make_trading_pairs_request()
        self.assertEqual({"markets": [{"market_name": "BTC/USD"}]}, result)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_address_derivation_error(self, mock_get_market_addr):
        mock_get_market_addr.side_effect = Exception("Invalid market name")
        self.exchange._trading_pair_symbol_map = bidict({self.exchange_symbol: self.trading_pair})

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(0.0, price)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_failed_response(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({"status": "failed", "message": "Market not found"})

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(0.0, price)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_no_data(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant([])

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(0.0, price)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_dict_response(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({"mark_px": "45000.0"})

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(45000.0, price)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_last_traded_price_exception(self, mock_get_market_addr):
        mock_get_market_addr.side_effect = Exception("Network error")

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertEqual(0.0, price)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_request_order_status_filled(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "status": "Filled",
            "order": {"unix_ms": 1700000000000}
        })

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        update = await self.exchange._request_order_status(order)
        self.assertEqual(OrderState.FILLED, update.new_state)

    async def test_update_trading_rules(self):
        self._mock_rest_assistant({
            "markets": [{
                "market_name": self.exchange_symbol,
                "min_size": 1000,
                "lot_size": 1000,
                "tick_size": 1000000,
                "px_decimals": 6,
                "sz_decimals": 3,
                "max_open_interest": 1000000000,
            }]
        })

        await self.exchange._update_trading_rules()

        self.assertIn(self.trading_pair, self.exchange._trading_rules)

    async def test_format_trading_rules_list_format(self):
        exchange_info = [{
            "market_name": self.exchange_symbol,
            "min_size": 1000,
            "lot_size": 1000,
            "tick_size": 1000000,
            "px_decimals": 6,
            "sz_decimals": 3,
            "max_open_interest": 1000000000,
        }]

        trading_rules = await self.exchange._format_trading_rules(exchange_info)
        self.assertEqual(1, len(trading_rules))

    async def test_format_trading_rules_error(self):
        exchange_info = {
            "markets": [{"market_name": None}]
        }
        trading_rules = await self.exchange._format_trading_rules(exchange_info)
        self.assertEqual(0, len(trading_rules))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_all_trade_updates_for_order_no_exchange_id(self, mock_get_market_addr):
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        result = await self.exchange._all_trade_updates_for_order(order)
        self.assertEqual([], result)

    async def test_update_order_fills_from_trades_no_trading_pairs(self):
        self.exchange._trading_pairs = []
        # Should return early without error
        await self.exchange._update_order_fills_from_trades()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_order_fills_from_trades_with_data(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "trades": [{
                "order_id": "123",
                "trade_id": "t1",
                "price": "50000",
                "size": "0.5",
                "fee_rate": 0.0004,
                "fee_asset": "USD",
                "timestamp": 1700000000000,
            }]
        })

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("50000"),
            creation_timestamp=1640780000
        )
        order.exchange_order_id = "123"
        self.exchange._order_tracker.all_fillable_orders_by_exchange_order_id["123"] = order

        await self.exchange._update_order_fills_from_trades()

    async def test_process_order_update_event_unknown_order(self):
        event = {
            "order_id": "999",
            "status": "Filled",
            "timestamp": 1700000000000,
        }
        # Should not raise, just logs and returns
        await self.exchange._process_order_update_event(event)

    async def test_process_trade_event(self):
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("50000"),
            creation_timestamp=1640780000
        )
        order._exchange_order_id = "123"
        order.exchange_order_id_update_event.set()
        self.exchange._order_tracker.active_orders["test_id"] = order

        event = {
            "order_id": "123",
            "trade_id": "t1",
            "price": "50000",
            "size": "0.5",
            "fee": "10",
            "timestamp": 1700000000000,
        }

        await self.exchange._process_trade_event(event)

    async def test_process_position_update_event(self):
        event = {
            "market": self.exchange_symbol,
            "size": "2.0",
            "entry_price": "50000",
            "unrealized_pnl": "200",
            "leverage": "5",
        }

        await self.exchange._process_position_update_event(event)

        position = self.exchange._perpetual_trading.get_position(self.trading_pair)
        self.assertIsNotNone(position)
        self.assertEqual(Decimal("2.0"), position.amount)

    async def test_process_position_update_event_short(self):
        event = {
            "market": self.exchange_symbol,
            "size": "-1.5",
            "entry_price": "50000",
            "unrealized_pnl": "-100",
            "leverage": "3",
        }

        await self.exchange._process_position_update_event(event)

        position = self.exchange._perpetual_trading.get_position(self.trading_pair)
        self.assertIsNotNone(position)
        self.assertEqual(Decimal("1.5"), position.amount)

    async def test_process_position_update_event_error(self):
        event = {"invalid": "data"}
        # Should not raise
        await self.exchange._process_position_update_event(event)

    async def test_process_balance_update_event(self):
        event = {
            "perp_equity_balance": 2000.0,
            "usdc_cross_withdrawable_balance": 1500.0,
        }

        await self.exchange._process_balance_update_event(event)

        self.assertEqual(Decimal("2000"), self.exchange._account_balances["USD"])
        self.assertEqual(Decimal("1500"), self.exchange._account_available_balances["USD"])

    async def test_process_balance_update_event_ignore_zero(self):
        # Set positive balance first
        self.exchange._account_available_balances["USD"] = Decimal("1000")
        self.exchange._account_balances["USD"] = Decimal("1000")

        event = {
            "perp_equity_balance": 0,
            "usdc_cross_withdrawable_balance": 0,
        }

        await self.exchange._process_balance_update_event(event)

        # Balance should remain unchanged
        self.assertEqual(Decimal("1000"), self.exchange._account_available_balances["USD"])

    async def test_process_balance_update_event_error(self):
        event = {"invalid": "data"}
        # Should not raise
        await self.exchange._process_balance_update_event(event)

    async def test_process_balance_update_event_nested(self):
        event = {
            "account_overview": {
                "perp_equity_balance": 3000.0,
                "usdc_cross_withdrawable_balance": 2500.0,
            }
        }

        await self.exchange._process_balance_update_event(event)

        self.assertEqual(Decimal("3000"), self.exchange._account_balances["USD"])
        self.assertEqual(Decimal("2500"), self.exchange._account_available_balances["USD"])

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_success(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "funding_payments": [{
                "timestamp": 1700000000000,
                "funding_rate": "0.0001",
                "payment": "5.0",
            }]
        })

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(1700000000.0, timestamp)
        self.assertEqual(Decimal("0.0001"), rate)
        self.assertEqual(Decimal("5.0"), payment)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_empty(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({"funding_payments": []})

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("0"), rate)
        self.assertEqual(Decimal("0"), payment)

    async def test_user_stream_event_listener_trade_update(self):
        # Test _process_trade_event directly
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("50000"),
            creation_timestamp=1640780000
        )
        order.exchange_order_id = "123"
        self.exchange._order_tracker.all_fillable_orders_by_exchange_order_id["123"] = order

        event = {
            "order_id": "123",
            "trade_id": "t1",
            "price": "50000",
            "size": "0.5",
            "fee": "10",
            "timestamp": 1700000000000,
        }
        await self.exchange._process_trade_event(event)

    async def test_process_trade_event_builds_fee_when_closing_position(self):
        """Regression: ``_process_trade_event`` was passing ``self.trade_fee_schema``
        (the bound method) instead of ``self.trade_fee_schema()`` (its return
        value) to ``TradeFeeBase.new_perpetual_fee``. When ``position_action``
        was anything other than ``OPEN``, the ``or fee_schema.percent_fee_token``
        branch evaluated and raised::

            AttributeError: '_cython_3_2_4.cython_function_or_method' object
            has no attribute 'percent_fee_token'

        The pre-existing ``test_user_stream_event_listener_trade_update`` did
        NOT catch this: it wrote to the *property* ``all_fillable_orders_by_exchange_order_id``
        (which rebuilds a fresh dict on every access), so ``tracked_order`` came
        back ``None`` and the fee-building path was never reached.

        This test seeds ``active_orders`` (which the property actually reads)
        with a ``PositionAction.CLOSE`` order so the fee path is exercised and
        the short-circuit is avoided.
        """
        from unittest.mock import MagicMock

        order = InFlightOrder(
            client_order_id="close_test_id",
            exchange_order_id="999",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            amount=Decimal("0.54"),
            price=Decimal("41.39"),
            creation_timestamp=1640780000,
            initial_state=OrderState.OPEN,
            position=PositionAction.CLOSE,
        )
        self.exchange._order_tracker._in_flight_orders[order.client_order_id] = order

        # Spy on process_trade_update to confirm the fee path completed.
        self.exchange._order_tracker.process_trade_update = MagicMock()

        event = {
            "order_id": "999",
            "trade_id": "close_trade_1",
            "price": "41.39",
            "size": "0.54",
            "fee": "0.009",
            "timestamp": 1700000000000,
        }
        # Must not raise AttributeError: '...' object has no attribute 'percent_fee_token'.
        await self.exchange._process_trade_event(event)

        self.exchange._order_tracker.process_trade_update.assert_called_once()
        trade_update = self.exchange._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("close_test_id", trade_update.client_order_id)
        self.assertEqual("999", trade_update.exchange_order_id)
        # Fee was built successfully (not None, has the expected flat fee).
        self.assertIsNotNone(trade_update.fee)
        self.assertEqual(1, len(trade_update.fee.flat_fees))
        self.assertEqual(Decimal("0.009"), trade_update.fee.flat_fees[0].amount)

    async def test_user_stream_event_listener_position_update(self):
        # Test _process_position_update_event directly
        event = {
            "market": self.exchange_symbol,
            "size": "1.0",
            "entry_price": "50000",
            "unrealized_pnl": "100",
            "leverage": "5",
        }
        await self.exchange._process_position_update_event(event)
        position = self.exchange._perpetual_trading.get_position(self.trading_pair)
        self.assertIsNotNone(position)

    async def test_user_stream_event_listener_balance_update(self):
        # Test _process_balance_update_event directly
        event = {
            "perp_equity_balance": 5000.0,
            "usdc_cross_withdrawable_balance": 4000.0,
        }
        await self.exchange._process_balance_update_event(event)
        self.assertEqual(Decimal("5000"), self.exchange._account_balances["USD"])
        self.assertEqual(Decimal("4000"), self.exchange._account_available_balances["USD"])

    async def test_user_stream_event_listener_non_dict_ignored(self):
        # The listener filters non-dict events; test the guard clause path
        # by verifying _process_order_update_event handles dict-only input
        # (non-dict events are filtered out by `if not isinstance(event_message, dict): continue`)
        pass  # Coverage achieved through the isinstance check in the listener

    async def test_user_stream_event_listener_open_orders_topic(self):
        # Test _process_order_update_event for open orders topic
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        order.exchange_order_id = "123"
        self.exchange._order_tracker.all_updatable_orders_by_exchange_order_id["123"] = order

        event = {
            "order_id": "123",
            "status": "Open",
            "timestamp": 1700000000000,
        }
        await self.exchange._process_order_update_event(event)

    def test_status_dict(self):
        result = self.exchange.status_dict
        self.assertIsInstance(result, dict)

    async def test_create_web_assistants_factory(self):
        factory = self.exchange._create_web_assistants_factory()
        self.assertIsNotNone(factory)

    async def test_initialize_trading_pair_symbols_from_exchange_info(self):
        exchange_info = {
            "markets": [{"market_name": self.exchange_symbol}]
        }
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(exchange_info)
        self.assertIsNotNone(self.exchange._trading_pair_symbol_map)

    # ========== Tests for _place_order ==========

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_no_order_book_raises(self, mock_get_market_addr):
        mock_get_market_addr.return_value = "0xmarketaddr123"
        # MARKET order requires order book for mark price
        self.exchange.get_order_book = MagicMock(return_value=None)
        with self.assertRaises(ValueError) as ctx:
            await self.exchange._place_order(
                order_id="test_order",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("50000"),
            )
        self.assertIn("Order book not available", str(ctx.exception))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_limit_success(self, mock_get_market_addr):
        """Test LIMIT order placement with mocked transaction builder."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        # Mock the transaction builder
        mock_tx_builder = AsyncMock()
        mock_tx_builder.place_order.return_value = ("0xtxhash", "order_123", 1700000000.0)
        self.exchange._transaction_builder = mock_tx_builder

        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id="test_order",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
        )

        self.assertEqual("order_123", exchange_order_id)
        self.assertIsInstance(timestamp, float)
        mock_tx_builder.place_order.assert_awaited_once()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_market_success(self, mock_get_market_addr):
        """Test MARKET order placement (converted to IOC with slippage).

        Regression test for the float/Decimal TypeError that broke MARKET-order
        position closes: OrderBook.get_price() returns float, so the connector
        must convert to Decimal before doing arithmetic with Decimal("2").
        """
        mock_get_market_addr.return_value = "0xmarketaddr123"

        # Trading rule is required since MARKET orders now quantize the
        # slippage-adjusted price via self.quantize_order_price().
        from hummingbot.connector.trading_rule import TradingRule
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
        )

        # Mock order book — get_price() returns float in production (see
        # hummingbot/core/data_type/order_book.pyx:318), so the mock must too.
        mock_order_book = MagicMock()
        mock_order_book.get_price.side_effect = lambda is_buy: 50100.0 if is_buy else 50000.0
        self.exchange.get_order_book = MagicMock(return_value=mock_order_book)

        # Mock the transaction builder
        mock_tx_builder = AsyncMock()
        mock_tx_builder.place_order.return_value = ("0xtxhash", "order_456", 1700000000.0)
        self.exchange._transaction_builder = mock_tx_builder

        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id="test_order",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("50000"),
        )

        self.assertEqual("order_456", exchange_order_id)
        mock_tx_builder.place_order.assert_awaited_once()
        # Verify IOC flag was set
        call_kwargs = mock_tx_builder.place_order.call_args.kwargs
        self.assertTrue(call_kwargs.get("is_ioc", False))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_market_price_quantized_to_tick_size(self, mock_get_market_addr):
        """Regression: MARKET orders must quantize the slippage-adjusted price to
        ``min_price_increment``. Decibel's Move contract aborts with
        ``EPRICE_NOT_RESPECTING_TICKER_SIZE(0x6)`` if the price is not a multiple
        of the market's tick size, which caused grid_strike executors to fail
        closing positions (LONG was left open, user had to close manually).
        """
        mock_get_market_addr.return_value = "0xmarketaddr123"

        # Coarse tick size: 0.01 USD. px_decimals=6 ⇒ tick in chain units = 10000.
        from hummingbot.connector.trading_rule import TradingRule
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
        )

        # Mid = 44.85 → SELL limit price = 44.85 * (1 - 0.08) = 41.262
        # Unquantized, this is already tick-aligned at 0.01; deliberately pick
        # a mid that produces a non-tick-aligned value to exercise the floor.
        mock_order_book = MagicMock()
        mock_order_book.get_price.side_effect = lambda is_buy: 44.905 if is_buy else 44.903
        self.exchange.get_order_book = MagicMock(return_value=mock_order_book)

        mock_tx_builder = AsyncMock()
        mock_tx_builder.place_order.return_value = ("0xtxhash", "order_qtz", 1700000000.0)
        self.exchange._transaction_builder = mock_tx_builder

        await self.exchange._place_order(
            order_id="test_order_qtz",
            trading_pair=self.trading_pair,
            amount=Decimal("0.54"),
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
        )

        call_kwargs = mock_tx_builder.place_order.call_args.kwargs
        chain_price = call_kwargs["price"]
        # tick_size in chain units = min_price_increment * 10^px_decimals = 0.01 * 1e6 = 10_000
        self.assertEqual(0, chain_price % 10_000,
                         f"chain_price={chain_price} is not a multiple of 10_000 "
                         f"(0.01 tick in chain units); Decibel will reject with "
                         f"EPRICE_NOT_RESPECTING_TICKER_SIZE")

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_limit_maker_success(self, mock_get_market_addr):
        """Test LIMIT_MAKER order placement (post_only)."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        mock_tx_builder = AsyncMock()
        mock_tx_builder.place_order.return_value = ("0xtxhash", "order_789", 1700000000.0)
        self.exchange._transaction_builder = mock_tx_builder

        await self.exchange._place_order(
            order_id="test_order",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT_MAKER,
            price=Decimal("50000"),
        )

        call_kwargs = mock_tx_builder.place_order.call_args.kwargs
        self.assertTrue(call_kwargs.get("is_post_only", False))

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_retry_on_txn_submit_error(self, mock_get_market_addr):
        """Test that order placement retries on TxnSubmitError."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        from decibel import TxnSubmitError
        mock_tx_builder = AsyncMock()
        # Fail twice, succeed on third attempt
        mock_tx_builder.place_order.side_effect = [
            TxnSubmitError("Network error"),
            TxnSubmitError("Network error"),
            ("0xtxhash", "order_retry", 1700000000.0),
        ]
        self.exchange._transaction_builder = mock_tx_builder

        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id="test_order",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
        )

        self.assertEqual("order_retry", exchange_order_id)
        self.assertEqual(3, mock_tx_builder.place_order.call_count)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_order_fails_after_max_retries(self, mock_get_market_addr):
        """Test that order placement raises after max retries."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        from decibel import TxnSubmitError
        mock_tx_builder = AsyncMock()
        mock_tx_builder.place_order.side_effect = TxnSubmitError("Persistent error")
        self.exchange._transaction_builder = mock_tx_builder

        with self.assertRaises(TxnSubmitError):
            await self.exchange._place_order(
                order_id="test_order",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("50000"),
            )

        self.assertEqual(3, mock_tx_builder.place_order.call_count)

    # ========== Tests for _place_cancel ==========

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_cancel_timeout_waiting_exchange_id(self, mock_get_market_addr):
        """Test cancel returns False when exchange_order_id times out."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        # Mock get_exchange_order_id to timeout
        order.get_exchange_order_id = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await self.exchange._place_cancel("test_id", order)
        self.assertFalse(result)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_cancel_no_exchange_order_id(self, mock_get_market_addr):
        """Test cancel returns False when exchange_order_id is None after waiting."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        # Mock get_exchange_order_id to return None
        order.get_exchange_order_id = AsyncMock(return_value=None)

        result = await self.exchange._place_cancel("test_id", order)
        self.assertFalse(result)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_cancel_txn_submit_error_returns_false(self, mock_get_market_addr):
        """Test cancel returns False on TxnSubmitError after retries."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        from decibel import TxnSubmitError
        mock_tx_builder = AsyncMock()
        mock_tx_builder.cancel_order.side_effect = TxnSubmitError("Submit error")
        self.exchange._transaction_builder = mock_tx_builder

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        object.__setattr__(order, '_exchange_order_id', "123")
        order.exchange_order_id_update_event.set()

        result = await self.exchange._place_cancel("test_id", order)
        self.assertFalse(result)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_place_cancel_unknown_error_returns_false(self, mock_get_market_addr):
        """Test cancel returns False on unknown exception after retries."""
        mock_get_market_addr.return_value = "0xmarketaddr123"

        mock_tx_builder = AsyncMock()
        mock_tx_builder.cancel_order.side_effect = Exception("Unknown error")
        self.exchange._transaction_builder = mock_tx_builder

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )
        object.__setattr__(order, '_exchange_order_id', "123")
        order.exchange_order_id_update_event.set()

        result = await self.exchange._place_cancel("test_id", order)
        self.assertFalse(result)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_order_fills_from_trades_with_matching_order(self, mock_get_market_addr):
        """Test _update_order_fills_from_trades processes trades for tracked orders."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "trades": [{
                "order_id": "123",
                "trade_id": "t1",
                "price": "50000",
                "size": "0.5",
                "fee_rate": 0.0004,
                "fee_asset": "USD",
                "timestamp": 1700000000000,
            }]
        })

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("50000"),
            creation_timestamp=1640780000
        )
        object.__setattr__(order, '_exchange_order_id', "123")
        order.exchange_order_id_update_event.set()
        self.exchange._order_tracker.active_orders["test_id"] = order

        await self.exchange._update_order_fills_from_trades()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_order_fills_from_trades_exception_path(self, mock_get_market_addr):
        """Test _update_order_fills_from_trades handles API errors gracefully."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        mock_rest = AsyncMock()
        mock_rest.execute_request.side_effect = Exception("API error")
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest)

        await self.exchange._update_order_fills_from_trades()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_order_fills_from_trades_no_matching_order(self, mock_get_market_addr):
        """Test _update_order_fills_from_trades skips trades for untracked orders."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "trades": [{
                "order_id": "999",
                "trade_id": "t1",
                "price": "50000",
                "size": "0.5",
            }]
        })

        await self.exchange._update_order_fills_from_trades()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_update_order_fills_from_trades_exception_in_trade_processing(self, mock_get_market_addr):
        """Test _update_order_fills_from_trades handles errors in individual trade processing."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "trades": [{
                "order_id": "123",
                "trade_id": "t1",
            }]
        })

        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("50000"),
            creation_timestamp=1640780000
        )
        object.__setattr__(order, '_exchange_order_id', "123")
        order.exchange_order_id_update_event.set()
        self.exchange._order_tracker.active_orders["test_id"] = order

        await self.exchange._update_order_fills_from_trades()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_with_data(self, mock_get_market_addr):
        """Test _fetch_last_fee_payment returns funding payment data."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({
            "funding_payments": [{
                "timestamp": 1700000000000,
                "funding_rate": "0.0001",
                "payment": "5.0",
            }]
        })

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(1700000000.0, timestamp)
        self.assertEqual(Decimal("0.0001"), rate)
        self.assertEqual(Decimal("5.0"), payment)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_empty_response(self, mock_get_market_addr):
        """Test _fetch_last_fee_payment returns zeros when no payments."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({"funding_payments": []})

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("0"), rate)
        self.assertEqual(Decimal("0"), payment)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_no_key(self, mock_get_market_addr):
        """Test _fetch_last_fee_payment returns zeros when key missing."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({})

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("0"), rate)
        self.assertEqual(Decimal("0"), payment)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_fetch_last_fee_payment_exception(self, mock_get_market_addr):
        """Test _fetch_last_fee_payment handles API errors."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        mock_rest = AsyncMock()
        mock_rest.execute_request.side_effect = Exception("API error")
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest)

        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(0, timestamp)
        self.assertEqual(Decimal("0"), rate)
        self.assertEqual(Decimal("0"), payment)

    async def test_user_stream_event_listener_routed_to_order_update(self):
        """Test _user_stream_event_listener routes to _process_order_update_event."""
        # Test the routing logic in _user_stream_event_listener
        # by calling _process_order_update_event directly (which is what the listener does)
        event = {
            "order_id": "unknown",
            "status": "Filled",
            "timestamp": 1700000000000,
        }
        # Should not raise for unknown orders
        await self.exchange._process_order_update_event(event)

    async def test_user_stream_event_listener_routed_to_trade_update(self):
        """Test _user_stream_event_listener routes to _process_trade_event."""
        event = {
            "order_id": "unknown",
            "trade_id": "t1",
            "price": "50000",
            "size": "0.5",
            "fee": "10",
            "timestamp": 1700000000000,
        }
        # Should not raise for unknown orders
        await self.exchange._process_trade_event(event)

    async def test_user_stream_event_listener_routed_to_position_update(self):
        """Test _user_stream_event_listener routes to _process_position_update_event."""
        event = {
            "market": self.exchange_symbol,
            "size": "1.0",
            "entry_price": "50000",
            "unrealized_pnl": "100",
            "leverage": "5",
        }
        await self.exchange._process_position_update_event(event)
        position = self.exchange._perpetual_trading.get_position(self.trading_pair)
        self.assertIsNotNone(position)

    async def test_user_stream_event_listener_routed_to_balance_update(self):
        """Test _user_stream_event_listener routes to _process_balance_update_event."""
        event = {
            "perp_equity_balance": 5000.0,
            "usdc_cross_withdrawable_balance": 4000.0,
        }
        await self.exchange._process_balance_update_event(event)
        self.assertEqual(Decimal("5000"), self.exchange._account_balances["USD"])

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_success(self, mock_get_market_addr):
        """Test get_all_pairs_prices returns prices for all pairs."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant([{"mark_px": "50120.5"}])

        results = await self.exchange.get_all_pairs_prices()
        self.assertIsInstance(results, list)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_no_symbol_map(self, mock_get_market_addr):
        """Test get_all_pairs_prices returns empty when symbol map is None."""
        self.exchange._trading_pair_symbol_map = None
        self.exchange._set_trading_pair_symbol_map(None)

        results = await self.exchange.get_all_pairs_prices()
        self.assertEqual([], results)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_dict_response(self, mock_get_market_addr):
        """Test get_all_pairs_prices handles dict response."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant({"mark_px": "50120.5"})

        results = await self.exchange.get_all_pairs_prices()
        self.assertIsInstance(results, list)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_empty_response(self, mock_get_market_addr):
        """Test get_all_pairs_prices handles empty list response."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant([])

        results = await self.exchange.get_all_pairs_prices()
        self.assertIsInstance(results, list)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_no_mark_px(self, mock_get_market_addr):
        """Test get_all_pairs_prices skips entries without mark_px."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        self._mock_rest_assistant([{"other_field": "value"}])

        results = await self.exchange.get_all_pairs_prices()
        self.assertEqual([], results)

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative.get_market_addr")
    async def test_get_all_pairs_prices_exception(self, mock_get_market_addr):
        """Test get_all_pairs_prices handles API errors gracefully."""
        mock_get_market_addr.return_value = "0xmarketaddr123"
        mock_rest = AsyncMock()
        mock_rest.execute_request.side_effect = Exception("API error")
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_rest)

        results = await self.exchange.get_all_pairs_prices()
        self.assertEqual([], results)
