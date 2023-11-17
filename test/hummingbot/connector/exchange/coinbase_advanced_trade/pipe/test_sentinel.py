import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import SENTINEL, sentinel_ize


class TestSentinelIze(unittest.TestCase):

    def test_with_sentinel(self):
        items = (1, 2, SENTINEL, 3)
        expected = (1, 2, SENTINEL)
        result = sentinel_ize(items)
        self.assertEqual(result, expected)

    def test_without_sentinel(self):
        items = (1, 2, 3)
        expected = (1, 2, 3, SENTINEL)
        result = sentinel_ize(items)
        self.assertEqual(result, expected)

    def test_multiple_sentinels(self):
        items = (1, 2, SENTINEL, 3, SENTINEL)
        expected = (1, 2, SENTINEL)
        result = sentinel_ize(items)
        self.assertEqual(result, expected)

    def test_non_tuple_singleton(self):
        item = 1
        expected = (1, SENTINEL)
        result = sentinel_ize(item)
        self.assertEqual(result, expected)

    def test_non_tuple_list(self):
        item = [1, 2]
        expected = ([1, 2], SENTINEL)
        result = sentinel_ize(item)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
