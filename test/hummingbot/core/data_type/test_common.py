from typing import Set
from unittest import TestCase

from hummingbot.core.data_type.common import GroupedSetDict, LazyDict


class GroupedSetDictTests(TestCase):
    def setUp(self):
        self.dict = GroupedSetDict[str, str]()

    def test_add_or_update_new_key(self):
        self.dict.add_or_update("key1", "value1")
        self.assertEqual(self.dict["key1"], {"value1"})

    def test_add_or_update_existing_key(self):
        self.dict.add_or_update("key1", "value1")
        self.dict.add_or_update("key1", "value2")
        self.assertEqual(self.dict["key1"], {"value1", "value2"})

    def test_add_or_update_chaining(self):
        (self.dict.add_or_update("key1", "value1")
            .add_or_update("key1", "value2")
            .add_or_update("key1", "value2")  # This should be a no-op
            .add_or_update("key2", "value1"))
        self.assertEqual(self.dict["key1"], {"value1", "value2"})
        self.assertEqual(self.dict["key2"], {"value1"})

    def test_add_or_update_multiple_values(self):
        self.dict.add_or_update("key1", "value1", "value2", "value3")
        self.assertEqual(self.dict["key1"], {"value1", "value2", "value3"})

    def test_market_dict_type(self):
        market_dict = GroupedSetDict[str, Set[str]]()
        market_dict.add_or_update("exchange1", "BTC-USDT")
        self.assertEqual(market_dict["exchange1"], {"BTC-USDT"})


class LambdaDictTests(TestCase):
    def setUp(self):
        self.dict = LazyDict[str, int]()

    def test_get_or_add_new_key(self):
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return 42
        value = self.dict.get_or_add("key1", factory)

        self.assertEqual(value, 42)
        self.assertEqual(call_count, 1)
        # Verify factory not called again on subsequent gets
        self.assertEqual(self.dict.get_or_add("key1", factory), 42)
        self.assertEqual(call_count, 1)

        # Verify factory is called again for new key
        self.assertEqual(self.dict.get_or_add("key2", factory), 42)
        self.assertEqual(call_count, 2)

    def test_get_or_add_existing_key(self):
        self.dict["key1"] = 42

        def factory():
            return 100
        value = self.dict.get_or_add("key1", factory)
        self.assertEqual(value, 42)
        self.assertEqual(self.dict["key1"], 42)

    def test_default_value_factory(self):
        call_count = 0

        def factory(key: str) -> int:
            nonlocal call_count
            call_count += 1
            return len(key)
        self.dict = LazyDict[str, int](default_value_factory=factory)
        self.assertEqual(self.dict["key1"], 4)
        self.assertEqual(call_count, 1)
        # Verify factory is not called again for existing key
        self.assertEqual(self.dict["key1"], 4)
        self.assertEqual(self.dict.get("key1"), 4)
        self.assertEqual(call_count, 1)
        # Verify factory is called again for new key
        self.assertEqual(self.dict["longer_key"], 10)
        self.assertEqual(self.dict.get("longer_key"), 10)
        self.assertEqual(call_count, 2)

    def test_missing_key_no_factory(self):
        with self.assertRaises(KeyError):
            _ = self.dict["nonexistent"]
        with self.assertRaises(KeyError):
            _ = self.dict.get("nonexistent")


if __name__ == '__main__':
    TestCase.main()
