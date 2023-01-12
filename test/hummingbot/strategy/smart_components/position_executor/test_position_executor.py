import unittest


class TestPositionExecutor(unittest.TestCase):
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
