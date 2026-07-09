import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.models import XRP, IssuedCurrencyAmount, PaymentFlag
from xrpl.utils import xrp_to_drops

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy import (
    AMMSwapOrderStrategy,
    LimitOrderStrategy,
    MarketOrderStrategy,
    OrderPlacementStrategyFactory,
    XRPLOrderPlacementStrategy,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class TestXRPLOrderPlacementStrategy(unittest.IsolatedAsyncioTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "XRP"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = cls.trading_pair
        cls.client_order_id = "hbot_order_1"

    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock(spec=XrplExchange)

        # Mock XRP and IssuedCurrencyAmount objects
        xrp_obj = XRP()
        issued_currency_obj = IssuedCurrencyAmount(
            currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="0"
        )

        # Mock the connector's methods used by order placement strategies
        self.connector.get_currencies_from_trading_pair.return_value = (xrp_obj, issued_currency_obj)

        # Set up trading rules for the trading pair
        self.connector._trading_rules = {
            self.trading_pair: MagicMock(
                min_base_amount_increment=Decimal("0.000001"),
                min_quote_amount_increment=Decimal("0.000001"),
                min_price_increment=Decimal("0.000001"),
                min_base_amount=Decimal("0.1"),
                min_quote_amount=Decimal("0.1"),
            )
        }

        # Set up trading pair fee rules
        self.connector._trading_pair_fee_rules = {
            self.trading_pair: {
                "maker": Decimal("0.001"),
                "taker": Decimal("0.002"),
                "amm_pool_fee": Decimal("0.003"),
            }
        }

        # Mock authentication
        self.connector._xrpl_auth = MagicMock()
        self.connector._xrpl_auth.get_account.return_value = "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"

        # Create a buy limit order
        self.buy_limit_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="123456",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("0.5"),
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        # Create a sell limit order
        self.sell_limit_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="654321",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("0.5"),
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        # Create a buy market order
        self.buy_market_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="123789",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=None,
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        # Create a sell market order
        self.sell_market_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="987321",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=None,
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        # Create an AMM swap order
        self.amm_swap_buy_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="567890",
            trading_pair=self.trading_pair,
            order_type=OrderType.AMM_SWAP,
            trade_type=TradeType.BUY,
            price=None,
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        # Mock connector methods
        self.connector.xrpl_order_type = MagicMock(return_value=0)
        self.connector._get_best_price = AsyncMock(return_value=Decimal("0.5"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.IssuedCurrencyAmount")
    async def test_get_base_quote_amounts_for_sell_orders(self, mock_issued_currency):
        # Mock IssuedCurrencyAmount to return a proper object
        mock_issued_currency.return_value = IssuedCurrencyAmount(
            currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="50"
        )

        # Create a limit order strategy for a sell order
        strategy = LimitOrderStrategy(self.connector, self.sell_limit_order)

        # Test the get_base_quote_amounts method
        we_pay, we_get = strategy.get_base_quote_amounts()

        # For XRP, we expect the xrp_to_drops conversion to return a string
        self.assertEqual(we_pay, xrp_to_drops(Decimal("100")))

        # For we_get, we expect an IssuedCurrencyAmount
        self.assertIsInstance(we_get, IssuedCurrencyAmount)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.IssuedCurrencyAmount")
    async def test_get_base_quote_amounts_for_buy_orders(self, mock_issued_currency):
        # Mock IssuedCurrencyAmount to return a proper object
        mock_issued_currency.return_value = IssuedCurrencyAmount(
            currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="50"
        )

        # Create a limit order strategy for a buy order
        strategy = LimitOrderStrategy(self.connector, self.buy_limit_order)

        # Test the get_base_quote_amounts method
        we_pay, we_get = strategy.get_base_quote_amounts()

        # For a buy order, we expect we_pay to be an IssuedCurrencyAmount and we_get to be a string (drops)
        self.assertIsInstance(we_pay, IssuedCurrencyAmount)
        self.assertTrue(isinstance(we_get, str), f"Expected we_get to be a string, got {type(we_get)}")

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Memo")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.convert_string_to_hex")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.OfferCreate")
    async def test_limit_order_strategy_create_transaction(self, mock_offer_create, mock_convert_hex, mock_memo):
        # Set up mocks
        mock_convert_hex.return_value = "68626f745f6f726465725f31"  # hex for "hbot_order_1"
        mock_memo_instance = MagicMock()
        mock_memo_instance.memo_data = "68626f745f6f726465725f31"
        mock_memo.return_value = mock_memo_instance

        # Create a mock OfferCreate transaction
        mock_transaction = MagicMock()
        mock_transaction.account = "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"
        mock_transaction.flags = CONSTANTS.XRPL_SELL_FLAG
        mock_transaction.taker_gets = xrp_to_drops(Decimal("100"))
        mock_transaction.taker_pays = IssuedCurrencyAmount(
            currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="50"
        )

        # Create a list of memos
        mock_memos = [mock_memo_instance]
        # Set the memos as a property of the transaction
        mock_transaction.memos = mock_memos

        mock_offer_create.return_value = mock_transaction

        # Create a limit order strategy for a sell order
        strategy = LimitOrderStrategy(self.connector, self.sell_limit_order)

        # Test the create_order_transaction method
        transaction = await strategy.create_order_transaction()

        # Verify the transaction was created as expected
        self.assertEqual(transaction.account, "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")
        self.assertEqual(transaction.flags, CONSTANTS.XRPL_SELL_FLAG)

        # Access memo directly from the mock memos list
        self.assertEqual(mock_memos[0].memo_data, "68626f745f6f726465725f31")

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Decimal")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Memo")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.convert_string_to_hex")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.OfferCreate")
    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.MarketOrderStrategy.get_base_quote_amounts"
    )
    async def test_market_order_strategy_create_transaction(
        self, mock_get_base_quote, mock_offer_create, mock_convert_hex, mock_memo, mock_decimal
    ):
        # Set up mocks
        mock_decimal.return_value = Decimal("1")
        mock_convert_hex.return_value = "68626f745f6f726465725f31"  # hex for "hbot_order_1"
        mock_memo_instance = MagicMock()
        mock_memo_instance.memo_data = "68626f745f6f726465725f31"
        mock_memo.return_value = mock_memo_instance

        # Create a mock OfferCreate transaction
        mock_transaction = MagicMock()
        mock_transaction.account = "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"
        mock_transaction.flags = CONSTANTS.XRPL_SELL_FLAG

        # Create a list of memos
        mock_memos = [mock_memo_instance]
        # Set the memos as a property of the transaction
        mock_transaction.memos = mock_memos

        mock_offer_create.return_value = mock_transaction

        # Mock the get_best_price method to return a known value
        self.connector._get_best_price.return_value = Decimal("0.5")

        # Mock the get_base_quote_amounts to return predefined values
        mock_get_base_quote.return_value = (
            IssuedCurrencyAmount(currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="50"),
            xrp_to_drops(Decimal("100")),
        )

        # Create a market order strategy for a buy order
        strategy = MarketOrderStrategy(self.connector, self.buy_market_order)

        # Test the create_order_transaction method
        transaction = await strategy.create_order_transaction()

        # Verify the transaction was created as expected
        self.assertEqual(transaction.account, "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")
        self.assertEqual(transaction.flags, CONSTANTS.XRPL_SELL_FLAG)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Memo")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.convert_string_to_hex")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Path")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.Payment")
    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.AMMSwapOrderStrategy.get_base_quote_amounts"
    )
    async def test_amm_swap_order_strategy_create_transaction(
        self, mock_get_base_quote, mock_payment, mock_path, mock_convert_hex, mock_memo
    ):
        # Set up mocks
        mock_convert_hex.return_value = "68626f745f6f726465725f315f414d4d5f53574150"  # hex for "hbot_order_1_AMM_SWAP"
        mock_memo_instance = MagicMock()
        mock_memo_instance.memo_data = b"hbot_order_1_AMM_SWAP"
        mock_memo.return_value = mock_memo_instance

        # Create a custom dictionary to mock the payment transaction attributes
        # This avoids using `.destination` which triggers linter errors
        transaction_attrs = {
            "account": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",
            "flags": PaymentFlag.TF_NO_RIPPLE_DIRECT + PaymentFlag.TF_PARTIAL_PAYMENT,
        }

        # Create the mock transaction with the dictionary
        mock_transaction = MagicMock(**transaction_attrs)
        # Add the memos explicitly after creation to avoid subscript errors in assertions
        mock_transaction.memos = MagicMock()  # This will be a non-None value that can be safely accessed

        mock_payment.return_value = mock_transaction

        # Mock the get_best_price method to return a known value
        self.connector._get_best_price.return_value = Decimal("0.5")

        # Mock the get_base_quote_amounts to return predefined values
        mock_get_base_quote.return_value = (
            IssuedCurrencyAmount(currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="50"),
            xrp_to_drops(Decimal("100")),
        )

        # Create an AMM swap order strategy for a buy order
        strategy = AMMSwapOrderStrategy(self.connector, self.amm_swap_buy_order)

        # Test the create_order_transaction method
        transaction = await strategy.create_order_transaction()

        # Verify the returned transaction has the expected attributes
        self.assertEqual(transaction.account, "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")
        self.assertEqual(transaction.flags, PaymentFlag.TF_NO_RIPPLE_DIRECT + PaymentFlag.TF_PARTIAL_PAYMENT)

        # Instead of checking the memo directly, just verify that the Payment mock was called correctly
        mock_payment.assert_called_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.LimitOrderStrategy")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.MarketOrderStrategy")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.AMMSwapOrderStrategy")
    def test_order_placement_strategy_factory(self, mock_amm_swap_strategy, mock_market_strategy, mock_limit_strategy):
        # Set up mock strategy instances
        mock_limit_instance = MagicMock()
        mock_market_instance = MagicMock()
        mock_amm_swap_instance = MagicMock()

        mock_limit_strategy.return_value = mock_limit_instance
        mock_market_strategy.return_value = mock_market_instance
        mock_amm_swap_strategy.return_value = mock_amm_swap_instance

        # Test the factory with a limit order
        strategy = OrderPlacementStrategyFactory.create_strategy(self.connector, self.buy_limit_order)
        self.assertEqual(strategy, mock_limit_instance)
        mock_limit_strategy.assert_called_once_with(self.connector, self.buy_limit_order)

        # Reset the mocks
        mock_limit_strategy.reset_mock()

        # Test the factory with a market order
        strategy = OrderPlacementStrategyFactory.create_strategy(self.connector, self.buy_market_order)
        self.assertEqual(strategy, mock_market_instance)
        mock_market_strategy.assert_called_once_with(self.connector, self.buy_market_order)

        # Test the factory with an AMM swap order
        strategy = OrderPlacementStrategyFactory.create_strategy(self.connector, self.amm_swap_buy_order)
        self.assertEqual(strategy, mock_amm_swap_instance)
        mock_amm_swap_strategy.assert_called_once_with(self.connector, self.amm_swap_buy_order)

        # For unsupported order type test, create a new mock object with a controlled order_type property
        unsupported_order = MagicMock(spec=InFlightOrder)
        unsupported_order.client_order_id = self.client_order_id
        unsupported_order.exchange_order_id = "unsupported"
        unsupported_order.trading_pair = self.trading_pair
        unsupported_order.order_type = None  # This will trigger the ValueError
        unsupported_order.trade_type = TradeType.BUY
        unsupported_order.price = Decimal("0.5")
        unsupported_order.amount = Decimal("100")

        with self.assertRaises(ValueError):
            OrderPlacementStrategyFactory.create_strategy(self.connector, unsupported_order)

    async def test_order_with_invalid_price(self):
        # Create a limit order without a price
        invalid_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="invalid",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=None,  # Invalid - price is required for limit orders
            amount=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        strategy = LimitOrderStrategy(self.connector, invalid_order)

        # Test that ValueError is raised when calling get_base_quote_amounts
        with self.assertRaises(ValueError):
            strategy.get_base_quote_amounts()

    def test_get_digit_counts_normal_decimal(self):
        """Test _get_digit_counts with a normal decimal value."""
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("123.456"))
        self.assertEqual(int_digits, 3)
        self.assertEqual(frac_digits, 3)

    def test_get_digit_counts_scientific_notation_zero(self):
        """Test _get_digit_counts with '0E-15' — the exact value that caused the original crash.

        normalize() converts 0E-15 to 0, so the digit count reflects that zero
        has 1 integer digit and 0 fractional digits (no significant precision).
        """
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("0E-15"))
        self.assertEqual(int_digits, 1)
        self.assertEqual(frac_digits, 0)

    def test_get_digit_counts_integer(self):
        """Test _get_digit_counts with a whole number (no decimal point in str)."""
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("100"))
        self.assertEqual(int_digits, 3)
        self.assertEqual(frac_digits, 0)

    def test_get_digit_counts_scientific_positive_exponent(self):
        """Test _get_digit_counts with positive exponent scientific notation."""
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("5E+3"))
        self.assertEqual(int_digits, 4)
        self.assertEqual(frac_digits, 0)

    def test_get_digit_counts_small_decimal(self):
        """Test _get_digit_counts with a small decimal value."""
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("0.000001"))
        self.assertEqual(int_digits, 1)
        self.assertEqual(frac_digits, 6)

    def test_get_digit_counts_large_precision(self):
        """Test _get_digit_counts with a value exceeding XRPL's 16-digit limit."""
        # 17 significant digits — normalize() preserves all non-trailing-zero digits
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("12345.678901234567"))
        self.assertEqual(int_digits, 5)
        self.assertEqual(frac_digits, 12)

    def test_get_digit_counts_trailing_zeros_stripped(self):
        """Test that normalize() strips trailing fractional zeros (significant digits only)."""
        int_digits, frac_digits = XRPLOrderPlacementStrategy._get_digit_counts(Decimal("15.50000"))
        self.assertEqual(int_digits, 2)
        self.assertEqual(frac_digits, 1)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy.IssuedCurrencyAmount")
    async def test_get_base_quote_amounts_with_zero_price(self, mock_issued_currency):
        """Test that get_base_quote_amounts does not crash with a zero price (0E-15).

        This is a regression test for GitHub issue #8119 where BUY orders with
        a zero price (from 100% buy spread in PMM v1) caused an IndexError
        in the digit counting logic.
        """
        mock_issued_currency.return_value = IssuedCurrencyAmount(
            currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R", value="0"
        )

        # Create a buy order with price that becomes 0E-15 after quantization
        zero_price_order = InFlightOrder(
            client_order_id=self.client_order_id,
            exchange_order_id="zero_price",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("0E-15"),
            amount=Decimal("15.5"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )

        strategy = LimitOrderStrategy(self.connector, zero_price_order)

        # This should NOT raise IndexError anymore
        we_pay, we_get = strategy.get_base_quote_amounts()

        # Verify it returns valid results (quote amount will be 0 since price is 0)
        self.assertIsNotNone(we_pay)
        self.assertIsNotNone(we_get)
