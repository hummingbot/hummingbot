from decimal import Decimal
from unittest.mock import MagicMock

import pytest
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


@pytest.fixture
def mock_config():
    """Provide a valid executor config."""
    return MockExecutorConfig(
        trading_pair="BTC-USDT",
        amount=Decimal("1.0"),
        timestamp=1234567890,
    )


@pytest.fixture(autouse=True)
def register_mock_config():
    """Register mock config with factory before each test."""
    ExecutorFactory._registry[MockExecutorConfig] = "mock_executor"
    yield
    ExecutorFactory._registry.pop(MockExecutorConfig, None)


class TestExecutorActions:
    """Test suite for executor actions."""

    def test_create_action_from_base(self, mock_config):
        """Test creating action using base class factory method."""
        # Register config with factory
        ExecutorFactory._registry[MockExecutorConfig] = "mock_executor"

        action = ExecutorAction.create(
            controller_id="test",
            executor_config=mock_config,
        )

        assert action.action_type == "create"
        assert action.controller_id == "test"
        assert action.executor_config == mock_config
        assert action.executor_id is None
        assert action.keep_position is False

    def test_create_action_specialized(self, mock_config):
        """Test creating action using specialized class."""
        # Register config with factory
        ExecutorFactory._registry[MockExecutorConfig] = "mock_executor"

        action = CreateExecutorAction(
            controller_id="test",
            executor_config=mock_config,
        )

        assert action.action_type == "create"
        assert isinstance(action, CreateExecutorAction)
        assert action.executor_config == mock_config

    def test_stop_action_from_base(self):
        """Test creating stop action using base class factory method."""
        action = ExecutorAction.stop(
            controller_id="test",
            executor_id="exec_1",
        )

        assert action.action_type == "stop"
        assert action.controller_id == "test"
        assert action.executor_id == "exec_1"
        assert action.executor_config is None

    def test_stop_action_specialized(self):
        """Test creating stop action using specialized class."""
        action = StopExecutorAction(
            controller_id="test",
            executor_id="exec_1",
        )

        assert action.action_type == "stop"
        assert isinstance(action, StopExecutorAction)
        assert action.executor_id == "exec_1"

    def test_store_action_from_base(self):
        """Test creating store action using base class factory method."""
        action = ExecutorAction.store(
            controller_id="test",
            executor_id="exec_1",
        )

        assert action.action_type == "store"
        assert action.controller_id == "test"
        assert action.executor_id == "exec_1"

    def test_store_action_specialized(self):
        """Test creating store action using specialized class."""
        action = StoreExecutorAction(
            controller_id="test",
            executor_id="exec_1",
        )

        assert action.action_type == "store"
        assert isinstance(action, StoreExecutorAction)
        assert action.executor_id == "exec_1"

    def test_invalid_executor_config(self):
        with pytest.raises(ValidationError) as exc_info:
            CreateExecutorAction(
                controller_id="test",
                executor_config={"invalid": "config"},  # Dict instead of object
            )
        errors = exc_info.value.errors()
        # Fails validation of ExecutorConfigBase
        assert errors == [
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
        ]

    def test_unregistered_executor_config(self):
        """Test validation of unregistered executor config."""

        class MockUnregisteredExecutorConfig(ExecutorConfigBase):
            """Mock config for testing."""
            type: str = "mock"
            trading_pair: str
            amount: Decimal

        with pytest.raises(ValidationError) as exc_info:
            CreateExecutorAction(
                controller_id="test",
                executor_config=MockUnregisteredExecutorConfig(
                    trading_pair="BTC-USDT",
                    amount=Decimal("1.0"),
                    timestamp=1234567890,
                ),
            )
        assert "Executor config not registered with ExecutorFactory" in str(exc_info.value)

    def test_missing_required_fields(self):
        """Test validation of missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            CreateExecutorAction()

        error_dict = exc_info.value.errors()
        assert any("controller_id" in e["loc"] for e in error_dict)

    def test_stop_action_missing_executor_id(self):
        """Test stop action without executor_id."""
        with pytest.raises(ValidationError) as exc_info:
            StopExecutorAction(
                controller_id="test",
                executor_id=None,
            )

        error_dict = exc_info.value.errors()
        assert any("executor_id" in e["loc"] for e in error_dict)

    def test_action_immutability(self, mock_config):
        """Test that actions are immutable once created."""
        ExecutorFactory._registry[MockExecutorConfig] = "mock_executor"

        action = CreateExecutorAction(
            controller_id="test",
            executor_config=mock_config,
        )

        with pytest.raises(TypeError):
            action.action_type = "stop"

    @pytest.mark.parametrize("action_type", [
        "create",
        "stop",
        "store",
    ])
    def test_action_type_validation(self, action_type, mock_config):
        """Test validation of action types."""
        action = ExecutorAction(
            action_type=action_type,
            controller_id="test",
            executor_id="exec_1",
            executor_config=mock_config,
        )
        assert action.action_type == action_type

    def test_invalid_action_type(self):
        """Test validation of invalid action type."""
        with pytest.raises(ValidationError):
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
        assert isinstance(action.update_data, MockUpdate)

        # Test wrong update type
        class WrongUpdate(ExecutorUpdateBase):
            other_value: str

        with pytest.raises(ValidationError) as exc_info:
            UpdateExecutorAction(
                controller_id="test",
                executor_id="exec_1",
                update_data=WrongUpdate(other_value="wrong"),
            )
        assert "Invalid update type" in str(exc_info.value)

        # Test missing update data
        with pytest.raises(ValidationError) as exc_info:
            UpdateExecutorAction(
                controller_id="test",
                executor_id="exec_1",
            )
        assert "update_data is required" in str(exc_info.value)
