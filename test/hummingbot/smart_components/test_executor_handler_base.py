import unittest
from unittest.mock import MagicMock, patch

from hummingbot.smart_components.controller_base import ControllerBase
from hummingbot.smart_components.executor_handler_base import ExecutorHandlerBase


class TestExecutorHandlerBase(unittest.TestCase):
    def setUp(self):
        self.mock_strategy = MagicMock()
        self.mock_controller = MagicMock(spec=ControllerBase)
        self.mock_controller.config = MagicMock()
        self.mock_controller.config.order_levels = []
        self.mock_controller.get_csv_prefix = MagicMock(return_value="test_strategy")
        self.executor_handler = ExecutorHandlerBase(self.mock_strategy, self.mock_controller)

    def test_initialization(self):
        self.assertEqual(self.executor_handler.strategy, self.mock_strategy)
        self.assertEqual(self.executor_handler.controller, self.mock_controller)
        # ... other assertions ...

    @patch("hummingbot.smart_components.executor_handler_base.safe_ensure_future")
    def test_start(self, mock_safe_ensure_future):
        self.executor_handler.start()
        self.mock_controller.start.assert_called_once()
        mock_safe_ensure_future.assert_called_once()

    def test_terminate_control_loop(self):
        self.executor_handler.terminate_control_loop()
        self.assertTrue(self.executor_handler.terminated.is_set())

    def test_to_format_status(self):
        status = self.executor_handler.to_format_status()
        self.assertIsInstance(status, str)

    def test_on_stop(self):
        self.executor_handler.on_stop()
        self.mock_controller.stop.assert_called_once()

    def test_get_csv_path(self):
        path = self.executor_handler.get_csv_path()
        self.assertTrue(path.endswith(".csv"))
        self.assertIn("test_strategy", path)
