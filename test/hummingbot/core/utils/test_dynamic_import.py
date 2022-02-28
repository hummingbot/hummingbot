import tempfile
import unittest
from hummingbot.core.utils.dynamic_import import import_lite_strategy_sub_class
from hummingbot.strategy.lite_strategy_base import LiteStrategyBase
from hummingbot.exceptions import InvalidLiteStrategyFile


class DynamicImportTest(unittest.TestCase):

    def test_import_valid_lite_strategy_sub_class(self):
        temp_dir = tempfile.gettempdir()
        file_path = temp_dir + "/lite_test.py"
        with open(file_path, 'w') as f:
            f.write("from hummingbot.strategy.lite_strategy_base import LiteStrategyBase\n")
            f.write("class LiteTest(LiteStrategyBase):\n")
            f.write("  pass\n")
        lite_class = import_lite_strategy_sub_class(file_path)
        self.assertTrue(issubclass(lite_class, LiteStrategyBase))

    def test_import_invalid_lite_strategy_sub_class(self):
        temp_dir = tempfile.gettempdir()
        file_path = temp_dir + "/lite_test.py"
        with open(file_path, 'w') as f:
            f.write("class LiteTest:\n")
            f.write("  pass\n")
        with self.assertRaises(InvalidLiteStrategyFile) as context:
            import_lite_strategy_sub_class(file_path)
        self.assertEqual(str(context.exception), "The file does not contain any LiteStrategyBase derived class.")
