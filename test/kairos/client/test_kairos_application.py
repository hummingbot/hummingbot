import unittest

from kairos.client.kairos_application import KairosApplication


class KairosApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app = KairosApplication()

    def test_set_strategy_file_name(self):
        strategy_name = "some-strategy"
        file_name = f"{strategy_name}.yml"
        self.app.strategy_file_name = file_name

        self.assertEqual(file_name, self.app.strategy_file_name)

    def test_set_strategy_file_name_to_none(self):
        strategy_name = "some-strategy"
        file_name = f"{strategy_name}.yml"

        self.app.strategy_file_name = None

        self.assertEqual(None, self.app.strategy_file_name)

        self.app.strategy_file_name = file_name
        self.app.strategy_file_name = None

        self.assertEqual(None, self.app.strategy_file_name)
