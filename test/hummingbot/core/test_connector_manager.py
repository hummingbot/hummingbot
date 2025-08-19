from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.connector_manager import ConnectorManager


class ConnectorManagerTest(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create mock client config
        self.client_config = ClientConfigMap()
        self.client_config_adapter = ClientConfigAdapter(self.client_config)

        # Set up paper trade config
        self.client_config.paper_trade.paper_trade_account_balance = {
            "BTC": Decimal("1.0"),
            "USDT": Decimal("10000.0")
        }

        # Create connector manager instance
        self.connector_manager = ConnectorManager(self.client_config_adapter)

        # Create mock connector
        self.mock_connector = Mock(spec=ExchangeBase)
        self.mock_connector.name = "binance"
        self.mock_connector.ready = True
        self.mock_connector.trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.mock_connector.limit_orders = []
        self.mock_connector.get_balance.return_value = Decimal("1.0")
        self.mock_connector.get_all_balances.return_value = {
            "BTC": Decimal("1.0"),
            "USDT": Decimal("10000.0")
        }
        self.mock_connector.get_order_book.return_value = MagicMock()
        # Mock async method cancel_all
        self.mock_connector.cancel_all = AsyncMock(return_value=None)
        self.mock_connector.stop.return_value = None
        # Add set_balance method for paper trade tests
        self.mock_connector.set_balance = Mock()

    def test_init(self):
        """Test initialization of ConnectorManager"""
        manager = ConnectorManager(self.client_config_adapter)

        self.assertEqual(manager.client_config_map, self.client_config_adapter)
        self.assertEqual(manager.connectors, {})

    @patch("hummingbot.core.connector_manager.create_paper_trade_market")
    def test_create_paper_trade_connector(self, mock_create_paper_trade):
        """Test creating a paper trade connector"""
        # Set up mock
        mock_create_paper_trade.return_value = self.mock_connector

        # Create paper trade connector
        connector = self.connector_manager.create_connector(
            "binance_paper_trade",
            ["BTC-USDT", "ETH-USDT"],
            trading_required=True
        )

        # Verify connector was created correctly
        self.assertEqual(connector, self.mock_connector)
        self.assertIn("binance_paper_trade", self.connector_manager.connectors)
        self.assertEqual(self.connector_manager.connectors["binance_paper_trade"], self.mock_connector)

        # Verify paper trade market was called with correct params
        mock_create_paper_trade.assert_called_once_with(
            "binance",
            ["BTC-USDT", "ETH-USDT"]
        )

        # Verify balances were set
        self.mock_connector.set_balance.assert_any_call("BTC", Decimal("1.0"))
        self.mock_connector.set_balance.assert_any_call("USDT", Decimal("10000.0"))

    @patch("hummingbot.core.connector_manager.get_connector_class")
    @patch("hummingbot.core.connector_manager.Security")
    @patch("hummingbot.core.connector_manager.AllConnectorSettings")
    def test_create_live_connector(self, mock_settings, mock_security, mock_get_class):
        """Test creating a live connector"""
        # Set up mocks
        mock_api_keys = {"api_key": "test_key", "api_secret": "test_secret"}
        mock_security.api_keys.return_value = mock_api_keys

        mock_conn_setting = Mock()
        mock_conn_setting.conn_init_parameters.return_value = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "trading_pairs": ["BTC-USDT"],
            "trading_required": True
        }
        mock_settings.get_connector_settings.return_value = {"binance": mock_conn_setting}

        mock_connector_class = Mock(return_value=self.mock_connector)
        mock_get_class.return_value = mock_connector_class

        # Create live connector
        connector = self.connector_manager.create_connector(
            "binance",
            ["BTC-USDT"],
            trading_required=True
        )

        # Verify connector was created correctly
        self.assertEqual(connector, self.mock_connector)
        self.assertIn("binance", self.connector_manager.connectors)

        # Verify methods were called correctly
        mock_security.api_keys.assert_called_once_with("binance")
        mock_conn_setting.conn_init_parameters.assert_called_once()
        mock_connector_class.assert_called_once()

    @patch("hummingbot.core.connector_manager.Security")
    def test_create_live_connector_no_api_keys(self, mock_security):
        """Test creating a live connector without API keys raises error"""
        mock_security.api_keys.return_value = None

        with self.assertRaises(ValueError) as context:
            self.connector_manager.create_connector(
                "binance",
                ["BTC-USDT"],
                trading_required=True
            )

        self.assertIn("API keys required", str(context.exception))

    def test_create_existing_connector(self):
        """Test creating a connector that already exists returns existing one"""
        # Add connector to manager
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Try to create again
        connector = self.connector_manager.create_connector(
            "binance",
            ["BTC-USDT"],
            trading_required=True
        )

        # Should return existing connector
        self.assertEqual(connector, self.mock_connector)
        self.assertEqual(len(self.connector_manager.connectors), 1)

    async def test_remove_connector(self):
        """Test removing a connector"""
        # Add connector
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Remove connector
        result = self.connector_manager.remove_connector("binance")

        # Verify removal
        self.assertTrue(result)
        self.assertNotIn("binance", self.connector_manager.connectors)

    async def test_remove_nonexistent_connector(self):
        """Test removing a connector that doesn't exist"""
        result = self.connector_manager.remove_connector("nonexistent")

        self.assertFalse(result)

    @patch.object(ConnectorManager, "remove_connector")
    @patch.object(ConnectorManager, "create_connector")
    async def test_add_trading_pairs(self, mock_create, mock_remove):
        """Test adding trading pairs to existing connector"""
        # Set up
        mock_remove.return_value = True
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Add trading pairs
        result = await self.connector_manager.add_trading_pairs(
            "binance",
            ["XRP-USDT", "ADA-USDT"]
        )

        # Verify
        self.assertTrue(result)
        mock_remove.assert_called_once_with("binance")
        # Check that create was called with correct connector name
        call_args = mock_create.call_args
        self.assertEqual(call_args[0][0], "binance")
        # Check that all expected pairs are present (order doesn't matter due to set)
        actual_pairs = set(call_args[0][1])
        expected_pairs = {"BTC-USDT", "ETH-USDT", "XRP-USDT", "ADA-USDT"}
        self.assertEqual(actual_pairs, expected_pairs)

    async def test_add_trading_pairs_nonexistent_connector(self):
        """Test adding trading pairs to nonexistent connector"""
        result = await self.connector_manager.add_trading_pairs(
            "nonexistent",
            ["BTC-USDT"]
        )

        self.assertFalse(result)

    def test_get_connector(self):
        """Test getting a connector by name"""
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Get existing connector
        connector = self.connector_manager.get_connector("binance")
        self.assertEqual(connector, self.mock_connector)

        # Get nonexistent connector
        connector = self.connector_manager.get_connector("nonexistent")
        self.assertIsNone(connector)

    def test_get_all_connectors(self):
        """Test getting all connectors"""
        # Add multiple connectors
        mock_connector2 = Mock(spec=ExchangeBase)
        self.connector_manager.connectors["binance"] = self.mock_connector
        self.connector_manager.connectors["kucoin"] = mock_connector2

        all_connectors = self.connector_manager.get_all_connectors()

        # Verify we get a copy
        self.assertEqual(len(all_connectors), 2)
        self.assertIn("binance", all_connectors)
        self.assertIn("kucoin", all_connectors)
        self.assertIsNot(all_connectors, self.connector_manager.connectors)

    def test_get_order_book(self):
        """Test getting order book"""
        self.connector_manager.connectors["binance"] = self.mock_connector
        mock_order_book = MagicMock()
        self.mock_connector.get_order_book.return_value = mock_order_book

        # Get order book
        order_book = self.connector_manager.get_order_book("binance", "BTC-USDT")

        self.assertEqual(order_book, mock_order_book)
        self.mock_connector.get_order_book.assert_called_once_with("BTC-USDT")

        # Get order book for nonexistent connector
        order_book = self.connector_manager.get_order_book("nonexistent", "BTC-USDT")
        self.assertIsNone(order_book)

    def test_get_balance(self):
        """Test getting balance for an asset"""
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Get balance
        balance = self.connector_manager.get_balance("binance", "BTC")

        self.assertEqual(balance, Decimal("1.0"))
        self.mock_connector.get_balance.assert_called_once_with("BTC")

        # Get balance for nonexistent connector
        balance = self.connector_manager.get_balance("nonexistent", "BTC")
        self.assertEqual(balance, 0.0)

    def test_get_all_balances(self):
        """Test getting all balances"""
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Get all balances
        balances = self.connector_manager.get_all_balances("binance")

        self.assertEqual(balances["BTC"], Decimal("1.0"))
        self.assertEqual(balances["USDT"], Decimal("10000.0"))
        self.mock_connector.get_all_balances.assert_called_once()

        # Get balances for nonexistent connector
        balances = self.connector_manager.get_all_balances("nonexistent")
        self.assertEqual(balances, {})

    def test_get_status(self):
        """Test getting status of all connectors"""
        # Add multiple connectors
        mock_connector2 = Mock(spec=ExchangeBase)
        mock_connector2.ready = False
        mock_connector2.trading_pairs = ["ETH-BTC"]
        mock_connector2.limit_orders = [Mock()]
        mock_connector2.get_all_balances.return_value = {}

        self.connector_manager.connectors["binance"] = self.mock_connector
        self.connector_manager.connectors["kucoin"] = mock_connector2

        # Get status
        status = self.connector_manager.get_status()

        # Verify status structure
        self.assertIn("binance", status)
        self.assertIn("kucoin", status)

        # Check binance status
        self.assertTrue(status["binance"]["ready"])
        self.assertEqual(status["binance"]["trading_pairs"], ["BTC-USDT", "ETH-USDT"])
        self.assertEqual(status["binance"]["orders_count"], 0)
        self.assertEqual(status["binance"]["balances"]["BTC"], Decimal("1.0"))

        # Check kucoin status
        self.assertFalse(status["kucoin"]["ready"])
        self.assertEqual(status["kucoin"]["trading_pairs"], ["ETH-BTC"])
        self.assertEqual(status["kucoin"]["orders_count"], 1)
        self.assertEqual(status["kucoin"]["balances"], {})

    @patch("hummingbot.core.connector_manager.AllConnectorSettings")
    def test_create_connector_exception_handling(self, mock_settings):
        """Test exception handling in create_connector"""
        # Make settings throw exception
        mock_settings.get_connector_settings.side_effect = Exception("Settings error")

        with self.assertRaises(Exception) as context:
            self.connector_manager.create_connector(
                "binance",
                ["BTC-USDT"],
                trading_required=True
            )

        self.assertIn("Settings error", str(context.exception))
        # Connector should not be added
        self.assertNotIn("binance", self.connector_manager.connectors)

    @patch("hummingbot.core.connector_manager.AllConnectorSettings")
    def test_is_gateway_market(self, mock_settings):
        """Test is_gateway_market static method"""
        # Test with gateway market
        mock_settings.get_gateway_amm_connector_names.return_value = {"jupiter_solana_mainnet-beta"}
        self.assertTrue(ConnectorManager.is_gateway_market("jupiter_solana_mainnet-beta"))

        # Test with non-gateway market
        self.assertFalse(ConnectorManager.is_gateway_market("binance"))
        self.assertFalse(ConnectorManager.is_gateway_market("kucoin"))

    async def test_update_connector_balances(self):
        """Test update_connector_balances method"""
        # Add mock connector with _update_balances method
        mock_update_balances = AsyncMock()
        self.mock_connector._update_balances = mock_update_balances
        self.connector_manager.connectors["binance"] = self.mock_connector

        # Update balances for existing connector
        await self.connector_manager.update_connector_balances("binance")

        # Verify _update_balances was called
        mock_update_balances.assert_called_once()

    async def test_update_connector_balances_nonexistent(self):
        """Test update_connector_balances with nonexistent connector"""
        # Try to update balances for nonexistent connector
        with self.assertRaises(ValueError) as context:
            await self.connector_manager.update_connector_balances("nonexistent")

        self.assertIn("Connector nonexistent not found", str(context.exception))
