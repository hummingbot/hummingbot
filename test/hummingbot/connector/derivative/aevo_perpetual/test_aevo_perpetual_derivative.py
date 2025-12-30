import unittest
from unittest.mock import MagicMock
import test.hummingbot.connector.derivative.aevo_perpetual.mock_utils as mock_utils
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative

class AevoPerpetualDerivativeTest(unittest.TestCase):
    def test_instantiation(self):
        # Mock dependencies
        aevo = AevoPerpetualDerivative(
            aevo_perpetual_api_key="test_key",
            aevo_perpetual_api_secret="test_secret",
            trading_pairs=["ETH-USD"],
            trading_required=True
        )
        self.assertIsInstance(aevo, AevoPerpetualDerivative)
