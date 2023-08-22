from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.smart_components.controller_base import ControllerBase
from hummingbot.smart_components.executor_handler_base import ExecutorHandlerBase


class TestExecutorHandlerBase(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
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

    @patch("pandas.DataFrame.to_csv", new_callable=MagicMock)
    def test_store_executor(self, _):
        mock_executor = MagicMock()
        mock_executor.to_json = MagicMock(return_value={"test": "test"})
        mock_order_level = MagicMock()
        self.executor_handler.store_executor(mock_executor, mock_order_level)
        self.assertIsNone(self.executor_handler.level_executors[mock_order_level.level_id])

    @patch.object(ExecutorHandlerBase, "_sleep", new_callable=AsyncMock)
    @patch.object(ExecutorHandlerBase, "control_task", new_callable=AsyncMock)
    async def test_control_loop(self, mock_control_task, mock_sleep):
        mock_sleep.side_effect = [None, Exception]
        with self.assertRaises(Exception):
            await self.executor_handler.control_loop()
        mock_control_task.assert_called()
