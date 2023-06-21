import unittest

from pydantic import BaseModel

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeErrorResponse,
    CoinbaseAdvancedTradeGetAccountResponse,
    CoinbaseAdvancedTradeGetProductResponse,
    CoinbaseAdvancedTradeResponse,
    is_product_tradable,
    is_valid_account,
)

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import *
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_class_validation_from_json_docstring import (
    ClassValidationFromJsonDocstring,
)
from hummingbot.core.utils.class_registry import ClassRegistry


class TestClassRegistrySubclassing(unittest.TestCase):
    """
    This test is redundant with respect to the tests in ClassRegistry, but it is here to ensure that the
    key attributes of the ClassRegistry as used in Response classes is working as intended.
    """

    def test_class_registration(self):
        class MockPrefixResponse(ClassRegistry):
            pass

        class MockPrefixTestResponse(BaseModel, MockPrefixResponse):
            field1: str
            field2: int

        # Test that the class is registered with both the full name and the shortened name
        self.assertIn('MockPrefixTestResponse', MockPrefixResponse.get_registry())
        self.assertIn('Test', MockPrefixResponse.get_registry())
        self.assertEqual(MockPrefixResponse.get_registry()['Test'], MockPrefixTestResponse)
        self.assertEqual(MockPrefixResponse.get_registry()['MockPrefixTestResponse'], MockPrefixTestResponse)
        self.assertEqual(ClassRegistry.get_registry()[MockPrefixResponse]['Test'], MockPrefixTestResponse)
        self.assertEqual(ClassRegistry.get_registry()[MockPrefixResponse]['MockPrefixTestResponse'],
                         MockPrefixTestResponse)

    def test_basemodel_features(self):
        class MockPrefixResponse(ClassRegistry):
            pass

        class MockPrefixTestResponse(BaseModel, MockPrefixResponse):
            field1: str
            field2: int

        # Test namedtuple features
        instance = MockPrefixTestResponse(**{'field1': 'value1', 'field2': 2})
        self.assertIsInstance(instance, MockPrefixResponse)
        self.assertEqual(instance.field1, 'value1')
        self.assertEqual(instance.field2, 2)
        self.assertEqual({'field1': 'value1', 'field2': 2}, instance.dict(), )
        self.assertIn('MockPrefixTestResponse', MockPrefixResponse.get_registry())
        self.assertIn('Test', MockPrefixResponse.get_registry())
        self.assertEqual(MockPrefixResponse.get_registry()['Test'], MockPrefixTestResponse)
        self.assertEqual(MockPrefixResponse.get_registry()['MockPrefixTestResponse'], MockPrefixTestResponse)
        self.assertEqual(ClassRegistry.get_registry()[MockPrefixResponse]['Test'], MockPrefixTestResponse)
        self.assertEqual(ClassRegistry.get_registry()[MockPrefixResponse]['MockPrefixTestResponse'],
                         MockPrefixTestResponse)


class TestValidProductAccount(unittest.TestCase):

    def test_is_product_tradable(self):
        test_substitutes = {
            "product_type": "SPOT",
            "trading_disabled": False,
            "is_disabled": False,
            "cancel_only": False,
            "limit_only": False,
            "post_only": False,
            "auction_mode": False
        }
        valid_product = CoinbaseAdvancedTradeGetProductResponse.dict_sample_from_json_docstring(test_substitutes)
        self.assertTrue(is_product_tradable(CoinbaseAdvancedTradeGetProductResponse(**valid_product)))

        test_substitutes = {
            "product_type": "SPOT",
            "trading_disabled": True,  # Change this to True
            "is_disabled": False,
            "cancel_only": False,
            "limit_only": False,
            "post_only": False,
            "auction_mode": False
        }
        invalid_product = CoinbaseAdvancedTradeGetProductResponse.dict_sample_from_json_docstring(test_substitutes)
        self.assertFalse(is_product_tradable(CoinbaseAdvancedTradeGetProductResponse(**invalid_product)))

    def test_is_valid_account(self):
        test_substitutes = {
            "account": {
                "active": True,
                "type": "ACCOUNT_TYPE_CRYPTO",
                "ready": True,
                # Other fields are omitted for simplicity
            }
        }
        valid_product = CoinbaseAdvancedTradeGetAccountResponse.dict_sample_from_json_docstring(test_substitutes)
        self.assertTrue(is_valid_account(CoinbaseAdvancedTradeGetAccountResponse(**valid_product)))

        test_substitutes = {
            "account": {
                "active": False,
                "type": "ACCOUNT_TYPE_CRYPTO",
                "ready": True,
                # Other fields are omitted for simplicity
            }
        }
        invalid_product = CoinbaseAdvancedTradeGetAccountResponse.dict_sample_from_json_docstring(test_substitutes)
        self.assertFalse(is_valid_account(CoinbaseAdvancedTradeGetAccountResponse(**invalid_product)))


# List of classes you want to test
classes_under_test = [CoinbaseAdvancedTradeResponse.get_registry()[key] for key in
                      CoinbaseAdvancedTradeResponse.get_registry().keys()]

# classes_under_test = [CoinbaseAdvancedTradeCancelOrdersResponse]
# Dynamically create a subclass for each class you want to test
for class_under_test in classes_under_test + [CoinbaseAdvancedTradeErrorResponse]:
    name = f"Test{class_under_test.__name__}"
    globals()[name] = type(name, (ClassValidationFromJsonDocstring.TestSuite,), {"class_under_test": class_under_test})

if __name__ == "__main__":
    unittest.main()
