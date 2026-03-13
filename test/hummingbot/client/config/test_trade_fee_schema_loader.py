import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from hummingbot.client.config.trade_fee_schema_loader import TradeFeeSchemaLoader
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class TestTradeFeeSchemaLoader(unittest.TestCase):

    @patch("hummingbot.client.config.trade_fee_schema_loader.AllConnectorSettings")
    @patch("hummingbot.client.config.trade_fee_schema_loader.fee_overrides_config_map")
    def test_configured_schema_with_maker_fee_override(self, mock_fee_overrides, mock_all_connector_settings):
        # Setup mock connector settings
        mock_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.001"),
            taker_percent_fee_decimal=Decimal("0.002"),
            buy_percent_fee_deducted_from_returns=False
        )
        mock_all_connector_settings.get_connector_settings.return_value = {
            "test_exchange": MagicMock(trade_fee_schema=mock_schema)
        }

        # Setup fee override with maker percent fee (covers line 31)
        mock_maker_config = MagicMock()
        mock_maker_config.value = Decimal("0.5")  # 0.5%
        mock_fee_overrides.get.side_effect = lambda key: {
            "test_exchange_maker_percent_fee": mock_maker_config
        }.get(key)

        # Call the method
        result = TradeFeeSchemaLoader.configured_schema_for_exchange("test_exchange")

        # Assert the maker fee was overridden
        self.assertEqual(result.maker_percent_fee_decimal, Decimal("0.005"))  # 0.5% = 0.005
        self.assertEqual(result.taker_percent_fee_decimal, Decimal("0.002"))  # unchanged

    @patch("hummingbot.client.config.trade_fee_schema_loader.AllConnectorSettings")
    @patch("hummingbot.client.config.trade_fee_schema_loader.fee_overrides_config_map")
    def test_configured_schema_with_taker_fee_override(self, mock_fee_overrides, mock_all_connector_settings):
        # Setup mock connector settings
        mock_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.001"),
            taker_percent_fee_decimal=Decimal("0.002"),
            buy_percent_fee_deducted_from_returns=False
        )
        mock_all_connector_settings.get_connector_settings.return_value = {
            "test_exchange": MagicMock(trade_fee_schema=mock_schema)
        }

        # Setup fee override with taker percent fee (covers line 35)
        mock_taker_config = MagicMock()
        mock_taker_config.value = Decimal("0.75")  # 0.75%
        mock_fee_overrides.get.side_effect = lambda key: {
            "test_exchange_taker_percent_fee": mock_taker_config
        }.get(key)

        # Call the method
        result = TradeFeeSchemaLoader.configured_schema_for_exchange("test_exchange")

        # Assert the taker fee was overridden
        self.assertEqual(result.maker_percent_fee_decimal, Decimal("0.001"))  # unchanged
        self.assertEqual(result.taker_percent_fee_decimal, Decimal("0.0075"))  # 0.75% = 0.0075

    @patch("hummingbot.client.config.trade_fee_schema_loader.AllConnectorSettings")
    @patch("hummingbot.client.config.trade_fee_schema_loader.fee_overrides_config_map")
    def test_configured_schema_with_buy_percent_fee_override(self, mock_fee_overrides, mock_all_connector_settings):
        # Setup mock connector settings
        mock_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.001"),
            taker_percent_fee_decimal=Decimal("0.002"),
            buy_percent_fee_deducted_from_returns=False
        )
        mock_all_connector_settings.get_connector_settings.return_value = {
            "test_exchange": MagicMock(trade_fee_schema=mock_schema)
        }

        # Setup fee override with buy percent fee deducted (covers line 39)
        mock_buy_config = MagicMock()
        mock_buy_config.value = True
        mock_fee_overrides.get.side_effect = lambda key: {
            "test_exchange_buy_percent_fee_deducted_from_returns": mock_buy_config
        }.get(key)

        # Call the method
        result = TradeFeeSchemaLoader.configured_schema_for_exchange("test_exchange")

        # Assert the buy percent fee deducted was overridden
        self.assertEqual(result.buy_percent_fee_deducted_from_returns, True)
        self.assertEqual(result.maker_percent_fee_decimal, Decimal("0.001"))  # unchanged
        self.assertEqual(result.taker_percent_fee_decimal, Decimal("0.002"))  # unchanged

    @patch("hummingbot.client.config.trade_fee_schema_loader.AllConnectorSettings")
    @patch("hummingbot.client.config.trade_fee_schema_loader.fee_overrides_config_map")
    def test_configured_schema_with_all_overrides(self, mock_fee_overrides, mock_all_connector_settings):
        # Setup mock connector settings
        mock_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.001"),
            taker_percent_fee_decimal=Decimal("0.002"),
            buy_percent_fee_deducted_from_returns=False
        )
        mock_all_connector_settings.get_connector_settings.return_value = {
            "test_exchange": MagicMock(trade_fee_schema=mock_schema)
        }

        # Setup all fee overrides (covers lines 31, 35, 39)
        mock_maker_config = MagicMock(value=Decimal("0.5"))
        mock_taker_config = MagicMock(value=Decimal("0.75"))
        mock_buy_config = MagicMock(value=True)

        def get_side_effect(key):
            return {
                "test_exchange_maker_percent_fee": mock_maker_config,
                "test_exchange_taker_percent_fee": mock_taker_config,
                "test_exchange_buy_percent_fee_deducted_from_returns": mock_buy_config
            }.get(key)

        mock_fee_overrides.get.side_effect = get_side_effect

        # Call the method
        result = TradeFeeSchemaLoader.configured_schema_for_exchange("test_exchange")

        # Assert all overrides were applied
        self.assertEqual(result.maker_percent_fee_decimal, Decimal("0.005"))  # 0.5% = 0.005
        self.assertEqual(result.taker_percent_fee_decimal, Decimal("0.0075"))  # 0.75% = 0.0075
        self.assertEqual(result.buy_percent_fee_deducted_from_returns, True)

    @patch("hummingbot.client.config.trade_fee_schema_loader.AllConnectorSettings")
    def test_invalid_connector_raises_exception(self, mock_all_connector_settings):
        mock_all_connector_settings.get_connector_settings.return_value = {}

        with self.assertRaises(Exception) as context:
            TradeFeeSchemaLoader.configured_schema_for_exchange("invalid_exchange")

        self.assertIn("Invalid connector", str(context.exception))
        self.assertIn("invalid_exchange", str(context.exception))
