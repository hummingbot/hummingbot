import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.core.data_type.order_book import OrderBook


class TestBinanceExchangeGetPrice(unittest.TestCase):
    """Test cases for BinanceExchange.get_price fix"""

    def setUp(self):
        self.exchange = BinanceExchange(
            binance_api_key="test_key",
            binance_api_secret="test_secret",
            trading_pairs=["BTC-USDT", "ETH-USDT"]
        )

    def test_get_price_with_valid_order_book(self):
        """Test get_price returns correct price when order book exists"""
        # Mock order book
        mock_order_book = MagicMock(spec=OrderBook)
        mock_order_book.get_price.return_value = 50000.0
        
        # Mock order_book_tracker
        self.exchange._order_book_tracker = MagicMock()
        self.exchange._order_book_tracker.order_books = {"BTC-USDT": mock_order_book}
        
        # Test get_price
        price = self.exchange.get_price("BTC-USDT", True)
        
        self.assertEqual(price, Decimal("50000.0"))
        mock_order_book.get_price.assert_called_once_with(True)

    def test_get_price_with_missing_order_book(self):
        """Test get_price handles missing order book gracefully"""
        # Mock empty order books
        self.exchange._order_book_tracker = MagicMock()
        self.exchange._order_book_tracker.order_books = {}
        
        # Mock trading_pair_symbol_map_ready
        self.exchange._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT"}
        
        # Test get_price returns NaN for missing order book
        price = self.exchange.get_price("BTC-USDT", True)
        
        self.assertTrue(price.is_nan())

    def test_get_price_with_invalid_trading_pair(self):
        """Test get_price handles invalid trading pair gracefully"""
        # Mock empty order books
        self.exchange._order_book_tracker = MagicMock()
        self.exchange._order_book_tracker.order_books = {}
        
        # Test get_price returns NaN for invalid pair
        price = self.exchange.get_price("INVALID-PAIR", True)
        
        self.assertTrue(price.is_nan())

    def test_get_price_uses_parent_implementation(self):
        """Test that get_price tries parent implementation first"""
        with patch.object(BinanceExchange.__bases__[0], 'get_price', return_value=Decimal("45000.0")) as mock_parent:
            price = self.exchange.get_price("BTC-USDT", False)
            
            mock_parent.assert_called_once_with("BTC-USDT", False)
            self.assertEqual(price, Decimal("45000.0"))


if __name__ == '__main__':
    unittest.main()
