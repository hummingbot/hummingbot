import dataclasses
import json
import unittest
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Dict

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_order_types import (
    CoinbaseAdvancedTradeOrderType,
    LimitGTC,
    LimitGTD,
    LimitMakerGTC,
    LimitMakerGTD,
    MarketMarketIOC,
    Order,
    StopLimitGTC,
    StopLimitGTD,
    coinbase_advanced_trade_order_type_mapping,
    create_coinbase_advanced_trade_order_type_members,
    ignore_dataclass_extra_kwargs,
)
from hummingbot.core.data_type.common import OrderType


class TestIgnoreExtraKwargsOrder(unittest.TestCase):
    def test_correct_order(self):
        try:
            @ignore_dataclass_extra_kwargs
            @dataclasses.dataclass
            class TestClass:
                a: int
                b: int
                c: str = "default"
        except TypeError:
            self.fail("ignore_dataclass_extra_kwargs raised TypeError unexpectedly!")

    def test_incorrect_order(self):
        with self.assertRaises(TypeError):
            @dataclasses.dataclass
            @ignore_dataclass_extra_kwargs
            class TestClass:
                a: int
                b: int
                c: str = "default"


class TestIgnoreExtraKwargs(unittest.TestCase):
    @ignore_dataclass_extra_kwargs
    @dataclasses.dataclass
    class TestClass:
        a: int
        b: int
        c: str = "default"

    def test_no_kwargs(self):
        test_instance = self.TestClass(1, 2)
        self.assertEqual(test_instance.a, 1)
        self.assertEqual(test_instance.b, 2)
        self.assertEqual(test_instance.c, "default")

    def test_valid_kwargs(self):
        test_instance = self.TestClass(1, 2, c="custom")
        self.assertEqual(test_instance.a, 1)
        self.assertEqual(test_instance.b, 2)
        self.assertEqual(test_instance.c, "custom")

    def test_extra_kwargs(self):
        test_instance = self.TestClass(1, 2, c="custom", d=4, e="extra")
        self.assertEqual(test_instance.a, 1)
        self.assertEqual(test_instance.b, 2)
        self.assertEqual(test_instance.c, "custom")

        with self.assertRaises(AttributeError):
            _ = test_instance.d

        with self.assertRaises(AttributeError):
            _ = test_instance.e

    def test_mixed_valid_and_extra_kwargs(self):
        test_instance = self.TestClass(1, 2, c="custom", e="extra")
        self.assertEqual(test_instance.a, 1)
        self.assertEqual(test_instance.b, 2)
        self.assertEqual(test_instance.c, "custom")

        with self.assertRaises(AttributeError):
            _ = test_instance.e

    def test_only_extra_kwargs(self):
        test_instance = self.TestClass(1, 2, d=4, e="extra")
        self.assertEqual(test_instance.a, 1)
        self.assertEqual(test_instance.b, 2)
        self.assertEqual(test_instance.c, "default")

        with self.assertRaises(AttributeError):
            _ = test_instance.d

        with self.assertRaises(AttributeError):
            _ = test_instance.e


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


class TestOrderClasses(unittest.TestCase):
    def test_ignore_extra_kwargs(self):
        # Test if the ignore_dataclass_extra_kwargs decorator works as expected for all classes
        market_ioc = MarketMarketIOC(quote_size="10", base_size="20", extra_arg="extra")
        # limit_gtc = LimitGTC(base_size="20", limit_price="100", extra_arg="extra")
        # limit_maker_gtc = LimitMakerGTC(base_size="20", limit_price="100", extra_arg="extra")
        # limit_gtd = LimitGTD(base_size="20", limit_price="100", end_time="2023-01-01", extra_arg="extra")
        # limit_maker_gtd = LimitMakerGTD(base_size="20", limit_price="100", end_time="2023-01-01", extra_arg="extra")
        # stop_limit_gtc = StopLimitGTC(base_size="20", limit_price="100", stop_price="90", stop_direction="up",
        #                               extra_arg="extra")
        # stop_limit_gtd = StopLimitGTD(base_size="20", limit_price="100", stop_price="90", stop_direction="up",
        #                               end_time="2023-01-01", extra_arg="extra")

        order = Order(
            client_order_id="123",
            product_id="BTC-USD",
            side="buy",
            order_configuration=market_ioc,
        )
        self.assertEqual("123", order.client_order_id)

        with self.assertRaises(TypeError):
            order = Order(
                client_order_id="123",
                product_id="BTC-USD",
                side="buy",
                order_configuration=market_ioc,
                extra_arg="extra"
            )

            _ = order.extra_arg

    def test_class_hierarchy(self):
        # Test if the classes inherit their parent's attributes
        limit_gtc = LimitGTC(base_size="20", limit_price="100")
        self.assertEqual(limit_gtc.post_only, False)

        limit_maker_gtc = LimitMakerGTC(base_size="20", limit_price="100")
        self.assertEqual(limit_maker_gtc.post_only, True)

        stop_limit_gtc = StopLimitGTC(base_size="20", limit_price="100", stop_price="90", stop_direction="up")
        self.assertTrue(hasattr(stop_limit_gtc, "stop_price"))
        self.assertTrue(hasattr(stop_limit_gtc, "stop_direction"))

        stop_limit_gtd = StopLimitGTD(base_size="20", limit_price="100", stop_price="90", stop_direction="up",
                                      end_time="2023-01-01")
        self.assertTrue(hasattr(stop_limit_gtd, "end_time"))

    def _test_frozen_dataclasses(self, cls, attr_name, attr_value, *args, **kwargs):
        instance = cls(*args, **kwargs)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            setattr(instance, attr_name, attr_value)

    def test_frozen_dataclasses(self):
        self._test_frozen_dataclasses(MarketMarketIOC, "quote_size", "15", quote_size="10", base_size="20")
        self._test_frozen_dataclasses(LimitGTC, "base_size", "30", base_size="20", limit_price="100")
        self._test_frozen_dataclasses(LimitMakerGTC, "base_size", "30", base_size="20", limit_price="100")
        self._test_frozen_dataclasses(LimitGTD, "base_size", "30", base_size="20", limit_price="100",
                                      end_time="2023-01-01")
        self._test_frozen_dataclasses(LimitMakerGTD, "base_size", "30", base_size="20", limit_price="100",
                                      end_time="2023-01-01")
        self._test_frozen_dataclasses(StopLimitGTC, "base_size", "30", base_size="20", limit_price="100",
                                      stop_price="90", stop_direction="up")
        self._test_frozen_dataclasses(StopLimitGTD, "base_size", "30", base_size="20", limit_price="100",
                                      stop_price="90", stop_direction="up", end_time="2023-01-01")

    def _test_order_class(self, cls, *args, **kwargs):
        order_config = cls(*args, **kwargs)
        order = Order(
            client_order_id="123",
            product_id="BTC-USD",
            side="buy",
            order_configuration=order_config,
        )
        self.assertIsInstance(order.order_configuration, cls)

    def test_order_class(self):
        self._test_order_class(MarketMarketIOC, quote_size="10", base_size="20")
        self._test_order_class(LimitGTC, base_size="20", limit_price="100")
        self._test_order_class(LimitMakerGTC, base_size="20", limit_price="100")
        self._test_order_class(LimitGTD, base_size="20", limit_price="100", end_time="2023-01-01")
        self._test_order_class(LimitMakerGTD, base_size="20", limit_price="100", end_time="2023-01-01")
        self._test_order_class(StopLimitGTC, base_size="20", limit_price="100", stop_price="90", stop_direction="up")
        self._test_order_class(StopLimitGTD, base_size="20", limit_price="100", stop_price="90", stop_direction="up",
                               end_time="2023-01-01")


class TestCoinbaseAdvancedTradeOrderTypes(unittest.TestCase):
    def setUp(self):
        self.test_data: Dict[str, Dict[str, str]] = {
            "MARKET_IOC": {
                "serialized_json": '{"quote_size": "0.01", "base_size": "0.001"}',
                "deserialized_data": MarketMarketIOC(quote_size="0.01", base_size="0.001"),
            },
            "LIMIT_GTC": {
                "serialized_json": '{"base_size": "0.001", '
                                   '"limit_price": "10000.00", '
                                   '"post_only": false}',
                "deserialized_data": LimitGTC(base_size="0.001", limit_price="10000.00"),
            },
            "LIMIT_MAKER_GTC": {
                "serialized_json": '{"base_size": "0.002", '
                                   '"limit_price": "10000.00", '
                                   '"post_only": true}',
                "deserialized_data": LimitMakerGTC(base_size="0.002", limit_price="10000.00"),
            },
            "LIMIT_GTD": {
                "serialized_json": '{"base_size": "0.001", '
                                   '"limit_price": "10000.00", '
                                   '"post_only": false, '
                                   '"end_time": "2023-05-04T16:17"}',
                "deserialized_data": LimitGTD(base_size="0.001", limit_price="10000.00", end_time="2023-05-04T16:17"),
            },
            "LIMIT_MAKER_GTD": {
                "serialized_json": '{"base_size": "0.001", '
                                   '"limit_price": "10000.00", '
                                   '"post_only": true, '
                                   '"end_time": "2023-05-04T16:17"}',
                "deserialized_data": LimitMakerGTD(base_size="0.001", limit_price="10000.00",
                                                   end_time="2023-05-04T16:17"),
            },
            "STOP_LIMIT_GTC": {
                "serialized_json": '{'
                                   '"base_size": "0.001",'
                                   '"limit_price": "10000.00",'
                                   '"stop_price": "9500.00",'
                                   '"stop_direction": "STOP_DIRECTION_STOP_UP"}',
                "deserialized_data": StopLimitGTC(base_size="0.001", limit_price="10000.00", stop_price="9500.00",
                                                  stop_direction="STOP_DIRECTION_STOP_UP"),
            },
            "STOP_LIMIT_GTD": {
                "serialized_json": '{'
                                   '"base_size": "0.001",'
                                   '"limit_price": "10000.00",'
                                   '"stop_price": "9500.00",'
                                   '"end_time": "2023-05-04T16:17",'
                                   '"stop_direction": "STOP_DIRECTION_STOP_DOWN"}',
                "deserialized_data": StopLimitGTD(base_size="0.001", limit_price="10000.00", stop_price="9500.00",
                                                  end_time="2023-05-04T16:17",
                                                  stop_direction="STOP_DIRECTION_STOP_DOWN"),
            },
        }

    def test_ignore_extra_kwargs(self):
        serialized_json = self.test_data["MARKET_IOC"]["serialized_json"]
        market_ioc = MarketMarketIOC(**json.loads(serialized_json), extra_arg="ignored")
        self.assertNotIn("extra_arg", asdict(market_ioc))

    def test_order_type_equivalence(self):
        for order_type in OrderType:
            coinbase_type = getattr(CoinbaseAdvancedTradeOrderType, order_type.name)
            self.assertEqual(order_type.name, coinbase_type.name)
            self.assertEqual(order_type.value, coinbase_type.value)

            # Equality, sameness cannot be achieved without a more complex definition of the Enum
            self.assertEqual(order_type, coinbase_type)

    def test_dataclasses(self):
        for key, test_data in self.test_data.items():
            with self.subTest(key=key):
                order_type_enum = CoinbaseAdvancedTradeOrderType[key]
                order_dataclass = coinbase_advanced_trade_order_type_mapping[order_type_enum]
                # Extract the fields from deserialized_data
                deserialized_data = test_data["deserialized_data"]
                field_values = {field.name: getattr(deserialized_data, field.name) for field in
                                dataclasses.fields(deserialized_data)}

                # Pass the field values to the constructor
                instance = order_dataclass(**field_values)
                self.assertTrue(is_dataclass(instance))

    def test_json_serialization_deserialization(self):
        for key, test_data in self.test_data.items():
            with self.subTest(key=key):
                order_type_enum = CoinbaseAdvancedTradeOrderType[key]
                order_type = coinbase_advanced_trade_order_type_mapping[order_type_enum]

                expected_json = test_data["serialized_json"]
                order = test_data["deserialized_data"]

                # Serialize
                serialized_json = json.dumps(asdict(order), default=str)
                # Deserialize
                deserialized_data = order_type(**json.loads(serialized_json))

                # Assertions
                self.assertEqual(json.loads(expected_json), json.loads(serialized_json))
                self.assertEqual(test_data["deserialized_data"], deserialized_data)

    def test_create_order(self):
        order_data = {
            "client_order_id": "test_order",
            "product_id": "BTC-USD",
            "side": "BUY",
            "order_configuration": {
                "base_size": "0.001",
                "limit_price": "10000.00",
            },
        }

        order = Order(
            client_order_id=order_data["client_order_id"],
            product_id=order_data["product_id"],
            side=order_data["side"],
            order_configuration=LimitGTC(**order_data["order_configuration"]),
        )

        self.assertTrue(is_dataclass(order))
        self.assertEqual(order.client_order_id, order_data["client_order_id"])
        self.assertEqual(order.product_id, order_data["product_id"])
        self.assertEqual(order.side, order_data["side"])
        self.assertIsInstance(order.order_configuration, LimitGTC)

        serialized_order = json.dumps(asdict(order))
        deserialized_order = json.loads(serialized_order)

        self.assertEqual(deserialized_order["client_order_id"], order_data["client_order_id"])
        self.assertEqual(deserialized_order["product_id"], order_data["product_id"])
        self.assertEqual(deserialized_order["side"], order_data["side"])

        deserialized_order_configuration = deserialized_order["order_configuration"]
        for field, value in order_data["order_configuration"].items():
            self.assertEqual(deserialized_order_configuration[field], value)


if __name__ == "__main__":
    unittest.main()
