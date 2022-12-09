import unittest
from dataclasses import dataclass

from hummingbot.logger import log_encoder


class LoggerUtilFunctionsTest(unittest.TestCase):
    def test_log_encoder_encodes_dataclasses(self):
        @dataclass
        class DummyDataClass:
            one: int
            two: float

        encoded = log_encoder(DummyDataClass(one=1, two=2.0))

        self.assertEqual({"one": 1, "two": 2.0}, encoded)
