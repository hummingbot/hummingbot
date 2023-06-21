import inspect
import unittest
from enum import Enum

from _decimal import Decimal
from pydantic import BaseModel, ValidationError

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types import cat_api_v3_order_types

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import *
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import (
    CoinbaseAdvancedOrderTypeError,
    CoinbaseAdvancedTradeAPIOrderConfiguration,
    CoinbaseAdvancedTradeLimitGTCOrderType,
    CoinbaseAdvancedTradeOrderType,
    _coinbase_advanced_trade_order_types_annotations,
    create_coinbase_advanced_trade_order_type_members,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_class_validation_from_json_docstring import (
    ClassValidationFromJsonDocstring,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_collect_pydantic_class_annotations import (
    collect_pydantic_class_annotations,
)
from hummingbot.core.data_type.common import OrderType


class TestCreateCoinbaseAdvancedTradeOrderTypeMembers(unittest.TestCase):
    @create_coinbase_advanced_trade_order_type_members
    class CoinbaseAdvancedTradeOrderType(Enum):
        pass

    def test_member_mapping(self):
        # Test if the members of CoinbaseAdvancedTradeOrderType have the correct corresponding values from OrderType
        self.assertEqual(self.CoinbaseAdvancedTradeOrderType.MARKET_IOC, OrderType.MARKET)
        self.assertEqual(self.CoinbaseAdvancedTradeOrderType.LIMIT_GTC, OrderType.LIMIT)
        self.assertEqual(self.CoinbaseAdvancedTradeOrderType.LIMIT_MAKER_GTC, OrderType.LIMIT_MAKER)

    def test_additional_members(self):
        # Test if the additional members have been correctly added to CoinbaseAdvancedTradeOrderType
        additional_members = ["LIMIT_GTD", "STOP_LIMIT_GTC", "STOP_LIMIT_GTD", "LIMIT_MAKER_GTD"]
        for member_name in additional_members:
            self.assertTrue(hasattr(self.CoinbaseAdvancedTradeOrderType, member_name))

    def test_auto_generated_values(self):
        # Test if the auto-generated values have been assigned to the members that don't have corresponding names in
        # OrderType
        auto_generated_members = ["STOP_LIMIT_GTC", "STOP_LIMIT_GTD", "LIMIT_MAKER_GTD"]
        for member_name in auto_generated_members:
            self.assertNotEqual(getattr(self.CoinbaseAdvancedTradeOrderType, member_name),
                                getattr(OrderType, member_name, None))


class TestPydanticForJsonAllowExtra(unittest.TestCase):
    @staticmethod
    def get_sample_json_for_class(class_obj):
        # Assuming your class objects have some method to generate a sample JSON
        # You need to implement this function
        return class_obj.dict_sample_from_json_docstring()

    def test_class_fields_exist_in_annotations(self):
        for class_under_test in classes_under_test:
            sample_json = self.get_sample_json_for_class(class_under_test)
            for field in sample_json:
                self.assertIn(field, _coinbase_advanced_trade_order_types_annotations,
                              f"{field} not found in _annotations for {class_under_test.__name__}")

    def test_no_extra_field_in_json(self):
        for class_under_test in classes_under_test:
            sample_json = self.get_sample_json_for_class(class_under_test)
            self.assertTrue(set(sample_json.keys()).issubset(_coinbase_advanced_trade_order_types_annotations.keys()),
                            f"Extra field in sample_json for {class_under_test.__name__}")

    def test_collect_annotations(self):
        from hummingbot.connector.exchange.coinbase_advanced_trade import cat_data_types

        annotations = collect_pydantic_class_annotations(cat_api_v3_order_types, CoinbaseAdvancedTradeOrderType)
        # you can assert that annotations dictionary is not empty
        self.assertNotEqual(annotations, {})

        # For each class in the module, check if it's in the annotations dictionary
        for name, obj in inspect.getmembers(cat_data_types):
            if (
                    inspect.isclass(obj) and
                    issubclass(obj, BaseModel) and
                    issubclass(obj, CoinbaseAdvancedTradeOrderType) and
                    obj != BaseModel
            ):
                self.assertIn(name, annotations)


class TestCoinbaseAdvancedTradeAPIOrderConfiguration(unittest.TestCase):

    def test_limit_gtc_configuration(self):
        # Create Limit GTC order configuration
        CoinbaseAdvancedTradeLimitGTCOrderType(
            base_size="0.001",
            limit_price="10000.00",
            post_only=False
        )

        # Create the API Order Configuration with Limit GTC order configuration
        api_order_config = CoinbaseAdvancedTradeAPIOrderConfiguration.create(
            OrderType.LIMIT,
            base_size="0.001",
            limit_price="10000.00",
            post_only=False
        )

        self.assertIsInstance(api_order_config.order_type, CoinbaseAdvancedTradeLimitGTCOrderType)

    def test_invalid_configuration(self):
        # Try to assign invalid configuration
        with self.assertRaises(ValidationError):
            CoinbaseAdvancedTradeAPIOrderConfiguration(order_type="Invalid")

    def test_create_order_type_market(self):
        market_order = CoinbaseAdvancedTradeAPIOrderConfiguration.create(
            OrderType.MARKET, quote_size=Decimal("10.00"), base_size=Decimal("0.001")
        )
        self.assertEqual(market_order.market_market_ioc.quote_size, "10.00")
        self.assertEqual(market_order.market_market_ioc.base_size, "0.001")
        self.assertIsNone(market_order.limit_limit_gtc)
        self.assertIsNone(market_order.limit_limit_gtd)
        self.assertIsNone(market_order.stop_limit_stop_limit_gtc)
        self.assertIsNone(market_order.stop_limit_stop_limit_gtd)

    def test_create_order_type_limit(self):
        limit_order = CoinbaseAdvancedTradeAPIOrderConfiguration.create(
            OrderType.LIMIT, base_size=Decimal("0.001"), limit_price=Decimal("10000.00"), post_only=False
        )
        self.assertEqual(limit_order.limit_limit_gtc.base_size, "0.001")
        self.assertEqual(limit_order.limit_limit_gtc.limit_price, "10000.00")
        self.assertEqual(limit_order.limit_limit_gtc.post_only, False)
        self.assertIsNone(limit_order.market_market_ioc)
        self.assertIsNone(limit_order.limit_limit_gtd)
        self.assertIsNone(limit_order.stop_limit_stop_limit_gtc)
        self.assertIsNone(limit_order.stop_limit_stop_limit_gtd)

    def test_unsupported_order_type(self):
        with self.assertRaises(CoinbaseAdvancedOrderTypeError):
            CoinbaseAdvancedTradeAPIOrderConfiguration.create(
                5, quote_size=Decimal("10.00"), base_size=Decimal("0.001")
            )

    def test_order_type_property(self):
        limit_order = CoinbaseAdvancedTradeAPIOrderConfiguration.create(
            OrderType.LIMIT, base_size=Decimal("0.001"), limit_price=Decimal("10000.00"), post_only=False
        )
        self.assertEqual(limit_order.order_type.base_size, "0.001")
        self.assertEqual(limit_order.order_type.limit_price, "10000.00")
        self.assertEqual(limit_order.order_type.post_only, False)


# List of classes you want to test
classes_under_test = [CoinbaseAdvancedTradeOrderType.get_registry()[key] for key in
                      CoinbaseAdvancedTradeOrderType.get_registry().keys()]

# classes_under_test = [CoinbaseAdvancedTradeOrderTypeError]
# Dynamically create a subclass for each class you want to test
for class_under_test in classes_under_test:
    name = f"Test{class_under_test.__name__}"
    globals()[name] = type(name, (ClassValidationFromJsonDocstring.TestSuite,), {"class_under_test": class_under_test})

if __name__ == "__main__":
    unittest.main()
