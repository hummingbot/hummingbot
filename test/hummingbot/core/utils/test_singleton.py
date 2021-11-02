import unittest

from hummingbot.core.utils.singleton import Singleton


class SingletonTest(unittest.TestCase):
    def test_singleton(self):
        class SomeClass(metaclass=Singleton):
            pass

        s1 = SomeClass()
        s2 = SomeClass()

        self.assertEqual(id(s1), id(s2))
