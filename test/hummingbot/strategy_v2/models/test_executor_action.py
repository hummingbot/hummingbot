import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from pydantic import ValidationError

from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase, ExecutorUpdateBase
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
    UpdateExecutorAction,
)


class MockExecutorConfig(ExecutorConfigBase):
    """Mock config for testing."""
    type: str = "mock"
    trading_pair: str
    amount: Decimal


class TestExecutorActions(unittest.TestCase):
    """Test suite for executor actions."""

    def setUp(self):
        """Register mock config with factory before each test."""
        self.mock_config = MockExecutorConfig(
            trading_pair="BTC-USDT",
            amount=Decimal("1.0"),
            timestamp=1234567890,
        )
        ExecutorFactory._registry[MockExecutorConfig] = "mock_executor"

    def tearDown(self):
        """Unregister mock config with factory after each test."""
        ExecutorFactory._registry.pop(MockExecutorConfig, None)

    def test_create_action_from_base(self):
        """Test creating action using base class factory method."""
        action = ExecutorAction.create(
            controller_id="test",
            executor_config=self.mock_config,
        )

        self.assertEqual(action.action_type, "create")
        self.assertEqual(action.controller_id, "test")
        self.assertEqual(action.executor_config, self.mock_config)
        self.assertIsNone(action.executor_id)
        self.assertFalse(action.keep_position)

    def test_create_action_specialized(self):
        """Test creating action using specialized class."""
        action = CreateExecutorAction(
            controller_id="test",
            executor_config=self.mock_config,
        )

        self.assertEqual(action.action_type, "create")
        self.assertIsInstance(action, CreateExecutorAction)
        self.assertEqual(action.executor_config, self.mock_config)

    def test_stop_action_from_base(self):
        """Test creating stop action using base class factory method."""
        action = ExecutorAction.stop(
            controller_id="test",
            executor_id="exec_1",
        )

        self.assertEqual(action.action_type, "stop")
        self.assertEqual(action.controller_id, "test")
        self.assertEqual(action.executor_id, "exec_1")
        self.assertIsNone(action.executor_config)

    def test_stop_action_specialized(self):
        """Test creating stop action using specialized class."""
        action = StopExecutorAction(
            controller_id="test",
            executor_id="exec_1",
        )

        self.assertEqual(action.action_type, "stop")
        self.assertIsInstance(action, StopExecutorAction)
        self.assertEqual(action.executor_id, "exec_1")

    def test_store_action_from_base(self):
        """Test creating store action using base class factory method."""
        action = ExecutorAction.store(
            controller_id="test",
            executor_id="exec_1",
        )

        self.assertEqual(action.action_type, "store")
        self.assertEqual(action.controller_id, "test")
        self.assertEqual(action.executor_id, "exec_1")

    def test_store_action_specialized(self):
        """Test creating store action using specialized class."""
        action = StoreExecutorAction(
            controller_id="test",
            executor_id="exec_1",
        )

        self.assertEqual(action.action_type, "store")
        self.assertIsInstance(action, StoreExecutorAction)
        self.assertEqual(action.executor_id, "exec_1")

    def test_invalid_executor_config(self):
        with self.assertRaises(ValidationError) as exc_info:
            CreateExecutorAction(
                controller_id="test",
                executor_config={"invalid": "config"},  # Dict instead of object
            )
        errors = exc_info.exception.errors()
        self.assertEqual(errors, [
            {'loc': ('executor_config', 'type'),
             'msg': 'field required',
             'type': 'value_error.missing'
             },
            {'loc': ('executor_config', 'timestamp'),
             'msg': 'field required',
             'type': 'value_error.missing'
             },
            {'loc': ('__root__',),
             'msg': 'executor_config is required for create action',
             'type': 'value_error'
             }
        ])

    def test_unregistered_executor_config(self):
        """Test validation of unregistered executor config."""

        class MockUnregisteredExecutorConfig(ExecutorConfigBase):
            """Mock config for testing."""
            type: str = "mock"
            trading_pair: str
            amount: Decimal

        with self.assertRaises(ValidationError) as exc_info:
            CreateExecutorAction(
                controller_id="test",
                executor_config=MockUnregisteredExecutorConfig(
                    trading_pair="BTC-USDT",
                    amount=Decimal("1.0"),
                    timestamp=1234567890,
                ),
            )
        self.assertIn("Executor config not registered with ExecutorFactory", str(exc_info.exception))

    def test_missing_required_fields(self):
        """Test validation of missing required fields."""
        with self.assertRaises(ValidationError) as exc_info:
            CreateExecutorAction()

        error_dict = exc_info.exception.errors()
        self.assertTrue(any("controller_id" in e["loc"] for e in error_dict))

    def test_stop_action_missing_executor_id(self):
        """Test stop action without executor_id."""
        with self.assertRaises(ValidationError) as exc_info:
            StopExecutorAction(
                controller_id="test",
                executor_id=None,
            )

        error_dict = exc_info.exception.errors()
        self.assertTrue(any("executor_id" in e["loc"] for e in error_dict))

    def test_action_immutability(self):
        """Test that actions are immutable once created."""
        action = CreateExecutorAction(
            controller_id="test",
            executor_config=self.mock_config,
        )

        with self.assertRaises(TypeError):
            action.action_type = "stop"

    def test_action_type_validation(self):
        """Test validation of action types."""
        for action_type in ["create", "stop", "store"]:
            with self.subTest(action_type=action_type):
                action = ExecutorAction(
                    action_type=action_type,
                    controller_id="test",
                    executor_id="exec_1",
                    executor_config=self.mock_config,
                )
                self.assertEqual(action.action_type, action_type)

    def test_invalid_action_type(self):
        """Test validation of invalid action type."""
        with self.assertRaises(ValidationError):
            ExecutorAction(
                action_type="invalid",
                controller_id="test",
            )

    def test_executor_update_validation(self):
        """Test validation of executor updates."""
        # Create mock update type
        class MockUpdate(ExecutorUpdateBase):
            value: int

        # Create mock config type
        class MockConfig(ExecutorConfigBase):
            type: str = "mock"
            id: str = "exec_1"

        # Register executor with update type
        @ExecutorFactory.register_executor(
            config_type=MockConfig,
            update_type=MockUpdate,
        )
        class MockExecutor(ExecutorBase):
            def update_live(self, update_data: MockUpdate) -> None:
                pass

        ExecutorFactory.create_executor(
            strategy=MagicMock(name="MockStrategy"),
            config=MockConfig(timestamp=1234567890),
            update_interval=1.0,
        )

        # Test valid update
        action = UpdateExecutorAction(
            controller_id="test",
            executor_id="exec_1",
            update_data=MockUpdate(value=42),
        )
        self.assertIsInstance(action.update_data, MockUpdate)

        # Test wrong update type
        class WrongUpdate(ExecutorUpdateBase):
            other_value: str

        with self.assertRaises(ValidationError) as exc_info:
            UpdateExecutorAction(
                controller_id="test",
                executor_id="exec_1",
                update_data=WrongUpdate(other_value="wrong"),
            )
        self.assertIn("Invalid update type", str(exc_info.exception))

        # Test missing update data
        with self.assertRaises(ValidationError) as exc_info:
            UpdateExecutorAction(
                controller_id="test",
                executor_id="exec_1",
            )
        self.assertIn("update_data is required", str(exc_info.exception))


if __name__ == "__main__":
    unittest.main()
