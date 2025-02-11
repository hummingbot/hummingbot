# test/hummingbot/strategy_v2/executors/test_executor_factory.py
import time
import uuid

import pytest

from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory

from ..test_data import TestCustomInfo, TestExecutorConfig, TestExecutorUpdate


class TestExecutorFactoryRegistration:
    """Test executor registration functionality"""

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_basic_registration(self, test_executor_class, mock_strategy, test_config):
        """Test basic executor registration and creation"""
        # Register executor
        decorated_class = ExecutorFactory.register_executor(TestExecutorConfig)(test_executor_class)

        # Verify registration
        assert TestExecutorConfig in ExecutorFactory._registry
        assert ExecutorFactory._registry[TestExecutorConfig] == decorated_class

        # Create and verify executor
        executor = ExecutorFactory.create_executor(mock_strategy, test_config, 1.0)

        assert isinstance(executor, test_executor_class)
        assert executor.config == test_config
        assert executor.strategy == mock_strategy
        assert executor.update_interval == 1.0

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_registration_with_update_type(self, test_executor_class):
        """Test registration with update type"""
        ExecutorFactory.register_executor(
            TestExecutorConfig,
            update_type=TestExecutorUpdate
        )(test_executor_class)

        assert TestExecutorConfig in ExecutorFactory._update_types
        assert ExecutorFactory._update_types[TestExecutorConfig] == TestExecutorUpdate

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_registration_with_custom_info(self, test_executor_class, mock_strategy):
        """Test registration with custom info type"""
        # Register with custom info
        ExecutorFactory.register_executor(
            TestExecutorConfig,
            custom_info_type=TestCustomInfo,
        )(test_executor_class)

        # Create config and executor
        config = TestExecutorConfig(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            controller_id="test_controller",
        )
        executor = ExecutorFactory.create_executor(mock_strategy, config, 1.0)

        # Verify registration
        assert TestExecutorConfig in ExecutorFactory._custom_info_types
        assert ExecutorFactory._custom_info_types[TestExecutorConfig] == TestCustomInfo

        # Verify custom info creation and properties
        custom_info = ExecutorFactory.get_custom_info(executor)
        assert isinstance(custom_info, TestCustomInfo)
        assert custom_info.side == config.side

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_duplicate_registration_with_different_params(self, test_executor_class):
        """Test that duplicate registration raises error even with different parameters"""
        # First registration
        ExecutorFactory.register_executor(
            TestExecutorConfig,
            custom_info_type=TestCustomInfo,
        )(test_executor_class)

        # Attempt second registration with different parameters
        with pytest.raises(ValueError, match="already registered"):
            ExecutorFactory.register_executor(
                TestExecutorConfig,
                update_type=TestExecutorUpdate,
            )(test_executor_class)

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_get_update_type(self, test_executor_class, mock_strategy):
        """Test get_update_type method behavior"""
        # Register with update type
        ExecutorFactory.register_executor(
            TestExecutorConfig,
            update_type=TestExecutorUpdate,
        )(test_executor_class)

        # Verify registered update type
        update_type = ExecutorFactory.get_update_type(TestExecutorConfig)
        assert update_type == TestExecutorUpdate

        # Create config and executor
        config = TestExecutorConfig(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            controller_id="test_controller",
        )
        ExecutorFactory.create_executor(mock_strategy, config, 1.0)

        # Test update instance can be created and validated
        update = TestExecutorUpdate(value="test_update")
        assert update.validate()

    @pytest.mark.usefixtures("factory_registry_cleanup")
    def test_get_config_type_for_executor_lifecycle(self, test_executor_class, mock_strategy):
        """Test get_config_type_for_executor through registration and creation lifecycle"""
        # Register executor
        ExecutorFactory.register_executor(TestExecutorConfig)(test_executor_class)

        # Create multiple executors with different configs
        config1 = TestExecutorConfig(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            controller_id="controller_1",
        )
        config2 = TestExecutorConfig(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            controller_id="controller_2",
        )

        ExecutorFactory.create_executor(mock_strategy, config1, 1.0)
        ExecutorFactory.create_executor(mock_strategy, config2, 1.0)

        # Verify config type can be retrieved for both executors
        assert ExecutorFactory.get_config_type_for_executor(config1.id) == TestExecutorConfig
        assert ExecutorFactory.get_config_type_for_executor(config2.id) == TestExecutorConfig

        # Verify behavior with unknown executor id
        unknown_id = str(uuid.uuid4())
        assert ExecutorFactory.get_config_type_for_executor(unknown_id) is None
