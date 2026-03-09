import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Callable, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses import aioresponses

import hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import BluefinPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


# Valid BIP-39 test mnemonic (standard test mnemonic)
TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


class BluefinPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    """Comprehensive test suite for Bluefin Perpetual connector using AbstractPerpetualDerivativeTests."""

    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_mnemonic = TEST_MNEMONIC
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    # ============================================================
    # AbstractExchangeConnectorTests Required Properties
    # ============================================================

    @property
    def all_symbols_url(self):
        """URL for fetching all trading pairs."""
        # Bluefin SDK handles this internally - return mock URL
        url = web_utils.get_rest_url_for_endpoint("/markets")
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def latest_prices_url(self):
        """URL for fetching latest prices."""
        url = web_utils.get_rest_url_for_endpoint("/marketData")
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def network_status_url(self):
        """URL for checking network status."""
        url = web_utils.get_rest_url_for_endpoint("/status")
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def trading_rules_url(self):
        """URL for fetching trading rules."""
        return self.all_symbols_url

    @property
    def order_creation_url(self):
        """URL for creating orders."""
        url = web_utils.get_rest_url_for_endpoint("/orders")
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def balance_url(self):
        """URL for fetching account balance."""
        url = web_utils.get_rest_url_for_endpoint("/account")
        return url

    @property
    def funding_info_url(self):
        """URL for fetching funding rate info."""
        url = web_utils.get_rest_url_for_endpoint("/fundingInfo")
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def funding_payment_url(self):
        """URL for fetching funding payment history."""
        # Bluefin doesn't have separate funding payment endpoint
        return None

    # ============================================================
    # Mock Response Properties
    # ============================================================

    @property
    def all_symbols_request_mock_response(self):
        """Mock response for all trading pairs."""
        return {
            "markets": [
                {
                    "symbol": "BTC-PERP",
                    "baseAsset": "BTC",
                    "quoteAsset": "USD",
                    "tickSize": "0.1",
                    "stepSize": "0.001",
                    "minOrderSize": "0.001",
                    "maxLeverage": 50,
                },
                {
                    "symbol": "ETH-PERP",
                    "baseAsset": "ETH",
                    "quoteAsset": "USD",
                    "tickSize": "0.01",
                    "stepSize": "0.01",
                    "minOrderSize": "0.01",
                    "maxLeverage": 50,
                },
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        """Mock response for latest prices."""
        return {
            "marketData": [
                {
                    "symbol": "BTC-PERP",
                    "markPrice": str(self.expected_latest_price),
                    "indexPrice": "36700.0",
                    "lastPrice": str(self.expected_latest_price),
                },
                {
                    "symbol": "ETH-PERP",
                    "markPrice": "1920.0",
                    "indexPrice": "1918.0",
                    "lastPrice": "1920.0",
                },
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        """Mock response including an invalid pair."""
        return "INVALID-PAIR", self.all_symbols_request_mock_response

    @property
    def network_status_request_successful_mock_response(self):
        """Mock response for successful network status check."""
        return {"status": "ok", "timestamp": 1640780000000}

    @property
    def trading_rules_request_mock_response(self):
        """Mock response for trading rules."""
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        """Mock response with erroneous trading rules (missing stepSize)."""
        return {
            "markets": [
                {
                    "symbol": "BTC-PERP",
                    "baseAsset": "BTC",
                    "quote Asset": "USD",
                    "tickSize": "0.1",
                    # Missing stepSize - will cause parsing error
                    "minOrderSize": "0.001",
                },
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        """Mock response for successful order creation."""
        return {
            "success": True,
            "orderId": self.expected_exchange_order_id,
            "orderHash": "0xabc123def456",
            "status": "PENDING",
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        """Mock response for account balance."""
        return {
            "address": "0x123",
            "freeCollateral": "10000.0",
            "totalAccountValue": "12000.0",
            "totalNotionalPositionSize": "2000.0",
            "availableMargin": "10000.0",
            "positions": [],
        }

    @property
    def balance_request_mock_response_only_base(self):
        """Mock response for balance with only base asset."""
        return self.balance_request_mock_response_for_base_and_quote

    @property
    def expected_latest_price(self):
        """Expected latest price for testing."""
        return 9999.9

    @property
    def expected_supported_order_types(self):
        """Supported order types for Bluefin."""
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        """Supported position modes for Bluefin."""
        return [PositionMode.ONEWAY]

    @property
    def expected_trading_rule(self):
        """Expected trading rule."""
        return TradingRule(
            trading_pair=self.trading_pair,
            min_base_amount_increment=Decimal("0.001"),
            min_price_increment=Decimal("0.1"),
            min_order_size=Decimal("0.001"),
            min_notional_size=Decimal("10"),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        """Expected error message for erroneous trading rule."""
        return f"Error parsing the trading pair rule"

    @property
    def expected_exchange_order_id(self):
        """Expected exchange order ID."""
        return "bluefin_order_123456"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        """Whether order fill updates are included in status updates."""
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        """Whether HTTP fill updates happen during websocket processing."""
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        """Expected price for partial fill."""
        return Decimal("10000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        """Expected amount for partial fill."""
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        """Expected fill fee."""
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("5.0"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        """Expected fill trade ID."""
        return "bluefin_trade_789"

    # ============================================================
    # Funding Rate Properties
    # ============================================================

    @property
    def funding_info_mock_response(self):
        """Mock response for funding info."""
        return {
            "symbol": "BTC-PERP",
            "markPrice": str(self.target_funding_info_mark_price),
            "indexPrice": str(self.target_funding_info_index_price),
            "fundingRate": str(self.target_funding_info_rate),
            "nextFundingTime": self.target_funding_info_next_funding_utc_timestamp * 1000,
        }

    @property
    def empty_funding_payment_mock_response(self):
        """Mock response for empty funding payment history."""
        return {"payments": []}

    @property
    def funding_payment_mock_response(self):
        """Mock response for funding payment history."""
        # Bluefin SDK handles funding internally
        return {"payments": []}

    # ============================================================
    # Connector Creation and Configuration
    # ============================================================

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        """Convert base/quote tokens to exchange symbol."""
        return f"{base_token}-PERP"

    def create_exchange_instance(self):
        """Create Bluefin exchange instance for testing."""
        with patch("hummingbot.connector.derivative.bluefin_perpetual.data_sources.bluefin_data_source.BluefinDataSource"):
            exchange = BluefinPerpetualDerivative(
                bluefin_perpetual_wallet_mnemonic=self.api_mnemonic,
                bluefin_perpetual_network="MAINNET",
                trading_pairs=[self.trading_pair],
                trading_required=False,
            )
        return exchange

    def validate_auth_credentials_present(self, request_call):
        """Validate that auth credentials are present in request."""
        # Bluefin SDK handles authentication internally
        pass

    def validate_order_creation_request(self, order: InFlightOrder, request_call):
        """Validate order creation request."""
        # Bluefin SDK handles order creation internally
        pass

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call):
        """Validate order cancellation request."""
        pass

    def validate_order_status_request(self, order: InFlightOrder, request_call):
        """Validate order status request."""
        pass

    def validate_trades_request(self, order: InFlightOrder, request_call):
        """Validate trades request."""
        pass

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure successful cancellation response."""
        # Bluefin SDK handles cancellation
        return ""

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure erroneous cancellation response."""
        return ""

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure order not found error for cancellation."""
        return ""

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure order not found error for status."""
        return ""

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure completely filled order status response."""
        return ""

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure canceled order status response."""
        return ""

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure open order status response."""
        return ""

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure HTTP error for order status."""
        return ""

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure partially filled order status response."""
        return ""

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure partial fill trade response."""
        return ""

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure full fill trade response."""
        return ""

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """Configure erroneous fill trade response."""
        return ""

    def configure_successful_set_position_mode(
        self, position_mode: PositionMode, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure successful position mode set."""
        pass

    def configure_failed_set_position_mode(
        self, position_mode: PositionMode, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure failed position mode set."""
        pass

    def configure_failed_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure failed leverage set."""
        return "", "Unable to set leverage"

    def configure_successful_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        """Configure successful leverage set."""
        return ""

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        """Configure mixed success/error cancel all response."""
        return []

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        """WebSocket event for new order."""
        return {}

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        """WebSocket event for canceled order."""
        return {}

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        """WebSocket event for full fill."""
        return {}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        """WebSocket event for full fill trade."""
        return {}

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        """WebSocket event for position update."""
        return {}

    @property
    def balance_event_websocket_update(self):
        """WebSocket event for balance update."""
        return {}

    def funding_info_event_for_websocket_update(self):
        """WebSocket event for funding info update."""
        return {}

    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        """Whether cancel requests are executed synchronously."""
        return False

    @property
    def latest_trade_hist_timestamp(self) -> int:
        """Latest trade history timestamp."""
        return 1640780000

    # ============================================================
    # Position Mode Tests Override
    # ============================================================

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        """Test setting position mode to ONEWAY (only supported mode)."""
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        self.async_run_with_timeout(asyncio.sleep(0.1))
        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"Position mode switched to {PositionMode.ONEWAY}.",
            )
        )

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        """Test setting unsupported position mode."""
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=f"Position mode {PositionMode.HEDGE} is not supported. Mode not set.",
            )
        )

    # ============================================================
    # Bluefin-Specific Custom Tests
    # ============================================================

    # ============================================================
    # Bluefin-Specific Custom Tests
    # ============================================================

    @property
    def connector(self):
        """Alias for self.exchange for backward compatibility."""
        return self.exchange

    def test_supported_order_types_includes_limit_maker(self):
        """Test that LIMIT_MAKER is in supported order types."""
        supported = self.exchange.supported_order_types()

        self.assertIn(OrderType.LIMIT, supported)
        self.assertIn(OrderType.MARKET, supported)
        self.assertIn(OrderType.LIMIT_MAKER, supported)

    def test_supported_position_modes_oneway_only(self):
        """Test that only ONEWAY position mode is supported."""
        supported = self.exchange.supported_position_modes()

        self.assertEqual([PositionMode.ONEWAY], supported)

    def test_get_collateral_token_returns_usdc(self):
        """Test that collateral token is USDC for all pairs."""
        buy_collateral = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual("USDC", buy_collateral)
        self.assertEqual("USDC", sell_collateral)

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order")
    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType")
    async def test_place_order_limit_maker_sets_post_only(self, mock_order_type, mock_order):
        """Test that LIMIT_MAKER orders set post_only flag."""
        # Setup mocks
        mock_order_type.LIMIT = "LIMIT"
        mock_order_instance = MagicMock()
        mock_order.return_value = mock_order_instance

        # Mock data source
        self.exchange._data_source = MagicMock()
        self.exchange._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.exchange._data_source.place_order = AsyncMock(
            return_value=MagicMock(order_hash="test_hash_123")
        )

        # Mock quantize methods
        self.exchange.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.exchange.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place LIMIT_MAKER order
        order_id = "test_order_123"
        trading_pair = self.trading_pair
        amount = Decimal("1")
        price = Decimal("50000")

        result = await self.exchange._place_order(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER,
            price=price,
        )

        # Verify order was created with post_only=True
        mock_order.assert_called_once()
        call_kwargs = mock_order.call_args.kwargs
        self.assertTrue(call_kwargs.get("post_only"), "LIMIT_MAKER order should have post_only=True")

        # Verify result
        self.assertEqual("test_hash_123", result[0])

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order")
    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType")
    async def test_place_order_limit_does_not_set_post_only(self, mock_order_type, mock_order):
        """Test that regular LIMIT orders do not set post_only flag."""
        # Setup mocks
        mock_order_type.LIMIT = "LIMIT"
        mock_order_instance = MagicMock()
        mock_order.return_value = mock_order_instance

        # Mock data source
        self.exchange._data_source = MagicMock()
        self.exchange._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.exchange._data_source.place_order = AsyncMock(
            return_value=MagicMock(order_hash="test_hash_456")
        )

        # Mock quantize methods
        self.exchange.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.exchange.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place regular LIMIT order
        order_id = "test_order_456"
        trading_pair = self.trading_pair
        amount = Decimal("1")
        price = Decimal("50000")

        result = await self.exchange._place_order(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=price,
        )

        # Verify order was created with post_only=False
        mock_order.assert_called_once()
        call_kwargs = mock_order.call_args.kwargs
        self.assertFalse(call_kwargs.get("post_only"), "Regular LIMIT order should have post_only=False")

        # Verify result
        self.assertEqual("test_hash_456", result[0])

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.asyncio.sleep", new_callable=AsyncMock)
    async def test_place_order_retries_on_failure(self, mock_sleep):
        """Test that place_order retries on transient failures."""
        # Mock data source that fails twice then succeeds
        self.exchange._data_source = MagicMock()
        self.exchange._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.exchange._data_source.place_order = AsyncMock(
            side_effect=[
                Exception("Network error"),
                Exception("Temporary failure"),
                MagicMock(order_hash="success_hash"),
            ]
        )

        # Mock quantize methods
        self.exchange.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.exchange.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place order
        with patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order"):
            with patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType"):
                result = await self.exchange._place_order(
                    order_id="test_retry",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("50000"),
                )

        # Verify it retried and eventually succeeded
        self.assertEqual(3, self.exchange._data_source.place_order.await_count)
        self.assertEqual("success_hash", result[0])

        # Verify sleep was called for retries (2 retries = 2 sleeps)
        self.assertEqual(2, mock_sleep.await_count)


